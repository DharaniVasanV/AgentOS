"""
app/services/browser.py

Purpose
-------
Uses Playwright to launch a headless Chromium instance, navigate to a
meeting URL, and click through the join flow for Google Meet, Zoom, or Teams.

Google Meet is always joined as an anonymous guest — no stored Google
session/login is used. If Meet redirects to accounts.google.com, that means
the meeting requires a signed-in account and we fail fast rather than
attempting an automated login.

Flow
----
meeting_joiner.py -> join_meeting(meeting_url, platform, bot_name)
    -> launch_browser()
    -> page.goto(meeting_url)
    -> platform-specific join steps
    -> return (success: bool, browser: Browser | None, page: Page | None)
"""

from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Playwright

try:
    from pyvirtualdisplay import Display
except ImportError:
    Display = None

from app.services import recorder
from app.utils.logger import get_logger

logger = get_logger(__name__)

from typing import Any

# Tracks the Playwright driver instance behind each Browser so leave_meeting()
# can stop it (browser.close() alone does not stop the driver subprocess).
_active_playwrights: dict[int, Playwright] = {}

# Tracks the virtual (Xvfb) display behind each Browser so leave_meeting() can
# stop it. We run headed-under-Xvfb rather than headless because Google's
# properties actively fingerprint headless Chromium and gate anonymous guest
# access behind a sign-in wall when they detect it.
_active_displays: dict[int, Any] = {}

# Reused selectors
_IN_CALL_SELECTOR = '[aria-label*="Leave call" i], [aria-label*="Leave" i], [aria-label*="hang up" i], button[jsname="CQeAdf"], button[jsname="CQylEf"]'
_DENIED_TEXT_SELECTOR = 'text=/denied your request|can.?t join this call|removed you from the call|no longer available/i'
_INVALID_MEETING_SELECTOR = 'text=/check your meeting code|misspelled or the meeting has ended|invalid meeting/i'


async def launch_browser() -> tuple[Browser, BrowserContext, Page]:
    import sys
    import os
    import base64

    display = None
    if sys.platform != "win32":
        try:
            display = Display(visible=0, size=(1280, 720))
            display.start()
        except Exception as ex:
            logger.warning("Xvfb display not running (continuing without virtual display): %s", ex)

    playwright = await async_playwright().start()
    browser = None
    try:
        launch_kwargs = dict(
            headless=False,
            args=[
                # Accepts mic/camera permission prompts silently (does NOT fake the actual device)
                "--use-fake-ui-for-media-stream",
                # Allow media autoplay without user gesture (needed for Google Meet audio)
                "--autoplay-policy=no-user-gesture-required",
                "--no-user-gesture-required",
                # Anti-bot evasion
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-features=WebRtcHideLocalIpsWithMdns",
            ],
        )
        try:
            browser = await playwright.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception:
            browser = await playwright.chromium.launch(**launch_kwargs)

        # Cross-platform location for google_session.json
        session_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "google_session.json"))

        # Decode session from env var if present
        session_b64 = os.environ.get("GOOGLE_SESSION_B64")
        if session_b64:
            try:
                with open(session_file, "wb") as f:
                    f.write(base64.b64decode(session_b64))
                logger.info("Decoded Google Session from GOOGLE_SESSION_B64 env var.")
            except Exception:
                logger.exception("Failed to decode GOOGLE_SESSION_B64.")

        if os.path.exists(session_file):
            logger.info("Starting browser with authenticated bot session (%s).", session_file)
            context = await browser.new_context(
                storage_state=session_file,
                permissions=["camera", "microphone"],
                viewport={"width": 1280, "height": 720},
                locale="en-US",
            )
        else:
            logger.info("Starting browser in anonymous guest mode (no google_session.json found).")
            context = await browser.new_context(
                permissions=["camera", "microphone"],
                viewport={"width": 1280, "height": 720},
                locale="en-US",
            )

        # Mask webdriver flag & inject pre-load WebAudio AudioNode interceptor
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        await context.add_init_script(recorder._INIT_WEBAUDIO_CAPTURE_JS)
        page = await context.new_page()

        # Apply playwright-stealth if available
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            pass

        _active_playwrights[id(browser)] = playwright
        if display:
            _active_displays[id(browser)] = display
        return browser, context, page

    except Exception:
        if browser is not None:
            await browser.close()
        await playwright.stop()
        if display:
            display.stop()
        raise


