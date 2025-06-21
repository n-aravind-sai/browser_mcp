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

async def get_user_input_for_param(session, selected_tool, param, definition, is_required=False):
    """Get user input for a parameter with validation and clickable element support"""
    param_desc = definition.get("description", "")
    default_val = definition.get("default")
    choices = definition.get("enum")
    type_hint = definition.get("type", "string")

    # Special handling: auto-fetch clickable elements if relevant
    if "click" in selected_tool.name.lower() and "selector" in param.lower():
        try:
            print("\n🔍 Fetching clickable elements from browser...")
            response = await session.call_tool("get_clickable_elements")
            elements = []
            if hasattr(response, "content") and response.content:
                for part in response.content:
                    if isinstance(part, dict) and "elements" in part:
                        elements = part["elements"]
                        break

            if elements:
                print(f"\n📌 Choose a clickable element for '{param}':")
                for i, el in enumerate(elements):
                    text = el.get("text", "[No text]").strip()
                    selector = el.get("selector", "<unknown>")
                    print(f"{i + 1}. {text}  →  {selector}")
                while True:
                    try:
                        selected = int(input(f"Enter choice (1-{len(elements)}): ")) - 1
                        if 0 <= selected < len(elements):
                            return elements[selected]["selector"]
                        else:
                            print("Invalid selection. Try again.")
                    except ValueError:
                        print("Please enter a valid number.")
            else:
                print("⚠️ No clickable elements found. Fallback to manual input.")
        except Exception as e:
            print(f"❌ Failed to fetch clickable elements: {e}. Fallback to manual input.")

    # Enum-based MCQ
    if choices:
        print(f"\nChoose a value for '{param}' ({param_desc}):")
        for i, choice in enumerate(choices):
            print(f"{i + 1}. {choice}")
        while True:
            try:
                selected = int(input(f"Select a value (1-{len(choices)}): ")) - 1
                if 0 <= selected < len(choices):
                    return choices[selected]
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a number.")

    # Manual input fallback
    prompt = f"\nEnter value for '{param}'"
    if param_desc:
        prompt += f" ({param_desc})"
    if default_val is not None:
        prompt += f" [default: {default_val}]"
    prompt += f" (type: {type_hint})"
    if is_required:
        prompt += " [REQUIRED]"
    prompt += ": "

    while True:
        user_input = input(prompt).strip()
        if user_input:
            try:
                return cast_input_to_type(user_input, type_hint)
            except ValueError as e:
                print(f"Error: {e}")
        elif default_val is not None:
            return cast_input_to_type(str(default_val), type_hint)
        elif not is_required:
            return None
        else:
            print("This field is required. Please enter a value.")

async def run_script():
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"], env=None)

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("Initializing MCP session...")
                await session.initialize()

                print("Fetching available tools...")
                response = await session.list_tools()
                available_tools = response.tools

                if not available_tools:
                    print("No tools available from the server.")
                    return

                print("\n" + "=" * 50)
                print("AVAILABLE TOOLS:")
                print("=" * 50)
                for idx, tool in enumerate(available_tools):
                    print(f"{idx + 1}. {tool.name}")
                    print(f"   Description: {tool.description}")
                    print()

                while True:
                    while True:
                        try:
                            selection = input("Select a tool by number (or 'q' to quit): ").strip()
                            if selection.lower() == 'q':
                                print("Goodbye!")
                                return
                            selected_index = int(selection) - 1
                            if 0 <= selected_index < len(available_tools):
                                selected_tool = available_tools[selected_index]
                                break
                            else:
                                print(f"Invalid selection. Enter 1 to {len(available_tools)}.")
                        except ValueError:
                            print("Enter a number or 'q' to quit.")

                    print(f"\n{'=' * 50}")
                    print(f"CONFIGURING TOOL: {selected_tool.name}")
                    print(f"Description: {selected_tool.description}")
                    print(f"{'=' * 50}")

                    args = {}
                    schema = selected_tool.inputSchema

                    if isinstance(schema, dict) and schema:
                        if "properties" in schema:
                            properties = schema.get("properties", {})
                            required = schema.get("required", [])

                            if not properties:
                                print("This tool requires no parameters.")
                            else:
                                print("Please provide the following parameters:")
                                for param, definition in properties.items():
                                    is_required = param in required
                                    value = await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                                    if value is not None:
                                        args[param] = value
                        elif any(isinstance(v, dict) for v in schema.values()):
                            print("Please provide the following parameters:")
                            for param, definition in schema.items():
                                if isinstance(definition, dict):
                                    is_required = definition.get("required", True)
                                    value = await get_user_input_for_param(session, selected_tool, param, definition, is_required)
                                    if value is not None:
                                        args[param] = value
                                else:
                                    value = input(f"\nEnter value for '{param}': ").strip()
                                    if value:
                                        args[param] = value
                    else:
                        print("This tool requires no parameters.")

                    print(f"\n{'=' * 50}")
                    print(f"EXECUTING: {selected_tool.name}")
                    if args:
                        print(f"Arguments: {args}")
                    print(f"{'=' * 50}")

                    try:
                        result = await session.call_tool(selected_tool.name, arguments=args)

                        print("\nRESULT:")
                        print("-" * 30)
                        if hasattr(result, 'content') and result.content:
                            for content_item in result.content:
                                text = getattr(content_item, "text", None)
                                if text is not None:
                                    print(text)
                                else:
                                    print(content_item)
                        else:
                            print("Tool executed successfully (no output)")

                    except Exception as e:
                        print(f"Error executing tool: {e}")
                        logging.error(f"Tool execution error: {e}")

                    print("\n" + "=" * 50)
                    continue_choice = input("Run another tool? (y/n): ").strip().lower()
                    if continue_choice not in ['y', 'yes']:
                        print("Goodbye!")
                        break

    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        logging.error(f"MCP connection error: {e}")

if __name__ == "__main__":
    print("Starting MCP Browser Automation Client...")
    asyncio.run(run_script())
