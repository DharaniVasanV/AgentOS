"""
app/services/browser.py

*** THIS IS THE FILE MOST LIKELY TO NEED ADJUSTMENT AGAINST YOUR REAL
*** MEETING LINKS. Google Meet's DOM is relatively stable; Zoom and
*** Teams change button text/labels/waiting-room flows often enough
*** that hardcoded selectors WILL eventually break. Treat the
*** selectors below as a working starting point, not a guarantee.

Purpose
-------
Uses Playwright to launch a headless(ish) Chromium instance, disable
camera/mic, navigate to a meeting URL, and click through whatever
"join" flow that platform requires.

Responsibilities
----------------
- launch_browser(): one Chromium instance per meeting, camera/mic
  permissions denied at the context level (belt-and-suspenders on top
  of also disabling them at the OS/driver level)
- join_meeting(): dispatches to the platform-specific join function
- Each platform function returns True/False for success so
  meeting_joiner.py can retry / mark the meeting failed

Flow
----
meeting_joiner.py -> join_meeting(meeting_url, platform, bot_name)
    -> launch_browser()
    -> page.goto(meeting_url)
    -> platform-specific join steps
    -> return (success: bool, page: Page | None, browser: Browser | None)

Dependencies
------------
playwright.async_api
"""

import os

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_JOIN_TIMEOUT_MS = 20_000
_SESSION_FILE = "/app/google_session.json"  # path inside Docker container


async def launch_browser() -> tuple[Browser, BrowserContext, Page]:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            # Grant mic/camera permissions without a dialog, but do NOT use fake device.
            # Fake device bypasses PulseAudio entirely — Chromium would internally route
            # all audio (including received WebRTC audio) to its own fake device, making
            # the PulseAudio meetingsink always silent.
            "--use-fake-ui-for-media-stream",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--autoplay-policy=no-user-gesture-required",
            # Do NOT disable AudioServiceOutOfProcess - the out-of-process audio service
            # is what actually connects Chromium to the PulseAudio daemon
            "--disable-features=WebRtcHideLocalIpsWithMdns",
            # Ensure Chromium uses ALSA → PulseAudio plugin (not direct ALSA)
            "--use-gl=swiftshader",
        ],
        # Inherit full OS env so PULSE_SINK/PULSE_SOURCE from start_all.sh are visible to Chromium
    )

    common_ctx = dict(
        permissions=["camera", "microphone"],
        geolocation=None,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 720},
        locale="en-US",
    )

    # --- CLOUD DEPLOYMENT SUPPORT: Build json from Base64 ENV if provided ---
    session_b64 = os.environ.get("GOOGLE_SESSION_B64")
    if session_b64:
        import base64
        try:
            with open(_SESSION_FILE, "wb") as f:
                f.write(base64.b64decode(session_b64))
            logger.info("Successfully decoded Google Session from Environment Variable!")
        except Exception:
            logger.exception("Failed to decode GOOGLE_SESSION_B64.")

    # Load saved Google session if it exists
    if os.path.exists(_SESSION_FILE):
        logger.info("Loading saved Google session from %s", _SESSION_FILE)
        context = await browser.new_context(storage_state=_SESSION_FILE, **common_ctx)
    else:
        logger.warning(
            "No Google session found at %s. "
            "Click 'Connect Bot Account' on the dashboard or run: python save_google_session.py",
            _SESSION_FILE,
        )
        context = await browser.new_context(**common_ctx)

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    page = await context.new_page()
    return browser, context, page


