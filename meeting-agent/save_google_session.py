"""
save_google_session.py
======================
Run this ONCE on your local machine (not in Docker) to sign in to
Google manually and save the session cookies.

How it works:
  1. Opens a REAL Chrome window (no Playwright automation flags at all)
  2. You sign in to your bot Gmail account manually
  3. You close Chrome and press ENTER
  4. The script opens that same Chrome profile via Playwright to export cookies
  5. Saves google_auth.json for the Docker container to use

Usage:
    python save_google_session.py
"""

import asyncio
import os
import subprocess
import sys

SESSION_FILE = "google_auth.json"

# Chrome locations to try on Windows
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

# We use a SEPARATE, clean profile dir so we don't touch your personal Chrome
BOT_PROFILE_DIR = os.path.abspath("chrome_bot_profile")


def find_chrome():
    for path in CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None


def open_chrome_for_signin():
    chrome = find_chrome()
    if not chrome:
        print("❌ Chrome not found. Please install Google Chrome and try again.")
        sys.exit(1)

    print(f"\n✅ Found Chrome at: {chrome}")
    print(f"   Using a clean bot profile at: {BOT_PROFILE_DIR}")
    print("\n👉 A Chrome window is opening...")
    print("   Sign in to your bot Gmail account (agentos.meetbot@gmail.com)")
    print("   Complete any verification Google asks for.")
    print("   ⚠️  Do NOT close Chrome — come back here when signed in.\n")

    # Launch Chrome with a dedicated profile dir, NO automation flags
    proc = subprocess.Popen([
        chrome,
        f"--user-data-dir={BOT_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://accounts.google.com/signin",
    ])
    return proc


async def export_session():
    from playwright.async_api import async_playwright

    print("\n📦 Exporting session cookies from bot Chrome profile...")

    async with async_playwright() as p:
        # Open the bot profile non-headless so we can check it's signed in
        context = await p.chromium.launch_persistent_context(
            user_data_dir=BOT_PROFILE_DIR,
            channel="chrome",
            headless=True,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        # Navigate to Google to ensure cookies are fresh
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://myaccount.google.com/", wait_until="domcontentloaded", timeout=15000)

        await context.storage_state(path=SESSION_FILE)
        await context.close()

    print(f"\n✅ Session saved to '{SESSION_FILE}'")
    print("   Now rebuild Docker:")
    print("   docker compose up --build -d")


def main():
    print("=" * 55)
    print("  Google Session Saver for Meeting Agent Bot")
    print("=" * 55)

    proc = open_chrome_for_signin()
    input("   Press ENTER here once you are fully signed in to Google...\n")

    # Kill Chrome so Playwright can open the same profile
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

    print("   Chrome closed. Extracting session...")
    asyncio.run(export_session())


if __name__ == "__main__":
    main()
