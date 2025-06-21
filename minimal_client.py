import asyncio
import logging
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

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
    """Display tools in a compact format"""
    print("\n" + "=" * 60)
    print("AVAILABLE TOOLS:")
    print("=" * 60)
    for idx, tool in enumerate(available_tools):
        print(f"{idx + 1:2d}. {tool.name:<20} | {tool.description}")
    print("=" * 60)
    print("Commands: [tool number] | 'q' to quit | 'h' for help")

async def get_clickable_elements_data(session):
    """Helper function to get clickable elements data from server"""
    try:
        print("\n🔍 Fetching clickable elements from browser...")
        response = await session.call_tool("get_clickable_elements")
        
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    import json
                    try:
                        data = json.loads(content_item.text)
                        return data.get("elements", []), data.get("error")
                    except json.JSONDecodeError:
                        # If it's not JSON, treat as plain text
                        return [], content_item.text
        return [], "No response content"
    except Exception as e:
        return [], f"Failed to fetch elements: {str(e)}"

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
                    import json
                    try:
                        data = json.loads(content_item.text)
                        return data
                    except json.JSONDecodeError:
                        return {"error": "Failed to parse page info"}
        return {"error": "No page info available"}
    except Exception as e:
        return {"error": f"Failed to get page info: {str(e)}"}

async def get_user_input_for_param(session, selected_tool, param, definition, is_required=False):
    """Get user input for a parameter with validation and clickable element support"""
    param_desc = definition.get("description", "")
    default_val = definition.get("default")
    choices = definition.get("enum")
    type_hint = definition.get("type", "string")

    # Special handling: auto-fetch clickable elements if relevant
    if "click" in selected_tool.name.lower() and "selector" in param.lower():
        # First, get page info to ensure we're on a valid page
        page_info = await get_page_info(session)
        if "error" not in page_info:
            print(f"📄 Current page: {page_info.get('title', 'Unknown')}")
            print(f"🌐 URL: {page_info.get('url', 'Unknown')}")
            element_info = page_info.get('elements', {})
            if element_info:
                print(f"📊 Page elements: {element_info.get('total', 0)} total, {element_info.get('visible', 0)} visible, {element_info.get('clickable', 0)} clickable")
        else:
            print(f"⚠️ Page info error: {page_info['error']}")
        
        # Now get clickable elements
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
                
                # Format element display
                type_info = f" ({elem_type})" if elem_type else ""
                href_info = f" → {href}" if href else ""
                
                print(f"{i + 1:2d}. [{tag.upper()}{type_info}] {text}{href_info}")
                print(f"    Selector: {selector}")
                
                # Add spacing every 5 items for readability
                if i < len(elements) - 1 and (i + 1) % 5 == 0:
                    print()
            
            print("=" * 80)
            
            while True:
                user_input = input(f"Choose (1-{len(elements)}) | 'm' manual | 's' screenshot | 'r' refresh | 'p' page info: ").strip()
                
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
                        print(f"Text Preview: {page_info['visible_text_preview'][:200]}...")
                    continue
                
                try:
                    selected = int(user_input) - 1
                    if 0 <= selected < len(elements):
                        chosen_element = elements[selected]
                        print(f"✅ Selected: {chosen_element['text']}")
                        print(f"🎯 Selector: {chosen_element['selector']}")
                        return chosen_element["selector"]
                    else:
                        print(f"❌ Invalid selection. Enter 1-{len(elements)} or a command.")
                except ValueError:
                    print("❌ Please enter a valid number or command.")
        else:
            print("⚠️ No clickable elements found on the current page.")
            
            # Offer debugging options
            while True:
                debug_choice = input("Debug options: 's' screenshot | 'p' page info | 'm' manual input | 'r' retry: ").strip().lower()
                
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

    # Enum-based multiple choice
    if choices:
        print(f"\n📋 Choose a value for '{param}' ({param_desc}):")
        for i, choice in enumerate(choices):
            print(f"{i + 1}. {choice}")
        while True:
            try:
                selected = int(input(f"Select a value (1-{len(choices)}): ")) - 1
                if 0 <= selected < len(choices):
                    return choices[selected]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a number.")

    # Manual input fallback
    prompt = f"\n📝 Enter '{param}'"
    if param_desc:
        prompt += f" ({param_desc})"
    if default_val is not None:
        prompt += f" [default: {default_val}]"
    if is_required:
        prompt += " [REQUIRED]"
    prompt += ": "

    while True:
        user_input = input(prompt).strip()
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
                available_tools = response.tools

                if not available_tools:
                    print("❌ No tools available from the server.")
                    return

                while True:
                    show_tools_menu(available_tools)
                    
                    while True:
                        try:
                            selection = input("\nSelect tool: ").strip()
                            if selection.lower() == 'q':
                                print("👋 Goodbye!")
                                return
                            elif selection.lower() == 'h':
                                print("\n📖 Help:")
                                print("- Enter tool number to run a tool")
                                print("- 'q' to quit")
                                print("- 'h' for this help")
                                print("- When selecting elements, use 's' for screenshot, 'p' for page info")
                                continue
                            
                            selected_index = int(selection) - 1
                            if 0 <= selected_index < len(available_tools):
                                selected_tool = available_tools[selected_index]
                                break
                            else:
                                print(f"❌ Invalid selection. Enter 1-{len(available_tools)}, 'h', or 'q'.")
                        except ValueError:
                            print("❌ Enter a number, 'h' for help, or 'q' to quit.")

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
                                    if value is not None:
                                        args[param] = value
                        else:
                            # Handle other schema formats
                            for param, definition in schema.items():
                                if isinstance(definition, dict):
                                    is_required = definition.get("required", True)
                                    value = await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                                    if value is not None:
                                        args[param] = value
                                else:
                                    value = input(f"\n📝 Enter '{param}': ").strip()
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
                                    # Try to format JSON output nicely
                                    try:
                                        import json
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

                    input("\n🔄 Press Enter to continue...")

    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        logging.error(f"MCP connection error: {e}")

if __name__ == "__main__":
    asyncio.run(run_script())