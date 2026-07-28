import asyncio
import os
import base64
from playwright.async_api import async_playwright

async def run():
    print("================================================================")
    print("Google Meet Bot Authentication Session Generator")
    print("================================================================\n")
    print("This script will open a real, visible Chromium browser window.")
    print("Please log in to the dedicated bot Gmail account.")
    print("If it asks for 2FA, phone verification, or anything else, complete it.")
    print("Once you are fully logged in and looking at the Google Accounts dashboard,")
    print("return to this terminal and press ENTER to save the session.")
    print("----------------------------------------------------------------\n")
    
        # Attempt to use the user's real Chrome/Edge browser to completely bypass Google's bot detection
        try:
            print("Attempting to launch native Google Chrome...")
            browser = await p.chromium.launch(headless=False, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
        except Exception:
            try:
                print("Chrome not found. Attempting to launch native Microsoft Edge...")
                browser = await p.chromium.launch(headless=False, channel="msedge", args=["--disable-blink-features=AutomationControlled"])
            except Exception:
                print("Native browsers not found. Falling back to Playwright Chromium...")
                browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        
        # Omit hardcoded user-agents, as outdated UAs trigger "This browser is not secure"
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        
        page = await context.new_page()
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            pass

        # Go straight to Google Sign-in
        await page.goto("https://accounts.google.com/signin")
        
        # Wait for the user in the terminal
        input("\n[WAITING] Press ENTER here in the terminal ONLY when you have fully logged in... ")
        print("\nSaving session to google_session.json...")
        
        # Ensure the directory exists if run from a different CWD
        os.makedirs(os.path.dirname(os.path.abspath(__file__)) + "/../", exist_ok=True)
        session_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "google_session.json"))
        
        # Save the storage state (cookies, local storage)
        await context.storage_state(path=session_file)
        await browser.close()
        
        if not os.path.exists(session_file):
            print("ERROR: Failed to save the session file!")
            return
            
        # Generate the Base64 version for environmental injection
        with open(session_file, "rb") as f:
            b64_session = base64.b64encode(f.read()).decode("utf-8")
            
        print("\n================================================================")
        print("SUCCESS! SESSION SAVED.")
        print("================================================================\n")
        print("1. A local copy was saved to:")
        print(f"   {session_file}\n")
        print("2. For production (Render, Docker, etc), set this exact environment variable:")
        print("\nGOOGLE_SESSION_B64=" + b64_session)
        print("\n================================================================")
        print("Copy the base64 string above and add it to your .env or Render dashboard.")
        print("Do NOT commit the base64 string or the json file to version control!")

if __name__ == "__main__":
    asyncio.run(run())
