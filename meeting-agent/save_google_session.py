"""
save_google_session.py
======================
Run this ONCE on your local machine (not in Docker) to sign in to
Google manually and save the session cookies for the Meeting Agent bot.

Can be triggered from the dashboard's "Connect Bot Account" button
or run manually: python save_google_session.py

How it works:
  1. Launches a visible Playwright Chromium browser
  2. You sign in to your Google account manually
  3. After sign-in, press ENTER in the terminal
  4. The script saves the browser cookies as google_session.json
  5. The Docker container mounts this file for Google Meet access
"""

import asyncio
import sys
import os

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_session.json")


async def run_session_saver():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright is not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    print("=" * 55)
    print("  Google Session Saver for Meeting Agent Bot")
    print("=" * 55)
    print()
    print("📌 A browser window will open now.")
    print("   1. Sign in to your Google account")
    print("   2. Make sure you see your profile picture in the top-right")
    print("   3. Come back here and press ENTER")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        page = await context.new_page()
        await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")

        # Wait for user to sign in manually via the frontend UI signal
        print("\n   Waiting for the user to click 'Finish Sign In' on the dashboard...")
        lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_signin_done.txt")
        # Ensure it's clear before we start
        if os.path.exists(lock_file):
            os.remove(lock_file)
            
        while not os.path.exists(lock_file):
            # If the user closed the browser prematurely, gracefully exit
            if not browser.is_connected():
                print("❌ Browser was closed before sign-in was completed.")
                return
            await asyncio.sleep(1)

        # Proceed to save cookies and clean up lock
        try:
            os.remove(lock_file)
        except Exception:
            pass

        # Navigate to Google to refresh cookies
        await page.goto("https://myaccount.google.com/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)

        # Save the storage state (cookies + localStorage)
        await context.storage_state(path=SESSION_FILE)
        await browser.close()

    print(f"\n✅ Session saved to: {SESSION_FILE}")
    print("   The meeting bot will now join Google Meet as your signed-in account!")
    print("   Rebuild Docker: docker compose up --build -d")


def main():
    asyncio.run(run_session_saver())


if __name__ == "__main__":
    main()