async def _wait_for_join_outcome(page: Page, timeout_ms: int = 900_000) -> str:
    """
    Polls the page after clicking Join. Returns one of:
    'joined', 'denied', 'timeout'
    """
    poll_interval = 2000
    elapsed = 0
    while elapsed < timeout_ms:
        try:
            if await page.locator(_IN_CALL_SELECTOR).first.is_visible():
                return "joined"
        except Exception:
            pass
        try:
            if await page.locator(_DENIED_TEXT_SELECTOR).first.is_visible():
                return "denied"
        except Exception:
            pass
        await page.wait_for_timeout(poll_interval)
        elapsed += poll_interval
    return "timeout"


async def _join_google_meet(page: Page, meeting_url: str, bot_name: str) -> bool:
    try:
        logger.info("Navigating to Google Meet: %s", meeting_url)
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)

        # --- Step 0: Fail fast on states we can't recover from as a guest ---
        if "accounts.google.com" in page.url:
            import os
            if os.environ.get("GOOGLE_SESSION_B64"):
                logger.error(
                    "Meet redirected to Google sign-in for %s. A session file was loaded, "
                    "but it appears to be expired. Please re-run scripts/generate_google_session.py.", meeting_url
                )
            else:
                logger.error(
                    "Meet redirected to Google sign-in for %s. This meeting requires "
                    "a signed-in account, and no session was provided — cannot join anonymously.", meeting_url
                )
            return False

        invalid = page.locator(_INVALID_MEETING_SELECTOR)
        if await invalid.count() > 0 and await invalid.first.is_visible():
            logger.error("Meet reports an invalid/expired meeting code for %s", meeting_url)
            return False

        # --- Step 1: Dismiss permission/cookie popups ---
        for popup_text in ["Got it", "Dismiss", "Continue without", "Close", "Allow"]:
            try:
                pop = page.locator(f'button:has-text("{popup_text}")')
                if await pop.count() > 0 and await pop.first.is_visible():
                    await pop.first.click(force=True, timeout=2000)
            except Exception:
                pass

        # --- Step 2.5: Ensure Mic and Camera are muted before joining ---
        logger.info("Ensuring microphone and camera are muted before joining...")

        for device in ["microphone", "camera"]:
            try:
                off_btn = page.locator(
                    f'button[aria-label*="Turn off {device}" i], '
                    f'div[role="button"][aria-label*="Turn off {device}" i], '
                    f'button[data-tooltip*="Turn off {device}" i]'
                ).first

                if await off_btn.count() > 0 and await off_btn.is_visible():
                    logger.info("%s is currently ON — clicking to turn OFF...", device.capitalize())
                    await off_btn.click(timeout=2000)
                    await page.wait_for_timeout(300)
                else:
                    logger.info("%s is ALREADY OFF (no turn-off button detected).", device.capitalize())
            except Exception as ex:
                logger.warning("Could not check %s mute state: %s", device, ex)

        # --- Step 2: Fill guest name if prompted (unlocks the Join button) ---
        await page.wait_for_timeout(2000)
        try:
            name_input = page.locator(
                'input[placeholder*="name" i], input[aria-label*="name" i]'
            )
            if await name_input.count() > 0 and await name_input.first.is_visible():
                logger.info("Filling guest name: %s", bot_name)
                await name_input.first.fill(bot_name)
                await name_input.first.press("Tab")
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        # --- Step 3: Wait for "Ask to join" / "Join now", with a real fallback ---
        logger.info("Waiting up to 90s for the Join button to appear...")
        join_btn = page.locator(
            'button:has-text("Ask to join"):visible, '
            '[role="button"]:has-text("Ask to join"):visible, '
            'button:has-text("Join now"):visible, '
            '[role="button"]:has-text("Join now"):visible'
        )

        try:
            await join_btn.first.wait_for(state="visible", timeout=90_000)
            logger.info("Visible Join button found.")
        except Exception:
            logger.warning("Primary join-button selector timed out — scanning all visible buttons.")
            all_buttons = page.locator('button:visible, [role="button"]:visible')
            count = await all_buttons.count()
            found = None
            for i in range(count):
                btn = all_buttons.nth(i)
                txt = ((await btn.inner_text()) or "").strip().lower()
                if "join" in txt or "ask to" in txt:
                    found = btn
                    break
            if found is None:
                texts = []
                for i in range(count):
                    t = ((await all_buttons.nth(i).inner_text()) or "").strip()
                    if t:
                        texts.append(t)
                logger.error("No join button found. Visible buttons were: %s", texts)
                logger.error("PAGE URL at failure: %s", page.url)
                logger.error("PAGE TITLE at failure: %s", await page.title())
                try:
                    body_text = await page.locator("body").inner_text()
                    logger.error("PAGE BODY TEXT (first 500 chars): %s", body_text[:500].replace("\n", " | "))
                except Exception:
                    pass
                try:
                    await page.screenshot(path="/tmp/meet_join_failure.png")
                    logger.error("Saved failure screenshot to /tmp/meet_join_failure.png")
                except Exception:
                    pass
                return False
            join_btn = found

        # --- Step 4: Click the Join button ---
        clicked = False
        try:
            box = await join_btn.first.bounding_box()
            if box:
                x = box["x"] + box["width"] / 2
                y = box["y"] + box["height"] / 2
                logger.info("Clicking join button at (%.0f, %.0f)...", x, y)
                await page.mouse.move(x, y)
                await page.wait_for_timeout(200)
                await page.mouse.click(x, y)
                clicked = True
            else:
                logger.warning("bounding_box() returned None, falling back to force click.")
                await join_btn.first.click(force=True, timeout=5000)
                clicked = True
        except Exception as ex:
            logger.error("Failed to click Join button: %s", ex)

        if not clicked:
            logger.error("Could not click any Join button.")
            return False

        # --- Step 5: Wait to actually enter the call (or get denied) ---
        logger.info("Join clicked. Waiting up to 15m for host admission or auto-entry...")
        outcome = await _wait_for_join_outcome(page, timeout_ms=900_000)
        if outcome == "joined":
            logger.info("Successfully joined Google Meet!")
            return True
        elif outcome == "denied":
            logger.error("Host denied entry (or removed the bot) for %s", meeting_url)
            return False
        else:
            logger.error("Timed out waiting to enter the call for %s", meeting_url)
            return False

    except Exception as e:
        logger.exception("Failed to join Google Meet at %s: %s", meeting_url, e)
        try:
            logger.error("PAGE URL: %s", page.url)
            logger.error("PAGE TITLE: %s", await page.title())
            buttons = page.locator("button, a, [role='button']")
            count = await buttons.count()
            ui_texts = []
            for i in range(count):
                txt = (await buttons.nth(i).inner_text() or "").strip()
                aria = await buttons.nth(i).get_attribute("aria-label")
                if txt or aria:
                    ui_texts.append(f"Text='{txt}' Aria='{aria}'")
            logger.error("BUTTONS ON SCREEN: %s", ui_texts)
        except Exception:
            pass
        return False