async def _google_sign_in(page: Page) -> bool:
    """Sign in to Google with the bot credentials before joining Meet.
    Returns True if login succeeded, False if credentials are missing or login failed."""
    email = settings.GOOGLE_BOT_EMAIL
    password = settings.GOOGLE_BOT_PASSWORD

    if not email or not password:
        logger.warning("GOOGLE_BOT_EMAIL / GOOGLE_BOT_PASSWORD not set — bot will join as guest.")
        return False

    try:
        logger.info("Signing in to Google as %s", email)
        await page.goto(
            "https://accounts.google.com/signin/v2/identifier",
            wait_until="networkidle",
            timeout=30_000,
        )

        # Handle "Choose an account" screen (shown when cookies from a prior session exist)
        use_another = page.locator('li[data-identifier*="@"], [data-email], div:has-text("Use another account")')
        if await use_another.count() > 0:
            another_btn = page.locator('div:has-text("Use another account")')
            if await another_btn.count() > 0:
                await another_btn.last.click()
                await page.wait_for_timeout(2000)

        # Wait for the email input to actually appear
        await page.wait_for_selector(
            'input[type="email"], input[name="Email"]',
            state="visible",
            timeout=20_000,
        )

        email_input = page.locator('input[type="email"], input[name="Email"]').first
        await email_input.click()
        await email_input.fill(email)
        await page.wait_for_timeout(500)

        # Click Next
        await page.locator('#identifierNext, button:has-text("Next")').first.click()

        # Wait for password field
        await page.wait_for_selector(
            'input[type="password"], input[name="Passwd"]',
            state="visible",
            timeout=15_000,
        )

        pwd_input = page.locator('input[type="password"], input[name="Passwd"]').first
        await pwd_input.click()
        await pwd_input.fill(password)
        await page.wait_for_timeout(500)

        # Click Next / Sign in
        await page.locator('#passwordNext, button:has-text("Next")').first.click()

        # Wait for redirect away from accounts.google.com
        await page.wait_for_url(
            lambda url: "accounts.google.com" not in url,
            timeout=20_000,
        )
        logger.info("Google sign-in successful")
        return True
    except Exception:
        logger.exception("Google sign-in failed — proceeding as guest")
        return False


