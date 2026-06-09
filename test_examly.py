import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled"
        ])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Capture console logs
        page.on("console", lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))
        
        print("Navigating to Examly...")
        response = await page.goto("https://mbu931.examly.io/login", wait_until="networkidle", timeout=30000)
        print(f"Status: {response.status if response else 'None'}")
        
        # Wait a bit
        await asyncio.sleep(5)
        
        content = await page.content()
        print(f"HTML length: {len(content)}")
        if len(content) < 2000:
            print("HTML Content:", content)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
