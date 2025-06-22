import asyncio
import logging
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import json

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# Tools that should be hidden from the user menu (internal/utility tools)
HIDDEN_TOOLS = {
    'evaluate_javascript',  # Used internally by get_clickable_elements and other tools
    'wait_for_element',     # Used internally by click_element and other tools
    'get_form_elements'     # Used internally by form filling interface
}

def cast_input_to_type(value: str, type_hint: str):
    try:
        if type_hint == "integer":
            return int(value)
        elif type_hint == "number":
            return float(value)
        elif type_hint == "boolean":
            return value.lower() in ["true", "1", "yes", "y"]
        else:
            return value
    except ValueError:
        raise ValueError(f"Invalid input '{value}' for expected type {type_hint}")

def show_tools_menu(available_tools):
    """Display tools in a compact format, excluding internal tools"""
    # Filter out hidden tools
    visible_tools = [tool for tool in available_tools if tool.name not in HIDDEN_TOOLS]
    
    print("\n" + "=" * 60)
    print("AVAILABLE TOOLS:")
    print("=" * 60)
    for idx, tool in enumerate(visible_tools):
        print(f"{idx + 1:2d}. {tool.name:<20} | {tool.description}")
    print("=" * 60)
    print("Commands: [tool number] | 'h' for help | 'i' for info")  # <-- Removed 'q' to quit from here
    
    return visible_tools  # Return filtered list

async def get_clickable_elements_data(session):
    """Helper function to get clickable elements data from server"""
    try:
        print("\n🔍 Fetching clickable elements from browser...")
        response = await session.call_tool("get_clickable_elements")
        
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    try:
                        data = json.loads(content_item.text)
                        return data.get("elements", []), data.get("error")
                    except json.JSONDecodeError:
                        # If it's not JSON, treat as plain text
                        return [], content_item.text
        return [], "No response content"
    except Exception as e:
        return [], f"Failed to fetch elements: {str(e)}"

async def click_element_with_force(session, selector):
    """Try normal click, then force click, then navigation fallback for <a> tags."""
    try:
        result = await session.call_tool("click_element", {"selector": selector})
        if hasattr(result, "content") and result.content:
            for content_item in result.content:
                text = getattr(content_item, "text", "")
                if "not clickable" in text.lower() or "not found" in text.lower():
                    print(f"⚠️ {text}")
                    while True:
                        choice = input("Try force click? (y/N), 'n' for navigation fallback, or 'b' to go back: ").strip().lower()
                        if choice == "b":
                            return "_back_"
                        if choice == "y":
                            js = f"""
(() => {{
    const el = document.querySelector({json.dumps(selector)});
    if (!el) return "Element not found for force click";
    el.scrollIntoView({{block: "center"}});
    el.focus();
    // Try native click
    try {{
        el.click();
    }} catch (e) {{
        // Ignore
    }}
    // Dispatch pointer and mouse events for better compatibility
    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(type => {{
        const evt = new MouseEvent(type, {{
            bubbles: true,
            cancelable: true,
            view: window,
            buttons: 1
        }});
        el.dispatchEvent(evt);
    }});
    return "Force click events dispatched";
}})()
"""
                            force_result = await session.call_tool("evaluate_javascript", {"expression": js})
                            if hasattr(force_result, "content") and force_result.content:
                                for fc in force_result.content:
                                    fc_text = getattr(fc, 'text', fc)
                                    print(f"⚡ Force click result: {fc_text}")
                                    if "not found" in str(fc_text).lower():
                                        back2 = input("Force click failed. Type 'b' to go back or Enter to continue: ").strip().lower()
                                        if back2 == "b":
                                            return "_back_"
                            else:
                                print("⚡ Force click attempted (no output)")
                            return
                        if choice == "n":
                            # Navigation fallback for <a> tags
                            nav_js = f"""
(() => {{
    const el = document.querySelector({json.dumps(selector)});
    if (!el) return "Element not found for navigation fallback";
    if (el.tagName === 'A' && el.href) {{
        window.location.href = el.href;
        return "Navigated via window.location.href";
    }}
    return "Element is not a link or has no href";
}})()
"""
                            nav_result = await session.call_tool("evaluate_javascript", {"expression": nav_js})
                            if hasattr(nav_result, "content") and nav_result.content:
                                for navc in nav_result.content:
                                    print(f"🌐 Navigation fallback: {getattr(navc, 'text', navc)}")
                            return
                        if choice == "" or choice == "n":
                            return
                    return
                print(text)
        else:
            print("✅ Click executed (no output)")
    except Exception as e:
        print(f"❌ Error clicking element: {e}")

