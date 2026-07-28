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
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-features=AudioServiceOutOfProcess",
        ],
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
    if session_b64 and not os.path.exists(_SESSION_FILE):
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

        # Wait for Meet's JS to finish rendering the pre-join screen
        await page.wait_for_timeout(3000)

        # Dismiss any "Got it" tracking/permission toasts that intercept clicks
        try:
            got_it = page.locator('button:has-text("Got it"), button:has-text("Dismiss")')
            if await got_it.count() > 0:
                await got_it.first.click(timeout=3000)
        except Exception:
            pass

        # Google Meet constantly changes the aria-labels (e.g., "Turn off mic" vs "Turn off microphone").
        # We will use universally bulletproof Keyboard Shortcuts first:
        await page.locator('body').focus()
        await page.keyboard.press("Control+d") # Mute Mic
        await page.wait_for_timeout(500)
        await page.keyboard.press("Control+e") # Mute Camera
        await page.wait_for_timeout(500)

        # Belt-and-suspenders DOM brute force: Click any button actively stating "Turn off" for AV
        for label in ["microphone", "mic", "camera", "video"]:
            btns = page.locator(f'button[aria-label*="{label}" i]')
            try:
                count = await btns.count()
                for i in range(count):
                    aria = await btns.nth(i).get_attribute("aria-label")
                    if aria and "turn off" in aria.lower():
                        await btns.nth(i).click(timeout=2000)
            except Exception:
                pass

        # Ensure we always type the name if requested, and explicitly blur to trigger React state
        name_input = page.locator('input[placeholder*="name" i], input[aria-label*="name" i]')
        if await name_input.count() > 0:
            try:
                await name_input.first.wait_for(state="visible", timeout=5000)
                await name_input.first.fill(bot_name)
                await name_input.first.press("Tab") # Trigger blur to definitively enable the Join button
                await page.wait_for_timeout(500)
            except Exception:
                pass

        join_btn = page.locator('button:has-text("Ask to join"), button:has-text("Join now")')
        await join_btn.first.click(timeout=_JOIN_TIMEOUT_MS)

        # If it's "Ask to join", we now sit in a waiting room until admitted.
        # Detect the in-call state by waiting for the "leave call" control.
        await page.locator('[aria-label*="Leave call" i]').first.wait_for(timeout=60_000)
        return True
    except Exception:
        await page.screenshot(path='/app/meet_join_failed.png')
        try:
            html = await page.content()
            with open("/app/meet_join_failed.html", "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            pass
        logger.exception("Failed to join Google Meet at %s", meeting_url)
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