async def _join_google_meet(page: Page, meeting_url: str, bot_name: str) -> bool:
    try:
        # Authentication is handled at launch time via the saved session file
        # (loaded in launch_browser). No sign-in needed here.

        # Use a longer timeout — Docker network can be slow loading Meet
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(4000)

        # 0. Handle Google Cloud IP Security Interception (Account Chooser)
        if "accounts.google.com" in page.url:
            logger.warning("Google intercepted the meeting URL with a security chooser (likely due to Render IP change).")
            # Click the saved account profile to continue
            acct_btn = page.locator('div[data-email], li[data-identifier], div[data-identifier]')
            try:
                if await acct_btn.count() > 0:
                    logger.info("Found saved profile tile, clicking to bypass chooser...")
                    await acct_btn.first.click(force=True, timeout=5000)
                    await page.wait_for_timeout(2000)
                    
                    # Handle Cloud IP re-auth (Google asking for password again)
                    pwd_input = page.locator('input[type="password"], input[name="Passwd"]')
                    if await pwd_input.count() > 0 and await pwd_input.first.is_visible():
                        logger.info("Google requested password re-verification, filling...")
                        await pwd_input.first.fill(settings.GOOGLE_BOT_PASSWORD)
                        await page.keyboard.press("Enter")
                    
                    # wait for it to process the click/login and redirect back to Meet
                    await page.wait_for_url(lambda url: "meet.google.com" in url, timeout=20_000)
                    await page.wait_for_timeout(3000)
            except Exception as ex:
                logger.warning(f"Could not cleanly bypass account chooser: {ex}")

        # 1. Dismiss any "Got it" / tracking / permission toasts or modals
        for popup_text in ["Got it", "Dismiss", "Continue without", "Close", "Allow"]:
            try:
                pop = page.locator(f'button:has-text("{popup_text}")')
                if await pop.count() > 0 and await pop.first.is_visible():
                    await pop.first.click(force=True, timeout=2000)
            except Exception:
                pass

        # 3. Mute camera & mic via hotkeys + DOM clicks prior to clicking join
        try:
            await page.keyboard.press("Control+d")
            await page.wait_for_timeout(300)
            await page.keyboard.press("Control+e")
            await page.wait_for_timeout(300)
        except Exception:
            pass

        for label in ["microphone", "mic", "camera", "video"]:
            btns = page.locator(f'[aria-label*="{label}" i]')
            try:
                count = await btns.count()
                for i in range(count):
                    aria = await btns.nth(i).get_attribute("aria-label")
                    if aria and "turn off" in aria.lower():
                        await btns.nth(i).click(force=True, timeout=2000)
                        await page.wait_for_timeout(200)
            except Exception:
                pass

        # 4. Click the exact Google Meet Join button candidate (with up to 30s polling for React to render)
        join_candidates = [
            'button:has-text("Ask to join")',
            'button:has-text("Join now")',
            'span:has-text("Ask to join")',
            'span:has-text("Join now")',
            'button:has-text("Join")',
            'span:has-text("Join")',
            'button[jsname="Qjft2e"]',
            '[aria-label*="Ask to join" i]',
            '[aria-label*="Join now" i]',
        ]

        clicked = False
        name_filled = False
        import time
        start_wait = time.time()
        
        while time.time() - start_wait < 40 and not clicked:
            # Poll for guest name input first! The join button might not render until we fill this.
            if not name_filled:
                name_input = page.locator('input[placeholder*="name" i], input[aria-label*="name" i], input[type="text"]')
                try:
                    if await name_input.count() > 0 and await name_input.first.is_visible():
                        logger.info("Found guest name input field, filling bot name '%s'", bot_name)
                        await name_input.first.fill(bot_name)
                        await name_input.first.press("Enter")
                        name_filled = True
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

            for sel in join_candidates:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    logger.info("Found Google Meet Join button matching '%s', clicking...", sel)
                    await loc.first.click(force=True, timeout=5000)
                    clicked = True
                    break
            
            if not clicked:
                await page.wait_for_timeout(1000)  # Sleep 1s and check DOM again

        if not clicked:
            logger.warning("After 30s, no standard Google Meet Join button appeared! Trying blind fallback click...")
            fallback = page.locator('button[jsname="Qjft2e"]')
            if await fallback.count() > 0:
                await fallback.first.click(force=True, timeout=5000)
                clicked = True

        if not clicked:
            logger.error("FATAL: Could not find ANY Join button to click on the screen!")
            # We explicitly raise so the except block screenshoots and fails the try immediately
            raise Exception("No Join button visible on screen after 30s wait.")

        # 5. Wait to enter meeting or waiting room
        # We must wait for the "Leave" button to appear. If we are placed in a waiting room
        # ("Asking to join..."), we may wait here for a LONG time until the host admits us.
        # We set this timeout to 15 minutes to avoid dropping out if the host is delayed.
        logger.info("Clicked Join! Waiting for host to admit bot (timeout 15m) or automatic entry...")
        leave_selector = '[aria-label*="Leave call" i], [aria-label*="Leave" i], button[jsname="CQeAdf"]'
        await page.locator(leave_selector).first.wait_for(timeout=900_000)
        logger.info("Successfully joined Google Meet call!")
        return True
    except Exception as e:
        logger.exception("Failed to join Google Meet at %s: %s", meeting_url, e)
        try:
            curr_url = page.url
            curr_title = await page.title()
            logger.error(f"FAILURE CONTEXT -> URL: {curr_url}")
            logger.error(f"FAILURE CONTEXT -> Title: {curr_title}")
            
            # Dump all button text on screen to see what we COULD have clicked
            buttons = page.locator("button, a, [role='button']")
            count = await buttons.count()
            ui_texts = []
            for i in range(count):
                text = await buttons.nth(i).inner_text()
                aria = await buttons.nth(i).get_attribute("aria-label")
                if text or aria:
                    ui_texts.append(f"Text='{text.strip()}' Aria='{aria}'")
            logger.error(f"FAILURE CONTEXT -> Visible Buttons/Links: {ui_texts}")
            
            html = await page.content()
            with open("/tmp/meet_join_failed.html", "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            pass
        return False


async def _join_zoom(page: Page, meeting_url: str, bot_name: str) -> bool:
    """Zoom web client join flow. NOTE: Zoom frequently requires the meeting
    host to admit from a waiting room, and the web client's DOM/iframe
    structure changes across releases — verify selectors against the
    current Zoom web client before relying on this in production."""
    try:
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=_JOIN_TIMEOUT_MS)

        # Zoom often nests the join UI in an iframe.
        frame = page
        for f in page.frames:
            if "zoom" in f.url:
                frame = f
                break

        name_input = frame.locator('input#inputname, input[name="uname"]')
        if await name_input.count() > 0:
            await name_input.first.fill(bot_name)

        join_btn = frame.locator('button:has-text("Join"), #joinBtn')
        await join_btn.first.click(timeout=_JOIN_TIMEOUT_MS)

        await page.locator('button[aria-label*="leave" i], button:has-text("Leave")').first.wait_for(timeout=60_000)
        return True
    except Exception:
        logger.exception("Failed to join Zoom meeting at %s", meeting_url)
        return False