async def take_debug_screenshot(session):
    """Helper function to take a screenshot for debugging"""
    try:
        response = await session.call_tool("take_screenshot", {"path": "debug_screenshot.png"})
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    print(f"📸 {content_item.text}")
                    return True
        return False
    except Exception as e:
        print(f"❌ Failed to take screenshot: {e}")
        return False

async def get_page_info(session):
    """Helper function to get current page information"""
    try:
        response = await session.call_tool("get_page_info")
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    try:
                        data = json.loads(content_item.text)
                        return data
                    except json.JSONDecodeError:
                        return {"error": "Failed to parse page info"}
        return {"error": "No page info available"}
    except Exception as e:
        return {"error": f"Failed to get page info: {str(e)}"}

async def get_text_elements_data(session):
    """Helper function to get text elements data from server"""
    try:
        print("\n🔍 Fetching text elements from browser...")
        # Use JavaScript evaluation to get text-containing elements
        response = await session.call_tool("evaluate_javascript", {
            "expression": """
            (() => {
                const elements = document.querySelectorAll(`
                    h1, h2, h3, h4, h5, h6, p, div, span, a, button, li, td, th,
                    article, section, main, aside, header, footer, nav,
                    [role="heading"], [role="text"], [role="article"]
                `);
                
                const result = [];
                const seenText = new Set();
                
                for (let el of elements) {
                    const text = el.textContent?.trim();
                    if (!text || text.length < 5) continue; // Skip very short text
                    
                    // Skip if text is too long (likely contains child elements)
                    if (text.length > 500) continue;
                    
                    // Skip duplicates
                    if (seenText.has(text)) continue;
                    seenText.add(text);
                    
                    // Check if element is visible
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width <= 0 || rect.height <= 0) continue;
                    if (style.visibility === 'hidden' || style.display === 'none') continue;
                    
                    // Get selector (reuse the existing function if available)
                    let selector;
                    if (window.MCPGetSelector) {
                        selector = window.MCPGetSelector(el);
                    } else {
                        // Fallback selector logic
                        if (el.id) {
                            selector = "#" + el.id;
                        } else if (el.className && typeof el.className === 'string') {
                            const classes = el.className.trim().split(/\\s+/);
                            selector = "." + classes[0];
                        } else {
                            selector = el.tagName.toLowerCase();
                        }
                    }
                    
                    result.push({
                        text: text,
                        selector: selector,
                        tag: el.tagName.toLowerCase(),
                        length: text.length
                    });
                }
                
                // Sort by tag priority and text length
                result.sort((a, b) => {
                    const tagPriority = { h1: 0, h2: 1, h3: 2, h4: 3, h5: 4, h6: 5, p: 6, div: 10 };
                    const aPriority = tagPriority[a.tag] || 20;
                    const bPriority = tagPriority[b.tag] || 20;
                    
                    if (aPriority !== bPriority) return aPriority - bPriority;
                    return a.length - b.length; // Shorter text first within same tag type
                });
                
                return result.slice(0, 50); // Limit to 50 elements
            })()
            """
        })
        
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    try:
                        data = json.loads(content_item.text)
                        return data, None
                    except json.JSONDecodeError:
                        return [], content_item.text
        return [], "No response content"
    except Exception as e:
        return [], f"Failed to fetch text elements: {str(e)}"

