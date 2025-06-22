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
            # Add more browser options for better compatibility
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
        if self.page is None:
            self.page = await self.browser.new_page()
            
            # Set a realistic user agent
            await self.page.set_extra_http_headers({
                "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # Enhanced selector function with better visibility detection
            await self.page.add_init_script("""
                window.MCPGetSelector = function(el) {
                    // Try ID first (most reliable)
                    if (el.id && el.id.trim()) return "#" + CSS.escape(el.id);
                    
                    // Try data attributes for modern web apps
                    if (el.dataset && Object.keys(el.dataset).length > 0) {
                        const firstKey = Object.keys(el.dataset)[0];
                        const value = el.dataset[firstKey];
                        if (value && value.trim()) {
                            const attrName = firstKey.replace(/([A-Z])/g, '-$1').toLowerCase();
                            return `[data-${attrName}="${CSS.escape(value)}"]`;
                        }
                    }
                    
                    // Try meaningful class names (avoid utility classes)
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.trim().split(/\\s+/);
                        const meaningfulClasses = classes.filter(c => 
                            c.length > 2 && 
                            !c.match(/^(d-|p-|m-|text-|bg-|border-|flex-|position-|w-|h-|col-|row-|btn-|nav-)/));
                        
                        if (meaningfulClasses.length > 0) {
                            // Use the most specific class (often the longest meaningful one)
                            const bestClass = meaningfulClasses.sort((a, b) => b.length - a.length)[0];
                            return "." + CSS.escape(bestClass);
                        } else if (classes.length > 0) {
                            return "." + CSS.escape(classes[0]);
                        }
                    }
                    
                    // Try name attribute
                    if (el.name && el.name.trim()) return `[name="${CSS.escape(el.name)}"]`;
                    
                    // Try type for inputs
                    if (el.tagName === 'INPUT' && el.type) {
                        return `input[type="${el.type}"]`;
                    }
                    
                    // Try href for links (truncate long URLs and escape properly)
                    if (el.tagName === 'A') {
                        const href = el.getAttribute('href');
                        if (href && href.trim() && href.length < 100) {
                            return `a[href="${CSS.escape(href)}"]`;
                        }
                    }
                    
                    // Try text content for buttons and links (if short and unique)
                    const textContent = el.textContent?.trim();
                    if (textContent && textContent.length < 30 && textContent.length > 0) {
                        // Use :has-text() selector for better compatibility
                        const escapedText = textContent.replace(/"/g, '\\\\"');
                        return `${el.tagName.toLowerCase()}:has-text("${escapedText}")`;
                    }
                    
                    // Generate more specific nth-child selector
                    const parent = el.parentElement;
                    if (parent) {
                        const siblings = Array.from(parent.children).filter(
                            sibling => sibling.tagName === el.tagName
                        );
                        if (siblings.length > 1) {
                            const index = siblings.indexOf(el) + 1;
                            // Include parent context for better specificity
                            const parentSelector = parent.id ? `#${CSS.escape(parent.id)}` : 
                                                 parent.className ? `.${CSS.escape(parent.className.split(' ')[0])}` : 
                                                 parent.tagName.toLowerCase();
                            return `${parentSelector} > ${el.tagName.toLowerCase()}:nth-child(${index})`;
                        }
                    }
                    
                    return el.tagName.toLowerCase();
                };
                
                window.MCPIsVisible = function(el) {
                    if (!el || !el.getBoundingClientRect) return false;
                    
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    
                    // Check basic visibility
                    if (rect.width <= 0 || rect.height <= 0) return false;
                    if (style.visibility === 'hidden') return false;
                    if (style.display === 'none') return false;
                    if (style.opacity === '0') return false;
                    
                    // Check if element is in viewport
                    if (rect.bottom < 0 || rect.top > window.innerHeight) return false;
                    if (rect.right < 0 || rect.left > window.innerWidth) return false;
                    
                    // Check if element is not covered by other elements
                    const centerX = rect.left + rect.width / 2;
                    const centerY = rect.top + rect.height / 2;
                    const topElement = document.elementFromPoint(centerX, centerY);
                    
                    // Element is visible if it's the top element or contains the top element
                    return topElement === el || el.contains(topElement) || (topElement && topElement.contains(el));
                };
                
                window.MCPIsClickable = function(el) {
                    if (!window.MCPIsVisible(el)) return false;
                    
                    // Check if element is actually clickable
                    const tagName = el.tagName.toLowerCase();
                    const hasClickHandler = el.onclick || el.onmousedown || el.onmouseup;
                    const hasRole = el.getAttribute('role');
                    const isClickableRole = hasRole && ['button', 'link', 'tab', 'menuitem', 'option'].includes(hasRole);
                    const isClickableTag = ['a', 'button', 'input', 'select', 'textarea'].includes(tagName);
                    const hasClickableClass = el.className && el.className.match(/\\b(btn|button|link|clickable|click)\\b/i);
                    
                    return isClickableTag || hasClickHandler || isClickableRole || hasClickableClass;
                };
            """)
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
        
        try:
            # Navigate with longer timeout and less strict waiting
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # Wait for page to settle
            await self.page.wait_for_timeout(2000)
            
            # Try to wait for network to be idle, but don't fail if it takes too long
            try:
                await self.page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                pass  # Continue even if network doesn't become idle
            
            # Scroll to trigger lazy loading
            await self.page.evaluate("window.scrollTo(0, 100)")
            await self.page.wait_for_timeout(1000)
            await self.page.evaluate("window.scrollTo(0, 0)")
            
            return f"Navigated to {url}"
        except Exception as e:
            return f"Navigation completed with warnings: {str(e)}"

    async def click(self, selector: str):
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        
        try:
            print(f"[DEBUG] Attempting to click selector: {selector}")
            
            # First, try to find the element
            element = await self.page.query_selector(selector)
            if not element:
                print(f"[DEBUG] Element not found with selector: {selector}")
                return f"Element not found: {selector}"
            
            print(f"[DEBUG] Element found, checking if clickable...")
            
            # Check if element is visible and clickable using our custom function
            is_clickable = await self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return { clickable: false, reason: 'Element not found' };
                    
                    const visible = window.MCPIsVisible(el);
                    const clickable = window.MCPIsClickable(el);
                    
                    return { 
                        clickable: clickable, 
                        visible: visible,
                        reason: !visible ? 'Not visible' : !clickable ? 'Not clickable' : 'OK',
                        tagName: el.tagName,
                        text: el.textContent?.trim().substring(0, 50)
                    };
                }
            """, selector)
            
            print(f"[DEBUG] Element check result: {is_clickable}")
            
            if not is_clickable.get('clickable', False):
                # Try to scroll to element first
                print(f"[DEBUG] Element not clickable, trying to scroll to it...")
                await element.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
                
                # Check again
                is_clickable = await self.page.evaluate("""
                    (selector) => {
                        const el = document.querySelector(selector);
                        return el ? window.MCPIsClickable(el) : false;
                    }
                """, selector)
            
            if is_clickable if isinstance(is_clickable, bool) else is_clickable.get('clickable', False):
                # Use force click if necessary
                print(f"[DEBUG] Attempting click...")
                await self.page.click(selector, timeout=10000)
                return f"Clicked on {selector}"
            else:
                reason = is_clickable.get('reason', 'Unknown') if isinstance(is_clickable, dict) else 'Not clickable'
                return f"Element not clickable: {selector} - {reason}"
                
        except Exception as e:
            print(f"[DEBUG] Error during click: {str(e)}")
            # Try force click as last resort
            try:
                print(f"[DEBUG] Attempting force click...")
                await self.page.click(selector, force=True, timeout=5000)
                return f"Force-clicked on {selector} (element might not have been fully visible)"
            except Exception as force_error:
                print(f"[DEBUG] Force click also failed: {str(force_error)}")
                return f"Error clicking {selector}: {str(e)}"

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
        await self.page.screenshot(path=path, full_page=True)
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

    # Enhanced fill function with better error handling and validation
    async def fill_enhanced(self, selector: str, value: str):
        """Enhanced fill function with better validation and error handling"""
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser first.")
        
        try:
            print(f"[DEBUG] Attempting to fill selector: {selector} with value: {value}")
            
            # First, try to find the element
            element = await self.page.query_selector(selector)
            if not element:
                print(f"[DEBUG] Element not found with selector: {selector}")
                return f"Element not found: {selector}"
            
            # Check if element is fillable and get more info
            is_fillable = await self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return { fillable: false, reason: 'Element not found' };
                    
                    const tagName = el.tagName.toLowerCase();
                    const inputType = el.type || 'text';
                    const isContentEditable = el.contentEditable === 'true';
                    const isSelect = tagName === 'select';
                    const isCheckbox = tagName === 'input' && inputType === 'checkbox';
                    const isRadio = tagName === 'input' && inputType === 'radio';
                    
                    // Check if element is visible
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const visible = rect.width > 0 && rect.height > 0 && 
                                   style.visibility !== 'hidden' && 
                                   style.display !== 'none';
                    
                    // Check if element is fillable
                    const fillableTypes = ['text', 'email', 'password', 'search', 'tel', 'url', 
                                         'number', 'date', 'time', 'datetime-local', 'month', 'week'];
                    const isFillable = (tagName === 'input' && fillableTypes.includes(inputType)) ||
                                      tagName === 'textarea' || 
                                      isContentEditable || isSelect || isCheckbox || isRadio;
                    
                    // Check if element is disabled or readonly
                    const disabled = el.disabled || el.readOnly;
                    const maxlength = el.maxLength || null;
                    const placeholder = el.placeholder || null;
                    
                    return {
                        fillable: visible && isFillable && !disabled,
                        visible: visible,
                        disabled: disabled,
                        tagName: tagName,
                        type: inputType,
                        contentEditable: isContentEditable,
                        isSelect,
                        isCheckbox,
                        isRadio,
                        maxlength,
                        placeholder,
                        reason: !visible ? 'Not visible' : 
                               !isFillable ? 'Not fillable element' : 
                               disabled ? 'Disabled or readonly' : 'OK'
                    };
                }
            """, selector)
            
            print(f"[DEBUG] Element check result: {is_fillable}")
            
            if not is_fillable.get('fillable', False):
                # Try to scroll to element first
                print(f"[DEBUG] Element not fillable, trying to scroll to it...")
                await element.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
                
                # Check again
                is_fillable_retry = await self.page.evaluate("""
                    (selector) => {
                        const el = document.querySelector(selector);
                        if (!el) return false;
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 && 
                               style.visibility !== 'hidden' && 
                               style.display !== 'none' &&
                               !el.disabled && !el.readOnly;
                    }
                """, selector)
                
                if not is_fillable_retry:
                    reason = is_fillable.get('reason', 'Unknown')
                    return f"Element not fillable: {selector} - {reason}"
        
            # Warn if value exceeds maxlength
            maxlength = is_fillable.get('maxlength')
            if maxlength and maxlength > 0 and len(value) > maxlength:
                print(f"[DEBUG] Warning: Value length exceeds maxlength ({maxlength}) for {selector}")
            
            # Clear existing content first (if not checkbox/radio/select)
            if not (is_fillable.get('isCheckbox') or is_fillable.get('isRadio') or is_fillable.get('isSelect')):
                await self.page.fill(selector, "")
                await self.page.wait_for_timeout(100)
            
            # Fill with new value
            if is_fillable.get('contentEditable'):
                await self.page.evaluate("""
                    (args) => {
                        const el = document.querySelector(args.selector);
                        if (el) {
                            el.focus();
                            el.textContent = args.value;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                """, {"selector": selector, "value": value})
            elif is_fillable.get('isSelect'):
                await self.page.select_option(selector, value)
            elif is_fillable.get('isCheckbox') or is_fillable.get('isRadio'):
                # For checkbox/radio, set checked state based on value
                checked = value.lower() in ("1", "true", "yes", "on", "checked")
                await self.page.evaluate("""
                    (args) => {
                        const el = document.querySelector(args.selector);
                        if (el) {
                            el.checked = args.checked;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                """, {"selector": selector, "checked": checked})
            else:
                await self.page.fill(selector, value)
            
            # Trigger input and change events to ensure proper form handling
            await self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    if (el) {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('blur', { bubbles: true }));
                    }
                }
            """, selector)
            
            # Verify the value was set (normalize for comparison)
            actual_value = await self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return null;
                    if (el.type === "checkbox" || el.type === "radio") return el.checked ? "checked" : "unchecked";
                    if (el.tagName.toLowerCase() === "select") return el.value;
                    return el.value || el.textContent || el.innerText;
                }
            """, selector)
            
            expected_value = value.strip()
            actual_value_str = str(actual_value).strip() if actual_value is not None else ""
            if is_fillable.get('isCheckbox') or is_fillable.get('isRadio'):
                expected_value = "checked" if value.lower() in ("1", "true", "yes", "on", "checked") else "unchecked"
            
            if actual_value_str == expected_value:
                return f"Successfully filled {selector} with '{value}'"
            else:
                print(f"[DEBUG] Value verification failed. Expected: '{expected_value}', Got: '{actual_value_str}'")
                return f"Filled {selector} but value verification failed. Expected: '{expected_value}', Got: '{actual_value_str}'"
                
        except Exception as e:
            print(f"[DEBUG] Error during fill: {str(e)}")
            return f"Error filling {selector}: {str(e)}"