async def _join_teams(page: Page, meeting_url: str, bot_name: str) -> bool:
    """Microsoft Teams web join flow. NOTE: Teams frequently forces an app-
    download interstitial ("Continue on this browser" / "Use the web app
    instead") before showing the name field — verify this path against a
    live Teams link, it is the flow most likely to have shifted."""
    try:
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=_JOIN_TIMEOUT_MS)

        continue_browser = page.locator('a:has-text("Continue on this browser"), button:has-text("Continue on this browser")')
        if await continue_browser.count() > 0:
            await continue_browser.first.click(timeout=5000)

        name_input = page.locator('input[data-tid="prejoin-display-name-input"]')
        if await name_input.count() > 0:
            await name_input.first.fill(bot_name)

        for tid in ["toggle-mute", "toggle-video"]:
            btn = page.locator(f'[data-tid="{tid}"][aria-pressed="false"]')
            if await btn.count() > 0:
                try:
                    await btn.first.click(timeout=3000)
                except Exception:
                    pass

        join_btn = page.locator('button[data-tid="prejoin-join-button"]')
        await join_btn.first.click(timeout=_JOIN_TIMEOUT_MS)

        await page.locator('[data-tid="hangup-leave-button"]').first.wait_for(timeout=60_000)
        return True
    except Exception:
        logger.exception("Failed to join Teams meeting at %s", meeting_url)
        return False


_PLATFORM_HANDLERS = {
    "google_meet": _join_google_meet,
    "zoom": _join_zoom,
    "teams": _join_teams,
}


async def join_meeting(meeting_url: str, platform: str, bot_name: str) -> tuple[bool, Browser | None, Page | None]:
    handler = _PLATFORM_HANDLERS.get(platform)
    if handler is None:
        logger.error("Unsupported platform '%s' for url %s", platform, meeting_url)
        return False, None, None

    browser, context, page = await launch_browser()
    success = await handler(page, meeting_url, bot_name)

    if not success:
        await context.close()
        await browser.close()
        return False, None, None

    return True, browser, page


async def leave_meeting(browser: Browser | None) -> None:
    if browser is not None:
        await browser.close()


async def is_meeting_active(page: Page | None, platform: str) -> bool:
    """Checks if the bot is still inside the meeting (hasn't been kicked or meeting ended)."""
    if not page or page.is_closed():
        return False
        
    try:
        if platform == "google_meet":
            return await page.locator('[aria-label*="Leave call" i]').count() > 0
        elif platform == "zoom":
            return await page.locator('button[aria-label*="leave" i], button:has-text("Leave")').count() > 0
        elif platform == "teams":
            return await page.locator('[data-tid="hangup-leave-button"]').count() > 0
    except Exception:
        pass
        
    return False