async def get_body_text(session):
    """Helper function to get all body text"""
    try:
        response = await session.call_tool("evaluate_javascript", {
            "expression": """
            (() => {
                const body = document.body;
                if (!body) return { error: "No body element found" };
                
                // Get clean text content
                const text = body.innerText || body.textContent || "";
                
                // Also get structured text by headings
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                    level: h.tagName.toLowerCase(),
                    text: h.textContent?.trim()
                })).filter(h => h.text);
                
                // Get paragraphs
                const paragraphs = Array.from(document.querySelectorAll('p')).map(p => 
                    p.textContent?.trim()
                ).filter(p => p && p.length > 10);
                
                return {
                    fullText: text.trim(),
                    wordCount: text.trim().split(/\\s+/).length,
                    charCount: text.length,
                    headings: headings.slice(0, 20), // Limit headings
                    paragraphs: paragraphs.slice(0, 10) // Limit paragraphs
                };
            })()
            """
        })
        
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    try:
                        return json.loads(content_item.text)
                    except json.JSONDecodeError:
                        return {"error": "Failed to parse body text"}
        return {"error": "No response content"}
    except Exception as e:
        return {"error": f"Failed to get body text: {str(e)}"}

async def get_form_elements_data(session):
    """Helper function to get form elements data from server"""
    try:
        print("\n📝 Fetching form elements from browser...")
        response = await session.call_tool("get_form_elements")
        
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    try:
                        data = json.loads(content_item.text)
                        return data.get("elements", []), data.get("error")
                    except json.JSONDecodeError:
                        # If it's not JSON, treat as plain text
                        return [], content_item.text
        return [], "No response content"
    except Exception as e:
        return [], f"Failed to fetch form elements: {str(e)}"

def format_form_element_display(el, index):
    """Format form element for display in selection menu"""
    # Get basic info
    tag = el.get("tag", "unknown").upper()
    input_type = el.get("type", "text")
    name = el.get("name", "")
    label = el.get("label", "")
    placeholder = el.get("placeholder", "")
    value = el.get("value", "")
    required = el.get("required", False)
    form = el.get("form", "")
    max_length = el.get("maxLength")
    
    # Build display text
    display_parts = []
    
    # Add label or name as primary identifier
    if label:
        display_parts.append(f"'{label}'")
    elif name:
        display_parts.append(f"[{name}]")
    elif placeholder:
        display_parts.append(f'"{placeholder}"')
    else:
        display_parts.append("[Unnamed field]")
    
    # Add current value if present
    if value:
        value_preview = value[:30] + "..." if len(value) > 30 else value
        display_parts.append(f"= '{value_preview}'")
    
    # Build type info
    type_info = f"{tag}"
    if tag == "INPUT":
        type_info += f"[{input_type}]"
    elif el.get("isSelect"):
        options_count = len(el.get("options", []))
        type_info += f"[{options_count} options]"
    elif el.get("isTextarea"):
        type_info += "[multiline]"
    
    # Build the main display line
    main_text = " ".join(display_parts)
    
    # Add indicators
    indicators = []
    if required:
        indicators.append("REQUIRED")
    if max_length:
        indicators.append(f"max:{max_length}")
    if form and form != "no-form":
        indicators.append(f"form:{form}")
    
    indicator_text = f" ({', '.join(indicators)})" if indicators else ""
    
    return f"{index + 1:2d}. [{type_info}] {main_text}{indicator_text}"

def show_form_element_details(el):
    """Show detailed information about a form element"""
    print(f"\n📋 Element Details:")
    print(f"Selector: {el.get('selector', 'Unknown')}")
    print(f"Tag: {el.get('tag', 'unknown').upper()}")
    print(f"Type: {el.get('type', 'text')}")
    print(f"Name: {el.get('name', 'None')}")
    print(f"ID: {el.get('id', 'None')}")
    print(f"Label: {el.get('label', 'None')}")
    print(f"Placeholder: {el.get('placeholder', 'None')}")
    print(f"Current Value: {el.get('value', 'Empty')}")
    print(f"Required: {'Yes' if el.get('required') else 'No'}")
    if el.get('maxLength'):
        print(f"Max Length: {el.get('maxLength')}")
    print(f"Form: {el.get('form', 'None')}")
    
    # Show select options if applicable
    if el.get('isSelect') and el.get('options'):
        print(f"\nAvailable Options:")
        for i, option in enumerate(el.get('options', [])):
            print(f"  {i+1}. {option.get('text', '')} (value: {option.get('value', '')})")