async def _join_zoom(page: Page, meeting_url: str, bot_name: str) -> bool:
    try:
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=30_000)
        frame = page
        for f in page.frames:
            if "zoom" in f.url:
                frame = f
                break
        name_input = frame.locator('input#inputname, input[name="uname"]')
        if await name_input.count() > 0:
            await name_input.first.fill(bot_name)
        join_btn = frame.locator('button:has-text("Join"), #joinBtn')
        await join_btn.first.click(timeout=20_000)
        await page.locator('button[aria-label*="leave" i]').first.wait_for(timeout=60_000)
        return True
    except Exception:
        logger.exception("Failed to join Zoom meeting at %s", meeting_url)
        return False


async def _join_teams(page: Page, meeting_url: str, bot_name: str) -> bool:
    try:
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=30_000)
        cont = page.locator('a:has-text("Continue on this browser"), button:has-text("Continue on this browser")')
        if await cont.count() > 0:
            await cont.first.click(timeout=5000)
        name_input = page.locator('input[data-tid="prejoin-display-name-input"]')
        if await name_input.count() > 0:
            await name_input.first.fill(bot_name)
        join_btn = page.locator('button[data-tid="prejoin-join-button"]')
        await join_btn.first.click(timeout=20_000)
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


async def join_meeting(
    meeting_url: str, platform: str, bot_name: str
) -> tuple[bool, Browser | None, Page | None]:
    handler = _PLATFORM_HANDLERS.get(platform)
    if handler is None:
        logger.error("Unsupported platform '%s' for url %s", platform, meeting_url)
        return False, None, None

    browser, context, page = await launch_browser()
    success = await handler(page, meeting_url, bot_name)

    if not success:
        await context.close()
        await leave_meeting(browser)
        return False, None, None

    return True, browser, page


async def leave_meeting(browser: Browser | None) -> None:
    if browser is None:
        return
    playwright = _active_playwrights.pop(id(browser), None)
    display = _active_displays.pop(id(browser), None)
    try:
        await browser.close()
    finally:
        if playwright is not None:
            await playwright.stop()
        if display is not None:
            display.stop()