# Add this line:
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
async def click_element(selector: str, by: str = "css") -> str:
    """Click on an element using CSS or XPath selector."""
    if not session.page:
        raise RuntimeError("Browser not started. Call start_browser first.")
    try:
        if by == "xpath":
            element = await session.page.query_selector(f'xpath={selector}')
        else:
            element = await session.page.query_selector(selector)
        if not element:
            return f"Element not found: {selector} (by={by})"
        await element.scroll_into_view_if_needed()
        await element.focus()
        try:
            await element.click(timeout=5000, force=True)
            return f"Clicked {selector} (by={by})"
        except Exception as e:
            # JS fallback: try to click closest anchor
            await session.page.evaluate("""
                (el) => {
                    el.click();
                    let anchor = el.closest('a');
                    if(anchor && anchor.href) { window.location.href = anchor.href; }
                }
            """, element)
            return f"Clicked {selector} (by={by}) with JS fallback"
    except Exception as e:
        return f"Error clicking {selector} (by={by}): {str(e)}"

@mcp.tool()
async def fill_form(selector: str, value: str) -> str:
    """Fill a form field with a value using enhanced validation and error handling"""
    try:
        return await session.fill_enhanced(selector, value)
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

@mcp.tool()
async def get_clickable_elements() -> dict:
    """Get all clickable elements with visible text and CSS selectors"""
    if not session.page:
        raise RuntimeError("Browser not started. Call start_browser first.")

    try:
        # Wait for page to be ready
        await session.page.wait_for_timeout(1000)
        
        # Get all potentially clickable elements with improved filtering
        elements_data = await session.page.evaluate("""
            () => {
                const elements = document.querySelectorAll(`
                    a, button, input[type="submit"], input[type="button"], input[type="reset"],
                    [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="option"],
                    [onclick], [onmousedown], [onmouseup], [onkeydown], [onkeyup],
                    .btn, .button, .link, .clickable, .click, [data-action], [data-click], 
                    [data-href], [data-url], [data-target], .nav-link, .menu-item
                `);
                const result = [];
                const seenSelectors = new Set();
                for (let el of elements) {
                    if (!window.MCPIsClickable(el)) continue;
                    let selector = "";
                    if (el.id) {
                        selector = "#" + el.id;
                    } else if (el.tagName === "A" && el.innerText && el.innerText.trim().length < 40) {
                        selector = `a:has-text("${el.innerText.trim()}")`;
                    } else if (el.tagName === "BUTTON" && el.innerText && el.innerText.trim().length < 40) {
                        selector = `button:has-text("${el.innerText.trim()}")`;
                    } else if (el.tagName === "A" && el.getAttribute("href")) {
                        selector = `a[href="${el.getAttribute("href")}"]`;
                    } else {
                        const tag = el.tagName.toLowerCase();
                        const classes = el.className ? el.className.split(/\\s+/).join('.') : '';
                        selector = classes ? `${tag}.${classes}` : tag;
                    }
                    const textContent = el.textContent?.trim() || '';
                    const uniqueKey = selector + '|' + textContent;
                    if (seenSelectors.has(uniqueKey)) continue;
                    seenSelectors.add(uniqueKey);
                    result.push({
                        text: textContent,
                        selector: selector,
                        tag: el.tagName.toLowerCase(),
                        type: el.type || null,
                        href: el.href || el.getAttribute('href')
                    });
                }
                return result;
            }
        """)
        
        return {"elements": elements_data, "count": len(elements_data)}
    except Exception as e:
        return {"error": f"Failed to get clickable elements: {str(e)}", "elements": []}