def show_internal_tools_info():
    """Show information about hidden internal tools"""
    print("\n" + "=" * 60)
    print("INTERNAL TOOLS (Auto-used by other tools):")
    print("=" * 60)
    print("🔧 evaluate_javascript:")
    print("   • Executes JavaScript in browser context")
    print("   • Used by: get_clickable_elements, get_page_info")
    print("   • Automatically runs custom JS for element detection")
    print()
    print("⏳ wait_for_element:")
    print("   • Waits for elements to appear on page")
    print("   • Used by: click_element (when elements aren't immediately available)")
    print("   • Automatically handles dynamic content loading")
    print()
    print("📋 get_form_elements:")
    print("   • Fetches detailed information about form input elements.")
    print("   • Used by: fill_form (to help you select which field to fill)")
    print("   • Provides labels, placeholders, and current values of form fields.")
    print()
    print("These tools work behind the scenes to make other tools more reliable!")
    print("=" * 60)

async def get_user_input_for_param(session, selected_tool, param, definition, is_required=False):
    """Get user input for a parameter with validation and clickable element support"""
    param_desc = definition.get("description", "")
    default_val = definition.get("default")
    choices = definition.get("enum")
    type_hint = definition.get("type", "string")

    # Special handling: auto-fetch clickable elements if relevant
    if "click" in selected_tool.name.lower() and "selector" in param.lower():
        page_info = await get_page_info(session)
        if "error" not in page_info:
            print(f"📄 Current page: {page_info.get('title', 'Unknown')}")
            print(f"🌐 URL: {page_info.get('url', 'Unknown')}")
            element_info = page_info.get('elements', {})
            if isinstance(element_info, dict):
                print(f"📊 Page elements: {element_info.get('total', 0)} total, {element_info.get('visible', 0)} visible, {element_info.get('clickable', 0)} clickable")
            elif element_info:
                print(f"📊 Page elements info: {element_info}")
        else:
            print(f"⚠️ Page info error: {page_info['error']}")
        elements, error = await get_clickable_elements_data(session)
        if error:
            print(f"⚠️ Warning while fetching elements: {error}")

        if elements:
            print(f"\n📌 Found {len(elements)} clickable elements:")
            print("=" * 80)
            for i, el in enumerate(elements):
                text = el.get("text", "[No text]").strip()
                selector = el.get("selector", "<unknown>")
                tag = el.get("tag", "unknown")
                elem_type = el.get("type")
                href = el.get("href")
                type_info = f" ({elem_type})" if elem_type else ""
                href_info = f" → {href}" if href else ""
                print(f"{i + 1:2d}. [{tag.upper()}{type_info}] {text}{href_info}")
                print(f"    Selector: {selector}   [Index: {i}]")
                if i < len(elements) - 1 and (i + 1) % 5 == 0:
                    print()
            print("=" * 80)
            while True:
                user_input = input(f"Choose (1-{len(elements)}) | 'm' manual | 'i' index click | 's' screenshot | 'r' refresh | 'p' page info [or 'q' to quit]: ").strip()
                if user_input.lower() == 'q':
                    print("👋 Exiting...")
                    return
                if user_input.lower() == 'm':
                    print("📝 Switching to manual selector input...")
                    break
                elif user_input.lower() == 's':
                    await take_debug_screenshot(session)
                    continue
                elif user_input.lower() == 'r':
                    print("🔄 Refreshing elements...")
                    return await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                elif user_input.lower() == 'p':
                    page_info = await get_page_info(session)
                    print(f"\n📄 Page Information:")
                    print(f"Title: {page_info.get('title', 'Unknown')}")
                    print(f"URL: {page_info.get('url', 'Unknown')}")
                    print(f"Ready State: {page_info.get('ready_state', 'Unknown')}")
                    if 'visible_text_preview' in page_info:
                        print(f"Preview: {page_info['visible_text_preview'][:200]}...")
                    continue
                elif user_input.lower() == 'i':
                    idx = input(f"Enter index (0-{len(elements)-1}): ").strip()
                    try:
                        idx = int(idx)
                        chosen_element = elements[idx]
                        print(f"✅ Index-based click: {chosen_element['selector']} at index {idx}")
                        # Call the new tool
                        result = await session.call_tool("click_element_by_index", {"selector": chosen_element["selector"], "index": idx})
                        print(f"Result: {getattr(result, 'content', result)}")
                        return chosen_element["selector"]
                    except Exception as e:
                        print(f"❌ Invalid index: {e}")
                    continue
                try:
                    selected = int(user_input) - 1
                    if 0 <= selected < len(elements):
                        chosen_element = elements[selected]
                        print(f"✅ Selected: {chosen_element['text']}")
                        print(f"🎯 Selector: {chosen_element['selector']}")
                        # Try click with force/back option
                        click_result = await click_element_with_force(session, chosen_element["selector"])
                        if click_result == "_back_":
                            continue
                        return chosen_element["selector"]
                    else:
                        print(f"❌ Invalid selection. Enter 1-{len(elements)} or a command.")
                except ValueError:
                    print("❌ Please enter a valid number or command.")
        else:
            print("⚠️ No clickable elements found on the current page.")
            while True:
                debug_choice = input("Debug options: 's' screenshot | 'p' page info | 'm' manual input | 'r' retry [or 'q' to quit]: ").strip().lower()
                if debug_choice == 'q':
                    print("👋 Exiting...")
                    return
                if debug_choice == "s":
                    await take_debug_screenshot(session)
                elif debug_choice == "p":
                    page_info = await get_page_info(session)
                    print(f"\n📄 Page Information:")
                    for key, value in page_info.items():
                        print(f"{key}: {value}")
                elif debug_choice == "m":
                    print("📝 Switching to manual selector input...")
                    break
                elif debug_choice == "r":
                    print("🔄 Retrying element detection...")
                    return await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                else:
                    print("❌ Invalid option. Choose 's', 'p', 'm', or 'r'.")

    # Special handling: auto-fetch text elements for extract_text tool
    elif "extract" in selected_tool.name.lower() and "selector" in param.lower():
        print(f"📝 Text Extraction Options:")
        print("1. 📋 Browse text elements on page")
        print("2. 📄 Get all body text")
        print("3. ✏️  Manual selector input")
        
        while True:
            choice = input("Choose option (1-3) [or 'q' to quit]: ").strip()
            if choice.lower() == 'q':
                print("👋 Exiting...")
                return
            if choice == "1":
                # Get text elements
                elements, error = await get_text_elements_data(session)
                
                if error:
                    print(f"⚠️ Warning while fetching text elements: {error}")
                
                if elements:
                    print(f"\n📝 Found {len(elements)} text elements:")
                    print("=" * 80)
                    
                    for i, el in enumerate(elements):
                        text = el.get("text", "[No text]").strip()
                        selector = el.get("selector", "<unknown>")
                        tag = el.get("tag", "unknown")
                        length = el.get("length", 0)
                        
                        # Truncate long text for display
                        display_text = text[:60] + "..." if len(text) > 60 else text
                        
                        print(f"{i + 1:2d}. [{tag.upper()}] {display_text} ({length} chars)")
                        print(f"    Selector: {selector}")
                        
                        # Add spacing every 5 items for readability
                        if i < len(elements) - 1 and (i + 1) % 5 == 0:
                            print()
                    
                    print("=" * 80)
                    
                    while True:
                        user_input = input(f"Choose (1-{len(elements)}) | 'b' back | 's' screenshot [or 'q' to quit]: ").strip()
                        if user_input.lower() == 'q':
                            print("👋 Exiting...")
                            return
                        if user_input.lower() == 'b':
                            break
                        elif user_input.lower() == 's':
                            await take_debug_screenshot(session)
                            continue
                        try:
                            selected = int(user_input) - 1
                            if 0 <= selected < len(elements):
                                chosen_element = elements[selected]
                                print(f"✅ Selected text: {chosen_element['text'][:100]}...")
                                print(f"🎯 Selector: {chosen_element['selector']}")
                                return chosen_element["selector"]
                            else:
                                print(f"❌ Invalid selection. Enter 1-{len(elements)} or 'b' to go back.")
                        except ValueError:
                            print("❌ Please enter a valid number or 'b'.")
                else:
                    print("⚠️ No text elements found on the current page.")
                    print("Falling back to manual input...")
                    break
            elif choice == "2":
                # Get body text
                body_data = await get_body_text(session)
                
                if "error" in body_data:
                    print(f"❌ Error getting body text: {body_data['error']}")
                    continue
                
                print(f"\n📄 Page Body Text Summary:")
                print("=" * 60)
                print(f"📊 Word Count: {body_data.get('wordCount', 0)}")
                print(f"📊 Character Count: {body_data.get('charCount', 0)}")
                
                headings = body_data.get('headings', [])
                if headings:
                    print(f"\n📋 Headings ({len(headings)}):")
                    for heading in headings[:10]:  # Show first 10
                        print(f"  {heading['level'].upper()}: {heading['text']}")
                
                paragraphs = body_data.get('paragraphs', [])
                if paragraphs:
                    print(f"\n📝 Sample Paragraphs ({len(paragraphs)}):")
                    for i, para in enumerate(paragraphs[:3]):  # Show first 3
                        preview = para[:100] + "..." if len(para) > 100 else para
                        print(f"  {i+1}. {preview}")
                
                print("\n" + "=" * 60)
                
                action = input("Actions: 'f' full text | 'h' headings only | 'p' paragraphs only | 'b' back [or 'q' to quit]: ").strip().lower()
                
                if action == 'q':
                    print("👋 Exiting...")
                    return
                if action == 'f':
                    return "body"  # Special selector for full body text
                elif action == 'h':
                    return "h1, h2, h3, h4, h5, h6"  # Selector for all headings
                elif action == 'p':
                    return "p"  # Selector for all paragraphs
                elif action == 'b':
                    continue
                else:
                    print("❌ Invalid option.")
                    continue
            elif choice == "3":
                print("📝 Switching to manual selector input...")
                break
            else:
                print("❌ Invalid choice. Enter 1, 2, or 3.")

    # Special handling: auto-fetch form elements for fill_form tool
    elif "fill" in selected_tool.name.lower() and "selector" in param.lower():
        # First, get page info to ensure we're on a valid page
        page_info = await get_page_info(session)
        if "error" not in page_info:
            print(f"📄 Current page: {page_info.get('title', 'Unknown')}")
            print(f"🌐 URL: {page_info.get('url', 'Unknown')}")
            element_info = page_info.get('elements', {})
            if element_info:
                print(f"📊 Page elements: {element_info.get('total', 0)} total, {element_info.get('visible', 0)} visible")
        else:
            print(f"⚠️ Page info error: {page_info['error']}")
        
        # Now get form elements
        elements, error = await get_form_elements_data(session)
        
        if error:
            print(f"⚠️ Warning while fetching form elements: {error}")
        if elements:
            print(f"\n📝 Found {len(elements)} form elements:")
            print("=" * 90)
            form_groups = {}
            for el in elements:
                form_name = el.get("form", "no-form")
                if form_name not in form_groups:
                    form_groups[form_name] = []
                form_groups[form_name].append(el)
            element_index = 0
            for form_name, form_elements in form_groups.items():
                if len(form_groups) > 1:
                    form_display = "No Form" if form_name == "no-form" else f"Form: {form_name}"
                    print(f"\n🔲 {form_display}")
                    print("-" * 50)
                for el in form_elements:
                    print(format_form_element_display(el, element_index))
                    print(f"    Selector: {el.get('selector', 'unknown')}")
                    element_index += 1
                    if element_index < len(elements) and element_index % 5 == 0:
                        print()
            print("=" * 90)
            while True:
                user_input = input(f"Choose (1-{len(elements)}) | 'd' details | 'm' manual | 's' screenshot | 'r' refresh | 'p' page info [or 'q' to quit]: ").strip()
                if user_input.lower() == 'q':
                    print("👋 Exiting...")
                    return
                if user_input.lower() == 'm':
                    print("📝 Switching to manual selector input...")
                    break
                elif user_input.lower() == 's':
                    await take_debug_screenshot(session)
                    continue
                elif user_input.lower() == 'r':
                    print("🔄 Refreshing form elements...")
                    return await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                elif user_input.lower() == 'p':
                    page_info = await get_page_info(session)
                    print(f"\n📄 Page Information:")
                    print(f"Title: {page_info.get('title', 'Unknown')}")
                    print(f"URL: {page_info.get('url', 'Unknown')}")
                    print(f"Ready State: {page_info.get('ready_state', 'Unknown')}")
                    if 'visible_text_preview' in page_info:
                        print(f"Preview: {page_info['visible_text_preview'][:200]}...")
                    continue
                elif user_input.lower() == 'd':
                    detail_input = input(f"Show details for element (1-{len(elements)}) [or 'q' to quit]: ").strip()
                    if detail_input.lower() == 'q':
                        print("👋 Exiting...")
                        return
                    try:
                        detail_index = int(detail_input) - 1
                        if 0 <= detail_index < len(elements):
                            show_form_element_details(elements[detail_index])
                        else:
                            print(f"❌ Invalid selection. Enter 1-{len(elements)}.")
                    except ValueError:
                        print("❌ Please enter a valid number.")
                    continue
                try:
                    selected = int(user_input) - 1
                    if 0 <= selected < len(elements):
                        chosen_element = elements[selected]
                        print(f"✅ Selected: {chosen_element.get('label', chosen_element.get('name', 'Unnamed field'))}")
                        print(f"🎯 Selector: {chosen_element['selector']}")
                        if chosen_element.get('isSelect'):
                            print("📋 This is a select/dropdown element")
                            if chosen_element.get('options'):
                                print("Available options:", [opt.get('text', opt.get('value', '')) for opt in chosen_element.get('options', [])])
                        elif chosen_element.get('type') in ['email', 'password', 'tel', 'url']:
                            print(f"📧 This is a {chosen_element.get('type')} input field")
                        elif chosen_element.get('maxLength'):
                            print(f"📏 Maximum length: {chosen_element.get('maxLength')} characters")
                        return chosen_element["selector"]
                    else:
                        print(f"❌ Invalid selection. Enter 1-{len(elements)} or a command.")
                except ValueError:
                    print("❌ Please enter a valid number or command.")
        else:
            print("⚠️ No form elements found on the current page.")
            while True:
                debug_choice = input("Debug options: 's' screenshot | 'p' page info | 'm' manual input | 'r' retry [or 'q' to quit]: ").strip().lower()
                if debug_choice == 'q':
                    print("👋 Exiting...")
                    return
                if debug_choice == "s":
                    await take_debug_screenshot(session)
                elif debug_choice == "p":
                    page_info = await get_page_info(session)
                    print(f"\n📄 Page Information:")
                    for key, value in page_info.items():
                        print(f"{key}: {value}")
                elif debug_choice == "m":
                    print("📝 Switching to manual selector input...")
                    break
                elif debug_choice == "r":
                    print("🔄 Retrying form element detection...")
                    return await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                else:
                    print("❌ Invalid option. Choose 's', 'p', 'm', or 'r'.")

    # Special handling for the 'value' parameter when filling forms
    elif "fill" in selected_tool.name.lower() and "value" in param.lower():
        prompt = f"\n📝 Enter the value to fill"
        if param_desc:
            prompt += f" ({param_desc})"
        print("\n💡 Filling Tips:")
        print("• For email fields: user@example.com")
        print("• For password fields: Use a secure password")
        print("• For select dropdowns: Enter the visible option text or value")
        print("• For dates: Use format shown in placeholder (if any)")
        print("• For numbers: Enter numeric values only")
        if default_val is not None:
            prompt += f" [default: {default_val}]"
        if is_required:
            prompt += " [REQUIRED]"
        prompt += " [or 'q' to quit]: "
        while True:
            user_input = input(prompt).strip()
            if user_input.lower() == 'q':
                print("👋 Exiting...")
                return
            if user_input:
                try:
                    return cast_input_to_type(user_input, type_hint)
                except ValueError as e:
                    print(f"❌ Error: {e}")
            elif default_val is not None:
                return cast_input_to_type(str(default_val), type_hint)
            elif not is_required:
                return None
            else:
                print("❌ This field is required. Please enter a value.")

    if choices:
        print(f"\n📋 Choose a value for '{param}' ({param_desc}):")
        for i, choice in enumerate(choices):
            print(f"{i + 1}. {choice}")
        while True:
            selected = input(f"Select a value (1-{len(choices)}) [or 'q' to quit]: ")
            if selected.lower() == 'q':
                print("👋 Exiting...")
                return
            try:
                selected = int(selected) - 1
                if 0 <= selected < len(choices):
                    return choices[selected]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a number.")

    prompt = f"\n📝 Enter '{param}'"
    if param_desc:
        prompt += f" ({param_desc})"
    if default_val is not None:
        prompt += f" [default: {default_val}]"
    if is_required:
        prompt += " [REQUIRED]"
    prompt += " [or 'q' to quit]: "
    while True:
        user_input = input(prompt).strip()
        if user_input.lower() == 'q':
            print("👋 Exiting...")
            return
        if user_input:
            try:
                return cast_input_to_type(user_input, type_hint)
            except ValueError as e:
                print(f"❌ Error: {e}")
        elif default_val is not None:
            return cast_input_to_type(str(default_val), type_hint)
        elif not is_required:
            return None
        else:
            print("❌ This field is required. Please enter a value.")

