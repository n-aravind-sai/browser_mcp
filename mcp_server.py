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
            
            # Check if element is fillable
            is_fillable = await self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return { fillable: false, reason: 'Element not found' };
                    
                    const tagName = el.tagName.toLowerCase();
                    const inputType = el.type || 'text';
                    const isContentEditable = el.contentEditable === 'true';
                    
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
                                      isContentEditable;
                    
                    // Check if element is disabled or readonly
                    const disabled = el.disabled || el.readOnly;
                    
                    return {
                        fillable: visible && isFillable && !disabled,
                        visible: visible,
                        disabled: disabled,
                        tagName: tagName,
                        type: inputType,
                        contentEditable: isContentEditable,
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
            
            # Clear existing content first
            await self.page.fill(selector, "")
            await self.page.wait_for_timeout(100)
            
            # Fill with new value
            if is_fillable.get('contentEditable'):
                # For contenteditable elements, use different approach
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
            
            # Verify the value was set
            actual_value = await self.page.evaluate("""
                (selector) => {
                    const el = document.querySelector(selector);
                    return el ? (el.value || el.textContent || el.innerText) : null;
                }
            """, selector)
            
            if actual_value == value:
                return f"Successfully filled {selector} with '{value}'"
            else:
                return f"Filled {selector} but value verification failed. Expected: '{value}', Got: '{actual_value}'"
                
        except Exception as e:
            print(f"[DEBUG] Error during fill: {str(e)}")
            return f"Error filling {selector}: {str(e)}"

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
async def get_form_elements() -> dict:
    """Get all form elements (inputs, textareas, selects) with their details and CSS selectors"""
    if not session.page:
        raise RuntimeError("Browser not started. Call start_browser first.")

    try:
        # Wait for page to be ready
        await session.page.wait_for_timeout(1000)
        
        # Get all form elements with improved filtering
        elements_data = await session.page.evaluate("""
            () => {
                const elements = document.querySelectorAll(`
                    input[type="text"], input[type="email"], input[type="password"], 
                    input[type="search"], input[type="tel"], input[type="url"], 
                    input[type="number"], input[type="date"], input[type="time"],
                    input[type="datetime-local"], input[type="month"], input[type="week"],
                    input[type="color"], input[type="range"], input[type="file"],
                    input:not([type]), textarea, select,
                    [contenteditable="true"], [role="textbox"], [role="searchbox"],
                    [role="combobox"], [data-input], [data-field], [data-form-field]
                `);
                
                const result = [];
                const seenSelectors = new Set();
                
                for (let el of elements) {
                    // Skip hidden or disabled elements
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    if (style.visibility === 'hidden' || style.display === 'none') continue;
                    if (el.disabled || el.readOnly) continue;
                    
                    // Check if element is in viewport
                    if (rect.bottom < 0 || rect.top > window.innerHeight) continue;
                    if (rect.right < 0 || rect.left > window.innerWidth) continue;
                    
                    // Get element details
                    const tagName = el.tagName.toLowerCase();
                    const inputType = el.type || 'text';
                    const name = el.name || '';
                    const id = el.id || '';
                    const placeholder = el.placeholder || '';
                    const value = el.value || '';
                    const required = el.required || false;
                    const maxLength = el.maxLength > 0 ? el.maxLength : null;
                    
                    // Get label text
                    let labelText = '';
                    if (id) {
                        const label = document.querySelector(`label[for="${id}"]`);
                        if (label) labelText = label.textContent?.trim() || '';
                    }
                    if (!labelText) {
                        // Look for parent label
                        const parentLabel = el.closest('label');
                        if (parentLabel) labelText = parentLabel.textContent?.trim() || '';
                    }
                    if (!labelText) {
                        // Look for nearby text (aria-label, title, etc.)
                        labelText = el.getAttribute('aria-label') || 
                                   el.getAttribute('title') || 
                                   el.getAttribute('data-label') || '';
                    }
                    
                    // Get improved selector using existing function
                    const selector = window.MCPGetSelector ? window.MCPGetSelector(el) : 
                                   (id ? `#${id}` : (name ? `[name="${name}"]` : tagName));
                    
                    // Avoid duplicates
                    const uniqueKey = selector + '|' + inputType + '|' + name;
                    if (seenSelectors.has(uniqueKey)) continue;
                    seenSelectors.add(uniqueKey);
                    
                    // Get form context
                    const form = el.closest('form');
                    const formName = form ? (form.name || form.id || 'unnamed') : 'no-form';
                    
                    // Get select options if it's a select element
                    let options = [];
                    if (tagName === 'select') {
                        options = Array.from(el.options).map(opt => ({
                            value: opt.value,
                            text: opt.textContent?.trim() || opt.value
                        }));
                    }
                    
                    result.push({
                        selector: selector,
                        tag: tagName,
                        type: inputType,
                        name: name,
                        id: id,
                        label: labelText,
                        placeholder: placeholder,
                        value: value,
                        required: required,
                        maxLength: maxLength,
                        form: formName,
                        options: options,
                        isSelect: tagName === 'select',
                        isTextarea: tagName === 'textarea',
                        isContentEditable: el.contentEditable === 'true'
                    });
                }
                
                // Sort by priority: required first, then by form grouping, then by type
                result.sort((a, b) => {
                    // Required fields first
                    if (a.required && !b.required) return -1;
                    if (!a.required && b.required) return 1;
                    
                    // Group by form
                    if (a.form !== b.form) return a.form.localeCompare(b.form);
                    
                    // Sort by input type priority
                    const typePriority = {
                        email: 0, text: 1, password: 2, search: 3, tel: 4, url: 5,
                        number: 6, date: 7, time: 8, textarea: 9, select: 10
                    };
                    const aPriority = typePriority[a.type] || 20;
                    const bPriority = typePriority[b.type] || 20;
                    
                    return aPriority - bPriority;
                });
                
                return result;
            }
        """)
        
        return {"elements": elements_data, "count": len(elements_data)}
    except Exception as e:
        return {"error": f"Failed to get form elements: {str(e)}", "elements": []}

# Add the enhanced fill method to BrowserSession

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
        
        # Check if element is fillable
        is_fillable = await self.page.evaluate("""
            (selector) => {
                const el = document.querySelector(selector);
                if (!el) return { fillable: false, reason: 'Element not found' };
                
                const tagName = el.tagName.toLowerCase();
                const inputType = el.type || 'text';
                const isContentEditable = el.contentEditable === 'true';
                
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
                                  isContentEditable;
                
                // Check if element is disabled or readonly
                const disabled = el.disabled || el.readOnly;
                
                return {
                    fillable: visible && isFillable && !disabled,
                    visible: visible,
                    disabled: disabled,
                    tagName: tagName,
                    type: inputType,
                    contentEditable: isContentEditable,
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
        
        # Clear existing content first
        await self.page.fill(selector, "")
        await self.page.wait_for_timeout(100)
        
        # Fill with new value
        if is_fillable.get('contentEditable'):
            # For contenteditable elements, use different approach
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
        
        # Verify the value was set
        actual_value = await self.page.evaluate("""
            (selector) => {
                const el = document.querySelector(selector);
                return el ? (el.value || el.textContent || el.innerText) : null;
            }
        """, selector)
        
        if actual_value == value:
            return f"Successfully filled {selector} with '{value}'"
        else:
            return f"Filled {selector} but value verification failed. Expected: '{value}', Got: '{actual_value}'"
            
    except Exception as e:
        print(f"[DEBUG] Error during fill: {str(e)}")
        return f"Error filling {selector}: {str(e)}"

BrowserSession.fill_enhanced = fill_enhanced

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
                    [data-href], [data-url], [data-target], .nav-link, .menu-item,
                    select, textarea, input[type="text"], input[type="email"], 
                    input[type="password"], input[type="search"], input[type="tel"],
                    input[type="url"], input[type="number"], input[type="checkbox"],
                    input[type="radio"], [contenteditable="true"], [tabindex]:not([tabindex="-1"])
                `);
                
                const result = [];
                const seenSelectors = new Set();
                
                for (let el of elements) {
                    // Use our improved visibility and clickability check
                    if (!window.MCPIsClickable(el)) continue;
                    
                    // Get text content with fallbacks
                    let textContent = el.textContent?.trim() || '';
                    if (!textContent) {
                        textContent = el.value || el.placeholder || el.getAttribute('aria-label') || 
                                    el.getAttribute('title') || el.getAttribute('alt') || '[No text]';
                    }
                    
                    // Truncate long text
                    if (textContent.length > 80) {
                        textContent = textContent.substring(0, 77) + '...';
                    }
                    
                    // Get improved selector
                    const selector = window.MCPGetSelector(el);
                    
                    // Avoid duplicates - but allow duplicates if text is different
                    const uniqueKey = selector + '|' + textContent;
                    if (seenSelectors.has(uniqueKey)) continue;
                    seenSelectors.add(uniqueKey);
                    
                    // Get element info
                    const tagName = el.tagName.toLowerCase();
                    const elementType = el.type || null;
                    const href = el.href || el.getAttribute('href');
                    
                    result.push({
                        text: textContent,
                        selector: selector,
                        tag: tagName,
                        type: elementType,
                        href: href && href.length > 50 ? href.substring(0, 47) + '...' : href
                    });
                }
                
                // Sort by priority: buttons first, then links, then others
                result.sort((a, b) => {
                    const getPriority = (elem) => {
                        if (elem.tag === 'button') return 0;
                        if (elem.tag === 'a') return 1;
                        if (elem.tag === 'input') return 2;
                        return 3;
                    };
                    
                    const priorityDiff = getPriority(a) - getPriority(b);
                    if (priorityDiff !== 0) return priorityDiff;
                    
                    // Secondary sort by text length (shorter first)
                    return a.text.length - b.text.length;
                });
                
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

# Run the MCP server
try:
    mcp.run(transport="stdio")
except KeyboardInterrupt:
    asyncio.run(session.stop())
except Exception as e:
    print(f"Server error: {e}")
    asyncio.run(session.stop())