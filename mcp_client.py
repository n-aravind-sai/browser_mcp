import asyncio
import logging
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

def cast_input_to_type(value: str, type_hint: str):
    """Convert string input to the appropriate type based on type hint"""
    try:
        if type_hint == "integer":
            return int(value)
        elif type_hint == "number":
            return float(value)
        elif type_hint == "boolean":
            return value.lower() in ["true", "1", "yes", "y"]
        else:
            return value  # default to string
    except ValueError:
        raise ValueError(f"Invalid input '{value}' for expected type {type_hint}")

def get_user_input_for_param(param: str, definition: dict, is_required: bool = False):
    """Get user input for a parameter with proper validation"""
    param_desc = definition.get("description", "")
    default_val = definition.get("default")
    choices = definition.get("enum")
    type_hint = definition.get("type", "string")

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
    else:
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
                    continue
            elif default_val is not None:
                return cast_input_to_type(str(default_val), type_hint)
            elif not is_required:
                return None  # Optional parameter with no input
            else:
                print("This field is required. Please enter a value.")

async def run_script():
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        env=None
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                print("Initializing MCP session...")
                await session.initialize()
                
                # List available tools
                print("Fetching available tools...")
                response = await session.list_tools()
                available_tools = response.tools

                if not available_tools:
                    print("No tools available from the server.")
                    return

                print("\n" + "="*50)
                print("AVAILABLE TOOLS:")
                print("="*50)
                for idx, tool in enumerate(available_tools):
                    print(f"{idx + 1}. {tool.name}")
                    print(f"   Description: {tool.description}")
                    print()

                # Main tool execution loop
                while True:
                    # Tool selection
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
                                print(f"Invalid selection. Please enter a number between 1 and {len(available_tools)}.")
                        except ValueError:
                            print("Invalid input. Please enter a number or 'q' to quit.")

                    # Prepare arguments for the selected tool
                    print(f"\n" + "="*50)
                    print(f"CONFIGURING TOOL: {selected_tool.name}")
                    print(f"Description: {selected_tool.description}")
                    print("="*50)

                    args = {}
                    schema = selected_tool.inputSchema

                    if isinstance(schema, dict) and schema:
                        # Handle JSON Schema format
                        if "properties" in schema:
                            properties = schema.get("properties", {})
                            required = schema.get("required", [])
                            
                            if not properties:
                                print("This tool requires no parameters.")
                            else:
                                print("Please provide the following parameters:")
                                for param, definition in properties.items():
                                    is_required = param in required
                                    value = get_user_input_for_param(param, definition, is_required)
                                    if value is not None:
                                        args[param] = value
                        
                        # Handle direct parameter definitions (fallback)
                        elif any(isinstance(v, dict) for v in schema.values()):
                            print("Please provide the following parameters:")
                            for param, definition in schema.items():
                                if isinstance(definition, dict):
                                    is_required = definition.get("required", True)
                                    value = get_user_input_for_param(param, definition, is_required)
                                    if value is not None:
                                        args[param] = value
                                else:
                                    # Simple parameter without detailed schema
                                    value = input(f"\nEnter value for '{param}': ").strip()
                                    if value:
                                        args[param] = value
                    else:
                        print("This tool requires no parameters.")

                    # Execute the tool
                    print(f"\n" + "="*50)
                    print(f"EXECUTING: {selected_tool.name}")
                    if args:
                        print(f"Arguments: {args}")
                    print("="*50)
                    
                    try:
                        result = await session.call_tool(selected_tool.name, arguments=args)
                        
                        print("\nRESULT:")
                        print("-" * 30)
                        if hasattr(result, 'content') and result.content:
                            for content_item in result.content:
                                if hasattr(content_item, 'text'):
                                    print(content_item.text)
                                else:
                                    print(content_item)
                        else:
                            print("Tool executed successfully (no output)")
                            
                    except Exception as e:
                        print(f"Error executing tool: {e}")
                        logging.error(f"Tool execution error: {e}")

                    # Ask if user wants to run another tool
                    print("\n" + "="*50)
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