async def run_script():
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"], env=None)
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("🚀 Starting Enhanced MCP Browser Automation Client...")
                print("⏳ Initializing MCP session...")
                await session.initialize()
                print("📋 Fetching available tools...")
                response = await session.list_tools()
                all_tools = response.tools
                if not all_tools:
                    print("❌ No tools available from the server.")
                    return
                while True:
                    visible_tools = show_tools_menu(all_tools)
                    while True:
                        try:
                            selection = input("\nSelect tool [or 'q' to quit]: ").strip()
                            if selection.lower() == 'q':
                                print("👋 Exiting...")
                                return
                            elif selection.lower() == 'h':
                                print("\n📖 Help:")
                                print("- Enter tool number to run a tool")
                                print("- 'q' to quit")
                                print("- 'h' for this help")
                                print("- 'i' for info about internal tools")
                                print("- When selecting elements, use 's' for screenshot, 'p' for page info")
                                continue
                            elif selection.lower() == 'i':
                                show_internal_tools_info()
                                continue
                            selected_index = int(selection) - 1
                            if 0 <= selected_index < len(visible_tools):
                                selected_tool = visible_tools[selected_index]
                                break
                            else:
                                print(f"❌ Invalid selection. Enter 1-{len(visible_tools)}, 'h', 'i', or 'q'.")
                        except ValueError:
                            print("❌ Enter a number, 'h' for help, 'i' for info, or 'q' to quit.")
                    print(f"\n🔧 CONFIGURING: {selected_tool.name}")
                    print(f"📝 Description: {selected_tool.description}")
                    print("-" * 50)
                    args = {}
                    schema = selected_tool.inputSchema
                    if isinstance(schema, dict) and schema:
                        if "properties" in schema:
                            properties = schema.get("properties", {})
                            required = schema.get("required", [])
                            if not properties:
                                print("✅ This tool requires no parameters.")
                            else:
                                for param, definition in properties.items():
                                    is_required = param in required
                                    value = await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                                    if value is None:
                                        return
                                    if value is not None:
                                        args[param] = value
                        else:
                            for param, definition in schema.items():
                                if isinstance(definition, dict):
                                    is_required = definition.get("required", True)
                                    value = await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                                    if value is None:
                                        return
                                    if value is not None:
                                        args[param] = value
                                else:
                                    value = input(f"\n📝 Enter '{param}' [or 'q' to quit]: ").strip()
                                    if value.lower() == 'q':
                                        print("👋 Exiting...")
                                        return
                                    if value:
                                        args[param] = value
                    else:
                        print("✅ This tool requires no parameters.")
                    print(f"\n⚡ EXECUTING: {selected_tool.name}")
                    if args:
                        print(f"📊 Arguments: {args}")
                    print("-" * 50)
                    try:
                        result = await session.call_tool(selected_tool.name, arguments=args)
                        print("📋 RESULT:")
                        if hasattr(result, 'content') and result.content:
                            for content_item in result.content:
                                text = getattr(content_item, "text", None)
                                if text is not None:
                                    try:
                                        data = json.loads(text)
                                        print(json.dumps(data, indent=2))
                                    except (json.JSONDecodeError, TypeError):
                                        print(text)
                                else:
                                    print(content_item)
                        else:
                            print("✅ Tool executed successfully (no output)")
                    except Exception as e:
                        print(f"❌ Error executing tool: {e}")
                        logging.error(f"Tool execution error: {e}")
                    cont = input("\n🔄 Press Enter to continue... [or 'q' to quit]: ")
                    if cont.lower() == 'q':
                        print("👋 Exiting...")
                        return
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        logging.error(f"MCP connection error: {e}")

if __name__ == "__main__":
    asyncio.run(run_script())