"""
app/services/browser.py

Purpose
-------
Uses Playwright to launch a headless Chromium instance, navigate to a
meeting URL, and click through the join flow for Google Meet, Zoom, or Teams.

Flow
----
meeting_joiner.py -> join_meeting(meeting_url, platform, bot_name)
    -> launch_browser()
    -> page.goto(meeting_url)
    -> platform-specific join steps
    -> return (success: bool, browser: Browser | None, page: Page | None)
"""

import os

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_SESSION_FILE = "/app/google_session.json"


async def launch_browser() -> tuple[Browser, BrowserContext, Page]:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--use-fake-ui-for-media-stream",   # auto-grant mic/camera without dialog
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-features=WebRtcHideLocalIpsWithMdns",
            "--use-gl=swiftshader",
        ],
    )

    common_ctx = dict(
        permissions=["camera", "microphone"],
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 720},
        locale="en-US",
    )

    # Decode session from env var (always refresh — don't rely on stale disk files)
    session_b64 = os.environ.get("GOOGLE_SESSION_B64")
    if session_b64:
        import base64
        try:
            with open(_SESSION_FILE, "wb") as f:
                f.write(base64.b64decode(session_b64))
            logger.info("Decoded Google Session from GOOGLE_SESSION_B64 env var.")
        except Exception:
            logger.exception("Failed to decode GOOGLE_SESSION_B64.")
    else:
        # No session env var → delete any stale file so we always run in guest mode
        if os.path.exists(_SESSION_FILE):
            try:
                os.remove(_SESSION_FILE)
                logger.info("Removed stale google_session.json — running as Anonymous Guest.")
            except Exception:
                pass

    if os.path.exists(_SESSION_FILE):
        logger.info("Loading saved Google session from %s", _SESSION_FILE)
        context = await browser.new_context(storage_state=_SESSION_FILE, **common_ctx)
    else:
        logger.info("Running in Anonymous Guest Mode.")
        context = await browser.new_context(**common_ctx)

    # Mask webdriver flag
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )

    page = await context.new_page()

    # Apply playwright-stealth if available
    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except ImportError:
        pass

    return browser, context, page


async def _join_google_meet(page: Page, meeting_url: str, bot_name: str) -> bool:
    try:
        logger.info("Navigating to Google Meet: %s", meeting_url)
        await page.goto(meeting_url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)

        # --- Step 0: Handle Google security interception (account chooser) ---
        if "accounts.google.com" in page.url:
            logger.warning("Google security intercepted the URL. Attempting to bypass account chooser...")
            acct_btn = page.locator('div[data-email], li[data-identifier], div[data-identifier]')
            try:
                if await acct_btn.count() > 0:
                    await acct_btn.first.click(force=True, timeout=5000)
                    await page.wait_for_timeout(2000)
                    # Handle re-auth password prompt
                    pwd_input = page.locator('input[type="password"]')
                    try:
                        await pwd_input.first.wait_for(state="visible", timeout=5000)
                        if settings.GOOGLE_BOT_PASSWORD:
                            await pwd_input.first.fill(settings.GOOGLE_BOT_PASSWORD)
                            await page.keyboard.press("Enter")
                        else:
                            logger.error("Google requires password but GOOGLE_BOT_PASSWORD is not set!")
                    except Exception:
                        pass  # No password prompt, that's fine
                    # Wait to land back on meet.google.com
                    await page.wait_for_url(
                        lambda url: url.startswith("https://meet.google.com/"),
                        timeout=20_000
                    )
                    await page.wait_for_timeout(3000)
            except Exception as ex:
                logger.warning("Could not bypass account chooser: %s", ex)

        # --- Step 1: Dismiss permission/cookie popups ---
        for popup_text in ["Got it", "Dismiss", "Continue without", "Close", "Allow"]:
            try:
                pop = page.locator(f'button:has-text("{popup_text}")')
                if await pop.count() > 0 and await pop.first.is_visible():
                    await pop.first.click(force=True, timeout=2000)
            except Exception:
                pass

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

        # --- Step 3: Wait up to 90s for "Ask to join" / "Join now" to appear ---
        logger.info("Waiting up to 90s for the Join button to appear...")
        try:
            await page.wait_for_function(
                """() => {
                    const els = document.querySelectorAll('button, [role="button"]');
                    return Array.from(els).some(el => {
                        const t = (el.innerText || '').trim().toLowerCase();
                        return t === 'ask to join' || t === 'join now';
                    });
                }""",
                timeout=90_000,
            )
            logger.info("Join button is visible in DOM.")
        except Exception:
            logger.warning("Timed out waiting for join button — attempting click anyway.")

        # --- Step 4: Click the Join button via JS bounding rect + real mouse ---
        result = await page.evaluate("""() => {
            const els = document.querySelectorAll('button, [role="button"], span');
            for (const el of els) {
                const t = (el.innerText || '').trim().toLowerCase();
                if (t === 'ask to join' || t === 'join now') {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        el.scrollIntoView({ block: 'center' });
                        return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, text: el.innerText.trim() };
                    }
                }
            }
            return null;
        }""")

        logger.info("Join button bounding rect: %s", result)

        clicked = False
        if result and result.get("w", 0) > 0 and result.get("h", 0) > 0:
            x, y = result["x"], result["y"]
            logger.info("Clicking '%s' at (%.0f, %.0f) via real mouse...", result["text"], x, y)
            await page.mouse.move(x, y)
            await page.wait_for_timeout(200)
            await page.mouse.click(x, y)
            clicked = True
        elif result:
            # Button found but 0-size (likely off-viewport). Scroll and try Playwright force click.
            logger.warning("Join button has 0 bounding rect — trying force click.")
            try:
                await page.locator('[role="button"]:has-text("Ask to join")').first.click(force=True, timeout=10_000)
                clicked = True
            except Exception:
                try:
                    await page.locator('[role="button"]:has-text("Join now")').first.click(force=True, timeout=10_000)
                    clicked = True
                except Exception as ex:
                    logger.error("Force click failed: %s", ex)

        if not clicked:
            logger.error("Could not click any Join button. Raising to trigger forensic dump.")
            raise RuntimeError("No clickable Join button found on screen.")

        # --- Step 5: Wait to actually enter the call (or waiting room) ---
        # This waits up to 15 minutes so the host has time to admit the bot.
        logger.info("Join clicked. Waiting up to 15m for host admission or auto-entry...")
        leave_selector = '[aria-label*="Leave call" i], [aria-label*="Leave" i], button[jsname="CQeAdf"]'
        await page.locator(leave_selector).first.wait_for(timeout=900_000)
        logger.info("Successfully joined Google Meet!")
        return True

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
        await browser.close()
        return False, None, None

    return True, browser, page


async def leave_meeting(browser: Browser | None) -> None:
    if browser is not None:
        await browser.close()


async def is_meeting_active(page: Page | None, platform: str) -> bool:
    if not page or page.is_closed():
        return False
    try:
        if platform == "google_meet":
            return await page.locator('[aria-label*="Leave call" i]').count() > 0
        elif platform == "zoom":
            return await page.locator('button[aria-label*="leave" i]').count() > 0
        elif platform == "teams":
            return await page.locator('[data-tid="hangup-leave-button"]').count() > 0
    except Exception:
        pass
    return False