async def ensure_muted(page: Page | None) -> None:
    """Checks in-meeting controls and turns off microphone and camera if they are on."""
    if not page or page.is_closed():
        return
    try:
        for device in ["microphone", "camera"]:
            off_btn = page.locator(
                f'button[aria-label*="Turn off {device}" i], '
                f'button[data-tooltip*="Turn off {device}" i]'
            ).first
            if await off_btn.count() > 0 and await off_btn.is_visible():
                logger.info("In-call %s detected as ON — muting immediately...", device.capitalize())
                await off_btn.click(timeout=1000)
    except Exception:
        pass


async def is_meeting_active(page: Page | None, platform: str) -> bool:
    if not page or page.is_closed():
        return False
    try:
        if platform == "google_meet":
            url = (page.url or "").lower()
            if "landing" in url or (url.startswith("https://meet.google.com") and len(url.rstrip("/").split("/")) <= 3):
                return False

            import time
            if not hasattr(page, "_joined_timestamp"):
                setattr(page, "_joined_timestamp", time.time())

            elapsed_since_join = time.time() - getattr(page, "_joined_timestamp", time.time())

            try:
                ended = await page.evaluate('''() => {
                    try {
                        let text = document.body ? document.body.innerText.toLowerCase() : "";
                        if (text.includes("return to home screen") || 
                            text.includes("ended this meeting") || 
                            text.includes("ended the call") ||
                            text.includes("has ended") ||
                            text.includes("call ended") ||
                            text.includes("you left the meeting") || 
                            text.includes("you've left") ||
                            text.includes("someone removed you") ||
                            text.includes("you've been removed") ||
                            text.includes("everyone else has left") ||
                            text.includes("no one else is in this call") ||
                            text.includes("no one else is here") ||
                            text.includes("you're the only one here") ||
                            text.includes("only one here")) {
                            return true;
                        }
                        return false;
                    } catch(e) {
                        return false;
                    }
                }''')
                if ended:
                    logger.info("Host ended call or left meeting. Exiting bot.")
                    return False

                # After 15 seconds of call stabilization, check if bot is left alone
                if elapsed_since_join > 15:
                    is_alone = await page.evaluate('''() => {
                        try {
                            let nodes = document.querySelectorAll('[data-participant-id], [data-requested-participant-id]');
                            let ids = new Set([...nodes].map(el => el.getAttribute('data-participant-id') || el.getAttribute('data-requested-participant-id')).filter(Boolean));
                            return ids.size === 1;
                        } catch(e) {
                            return false;
                        }
                    }''')
                    if is_alone:
                        logger.info("Host/participants left meeting (bot is alone). Exiting bot.")
                        return False
            except Exception:
                pass
            return True
        elif platform == "teams":
            return await page.locator('[data-tid="hangup-leave-button"]').count() > 0
    except Exception:
        pass
    return False


async def connect_bot_session() -> str:
    """Launches headed Chrome for user to sign into Google, automatically detects login,
    saves storage_state to google_session.json, and closes browser without terminal prompt."""
    import os
    import base64
    import asyncio
    from playwright.async_api import async_playwright

    session_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "google_session.json"))

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
        except Exception:
            try:
                browser = await p.chromium.launch(headless=False, channel="msedge", args=["--disable-blink-features=AutomationControlled"])
            except Exception:
                browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])

        context = await browser.new_context(viewport={"width": 1280, "height": 720}, locale="en-US")
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        page = await context.new_page()

        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            pass

        logger.info("Opening headed Chrome for bot Google sign-in...")
        await page.goto("https://accounts.google.com/signin")

        # Poll up to 180 seconds until sign in finishes or window closes
        for _ in range(180):
            await asyncio.sleep(1)
            if page.is_closed():
                break
            try:
                cookies = await context.cookies()
                cookie_names = [c.get("name", "") for c in cookies]
                if any(k in cookie_names for k in ["SID", "HSID", "SSID"]) and ("myaccount.google.com" in page.url or "google.com" in page.url):
                    logger.info("Detected successful Google sign-in!")
                    await asyncio.sleep(1.5)
                    break
            except Exception:
                pass

        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        await context.storage_state(path=session_file)

        if not page.is_closed():
            await page.close()
        await browser.close()

        try:
            with open(session_file, "rb") as f:
                os.environ["GOOGLE_SESSION_B64"] = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass

        logger.info("Saved Google session to %s", session_file)
        return session_file