@mcp.tool()
async def get_page_info() -> dict:
    """Get basic information about the current page"""
    if not session.page:
        raise RuntimeError("Browser not started. Call start_browser first.")
    
    try:
        title = await session.page.title()
        url = session.page.url
        
        # Get page readiness info
        ready_state = await session.page.evaluate("document.readyState")
        
        # Get some basic stats
        element_counts = await session.page.evaluate("""
            () => {
                return {
                    total: document.querySelectorAll('*').length,
                    visible: Array.from(document.querySelectorAll('*')).filter(el => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 && 
                               style.visibility !== 'hidden' && 
                               style.display !== 'none';
                    }).length,
                    clickable: Array.from(document.querySelectorAll('a, button, input, [onclick], [role="button"]')).length
                };
            }
        """)
        
        # Get visible text preview
        visible_text = await session.page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                let text = '';
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.trim()) {
                        text += node.textContent.trim() + ' ';
                    }
                }
                return text.substring(0, 300);
            }
        """)
        
        return {
            "title": title,
            "url": url,
            "ready_state": ready_state,
            "elements": element_counts,
            "visible_text_preview": visible_text.strip()
        }
    except Exception as e:
        return {"error": f"Failed to get page info: {str(e)}"}

@mcp.tool()
async def list_links_with_context() -> dict:
    """List all <a> links on the page with text, href, and surrounding context."""
    if not session.page:
        raise RuntimeError("Browser not started. Call start_browser first.")
    try:
        anchors = await session.page.evaluate("""
            () => {
                const anchors = Array.from(document.querySelectorAll('a'));
                return anchors.map((anchor, index) => {
                    const text = anchor.innerText.trim() || "(no text)";
                    const href = anchor.getAttribute('href') || "";
                    let container = anchor.closest('h1,h2,h3,h4,h5,h6,p,li,div');
                    let contextText = "";
                    let containerTag = "";
                    if (container) {
                        containerTag = container.tagName;
                        contextText = container.innerText.trim();
                    }
                    if (contextText.length > 100) {
                        const idx = contextText.indexOf(text);
                        if (idx >= 0) {
                            const snippetRadius = 50;
                            const start = Math.max(0, idx - snippetRadius);
                            const end = Math.min(contextText.length, idx + text.length + snippetRadius);
                            contextText = (start > 0 ? "…" : "") + contextText.substring(start, end) + (end < contextText.length ? "…" : "");
                        } else {
                            contextText = contextText.substring(0, 100) + "…";
                        }
                    }
                    return {
                        index: index + 1,
                        text: text,
                        href: href,
                        containerTag: containerTag || null,
                        context: contextText || null,
                        selector: `(//a)[${index + 1}]`
                    };
                });
            }
        """)
        return {"links": anchors}
    except Exception as e:
        return {"error": f"Failed to list links: {str(e)}"}

@mcp.tool()
async def get_form_elements() -> dict:
    """Get all form input elements with details for form filling."""
    if not session.page:
        raise RuntimeError("Browser not started. Call start_browser first.")
    try:
        elements = await session.page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input, textarea, select'));
                return inputs.map((el, idx) => {
                    const tag = el.tagName.toLowerCase();
                    const type = el.type || (tag === "textarea" ? "textarea" : (tag === "select" ? "select" : "text"));
                    const name = el.name || "";
                    const id = el.id || "";
                    const label = (() => {
                        if (el.labels && el.labels.length > 0) return el.labels[0].innerText.trim();
                        if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
                        if (el.placeholder) return el.placeholder;
                        return "";
                    })();
                    const placeholder = el.placeholder || "";
                    const value = el.value || "";
                    const required = !!el.required;
                    const maxLength = el.maxLength > 0 ? el.maxLength : null;
                    const form = el.form ? (el.form.name || el.form.id || "no-form") : "no-form";
                    const isSelect = tag === "select";
                    const isTextarea = tag === "textarea";
                    const isCheckbox = type === "checkbox";
                    const isRadio = type === "radio";
                    let options = [];
                    if (isSelect) {
                        options = Array.from(el.options).map(opt => ({
                            value: opt.value,
                            text: opt.text,
                            selected: opt.selected
                        }));
                    }
                    return {
                        index: idx,
                        tag,
                        type,
                        name,
                        id,
                        label,
                        placeholder,
                        value,
                        required,
                        maxLength,
                        form,
                        isSelect,
                        isTextarea,
                        isCheckbox,
                        isRadio,
                        options,
                        selector: window.MCPGetSelector ? window.MCPGetSelector(el) : ""
                    };
                });
            }
        """)
        return {"elements": elements}
    except Exception as e:
        return {"error": f"Failed to get form elements: {str(e)}", "elements": []}

# Run the MCP server
try:
    mcp.run(transport="stdio")
except KeyboardInterrupt:
    asyncio.run(session.stop())
except Exception as e:
    print(f"Server error: {e}")
    asyncio.run(session.stop())