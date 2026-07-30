import uvicorn
import sys
import asyncio

if sys.platform == "win32":
    # Uvicorn explicitly forces WindowsSelectorEventLoopPolicy on Windows, which breaks Playwright.
    # We monkey-patch Uvicorn to use WindowsProactorEventLoopPolicy instead.
    import uvicorn.loops.asyncio
    uvicorn.loops.asyncio.asyncio_setup = lambda *args, **kwargs: asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    print("Starting Meeting Agent server with Windows Proactor Event Loop...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
