import asyncio
import json
from typing import Optional
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright, Page, Browser, Playwright

# Initialize FastMCP server
mcp = FastMCP("browser_automation")

class BrowserSession:
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def start(self, headless: bool = True):
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        if self.browser is None:
            self.browser = await self.playwright.chromium.launch(headless=headless)
        if self.page is None:
            self.page = await self.browser.new_page()
        return "Browser started."

    async def stop(self):
        if self.page:
            await self.page.close()
            self.page = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        return "Browser stopped."

    async def goto(self, url: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        await self.page.goto(url)
        return f"Navigated to {url}"

    async def click(self, selector: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        await self.page.click(selector)
        return f"Clicked on {selector}"

    async def fill(self, selector: str, value: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        await self.page.fill(selector, value)
        return f"Filled {selector} with '{value}'"

    async def get_text(self, selector: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        text = await self.page.inner_text(selector)
        return text

    async def screenshot(self, path: str = "screenshot.png"):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        await self.page.screenshot(path=path)
        return f"Screenshot saved to {path}"

    async def evaluate_js(self, expression: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        result = await self.page.evaluate(expression)
        return json.dumps(result)

    async def wait_for_selector(self, selector: str, timeout: int = 10000):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        await self.page.wait_for_selector(selector, timeout=timeout)
        return f"Selector {selector} appeared."

# Global browser session
session = BrowserSession()

@mcp.tool()
async def start_browser(headless: bool = True) -> str:
    """Start a browser session"""
    try:
        return await session.start(headless=headless)
    except Exception as e:
        return f"Error starting browser: {str(e)}"

@mcp.tool()
async def stop_browser() -> str:
    """Stop the browser session"""
    try:
        return await session.stop()
    except Exception as e:
        return f"Error stopping browser: {str(e)}"

@mcp.tool()
async def navigate_to(url: str) -> str:
    """Navigate to a URL"""
    try:
        return await session.goto(url)
    except Exception as e:
        return f"Error navigating to {url}: {str(e)}"

@mcp.tool()
async def click_element(selector: str) -> str:
    """Click on an element using CSS selector"""
    try:
        return await session.click(selector)
    except Exception as e:
        return f"Error clicking {selector}: {str(e)}"

@mcp.tool()
async def fill_form(selector: str, value: str) -> str:
    """Fill a form field with a value"""
    try:
        return await session.fill(selector, value)
    except Exception as e:
        return f"Error filling {selector}: {str(e)}"

@mcp.tool()
async def extract_text(selector: str) -> str:
    """Extract text from an element"""
    try:
        return await session.get_text(selector)
    except Exception as e:
        return f"Error extracting text from {selector}: {str(e)}"

@mcp.tool()
async def take_screenshot(path: str = "screenshot.png") -> str:
    """Take a screenshot of the current page"""
    try:
        return await session.screenshot(path)
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"

@mcp.tool()
async def evaluate_javascript(expression: str) -> str:
    """Execute JavaScript in the browser"""
    try:
        return await session.evaluate_js(expression)
    except Exception as e:
        return f"Error evaluating JavaScript: {str(e)}"

@mcp.tool()
async def wait_for_element(selector: str, timeout: int = 10000) -> str:
    """Wait for an element to appear on the page"""
    try:
        return await session.wait_for_selector(selector, timeout)
    except Exception as e:
        return f"Error waiting for {selector}: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")