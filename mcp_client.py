import asyncio
import logging
import json
import google.generativeai as genai
from dotenv import load_dotenv
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

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

def show_main_menu():
    """Display the main application menu"""
    print("\n" + "=" * 60)
    print("🤖 ENHANCED MCP BROWSER AUTOMATION CLIENT")
    print("=" * 60)
    print("1. 🤖 AI Assistant Mode (Gemini-powered)")
    print("2. 🔧 Manual Tool Selection")
    print("3. 📖 Help")
    print("4. 🚪 Quit")
    print("=" * 60)

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
    print("Commands: [tool number] | 'b' back | 'h' for help")
    
    return visible_tools  # Return filtered list

class GeminiMCPAgent:
    def __init__(self, session, available_tools):
        self.session = session
        self.available_tools = available_tools
        self.visible_tools = [tool for tool in available_tools if tool.name not in HIDDEN_TOOLS]
        self.model = genai.GenerativeModel('models/gemini-1.5-flash')
        self.conversation_history = []
        self.system_prompt = self.create_system_prompt()

    def get_tools_info(self):
        tools_info = []
        for tool in self.visible_tools:
            tool_info = {
                "name": tool.name,
                "description": tool.description,
                "parameters": {}
            }
            schema = getattr(tool, 'inputSchema', {})
            if isinstance(schema, dict) and "properties" in schema:
                properties = schema.get("properties", {})
                required = schema.get("required", [])
                for param, definition in properties.items():
                    param_info = {
                        "type": definition.get("type", "string"),
                        "description": definition.get("description", ""),
                        "required": param in required
                    }
                    if "enum" in definition:
                        param_info["choices"] = definition["enum"]
                    if "default" in definition:
                        param_info["default"] = definition["default"]
                    tool_info["parameters"][param] = param_info
            tools_info.append(tool_info)
        return tools_info

    def create_system_prompt(self):
        tools_info = self.get_tools_info()
        return f"""You are an intelligent browser automation assistant. You have access to these MCP tools for web automation:

{json.dumps(tools_info, indent=2)}

Your role is to:
1. Understand user requests for web automation tasks
2. Plan the sequence of tool calls needed
3. Execute the tools with appropriate parameters
4. Provide clear feedback about what's happening
5. Handle errors gracefully and suggest alternatives

Key guidelines:
- Always explain what you're about to do before executing tools
- For navigation: use navigate_to tool with full URLs
- For clicking: use click_element with CSS selectors
- For form filling: use fill_form with selectors and values
- For content extraction: use extract_text with selectors
- For page analysis: use get_page_info and get_clickable_elements
- Take screenshots with take_screenshot when visual confirmation is needed

When users ask to:
- "Go to [website]" → Use navigate_to
- "Click [element]" → Use get_clickable_elements first, then click_element
- "Fill out [form]" → Use get_form_elements first, then fill_form
- "Get text from [element]" → Use extract_text
- "What's on this page?" → Use get_page_info
- "Take a picture" → Use take_screenshot

Always provide step-by-step explanations of your actions and ask for confirmation on destructive actions.

Respond in this format:
1. First, explain what you understand from the user's request
2. Outline your planned approach
3. Execute the tools one by one
4. Provide feedback on results
5. Ask if they need anything else

If you need to use a tool, format it as:
TOOL_CALL: tool_name
PARAMETERS: {{parameter: value}}

Be conversational, helpful, and proactive in suggesting next steps.
"""

    async def get_current_page_context(self):
        try:
            page_info_result = await self.session.call_tool("get_page_info")
            page_info = {}
            if hasattr(page_info_result, 'content') and page_info_result.content:
                for content_item in page_info_result.content:
                    if hasattr(content_item, 'text'):
                        raw_text = content_item.text.strip()
                        
                        # 🧪 Added debug log
                        print(f"[DEBUG] Raw page_info text: {raw_text[:300]}...")  # Print first 300 characters
                        
                        try:
                            # ✅ Attempt JSON parsing
                            page_info = json.loads(raw_text)
                        except json.JSONDecodeError:
                            # 🛡️ Fallback: deliver raw text so Gemini can work with it
                            page_info = {"raw_content": raw_text}
            return page_info
        except Exception as e:
            return {"error": f"Failed to get page context: {str(e)}"}


    async def execute_tool_call(self, tool_name, parameters):
        try:
            tool = next((t for t in self.visible_tools if t.name == tool_name), None)
            if not tool:
                return {"error": f"Tool '{tool_name}' not found"}
            print(f"🔧 Executing: {tool_name}")
            if parameters:
                print(f"📊 Parameters: {parameters}")
            result = await self.session.call_tool(tool_name, arguments=parameters)
            result_text = ""
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        result_text += content_item.text
            return {"success": True, "result": result_text}
        except Exception as e:
            return {"error": f"Failed to execute {tool_name}: {str(e)}"}

    def parse_gemini_response(self, response_text):
        import re
        tool_calls = []
        pattern = r'TOOL_CALL:\s*(\w+)\s*PARAMETERS:\s*(\{.*?\})(?=\nTOOL_CALL:|$)'
        matches = re.findall(pattern, response_text, re.DOTALL)
        for tool_name, param_json in matches:
            try:
                params = json.loads(param_json)
            except json.JSONDecodeError:
                params = {}
            tool_calls.append((tool_name.strip(), params))
        return tool_calls, response_text

    async def handle_user_request(self, user_input):
        try:
            page_context = await self.get_current_page_context()
            context_msg = f"Current page context: {json.dumps(page_context, indent=2)}\n\nUser request: {user_input}"
            self.conversation_history.append(f"User: {user_input}")
            conversation_context = "\n".join(self.conversation_history[-10:])
            full_prompt = f"{self.system_prompt}\n\nConversation History:\n{conversation_context}\n\nCurrent Context:\n{context_msg}"
            print("🤖 Thinking...")
            chat = self.model.start_chat(history=[])
            response = await chat.send_message_async(full_prompt)
            if not response.text:
                print("❌ No response from Gemini")
                return
            tool_calls, explanation = self.parse_gemini_response(response.text)
            print(f"\n🤖 Gemini: {explanation}")
            if tool_calls:
                print(f"\n🔧 Executing {len(tool_calls)} tool call(s)...")
                for tool_name, parameters in tool_calls:
                    result = await self.execute_tool_call(tool_name, parameters)
                    if result.get("error"):
                        print(f"❌ Error: {result['error']}")
                        self.conversation_history.append(f"Assistant: Error executing {tool_name}: {result['error']}")
                    else:
                        print(f"✅ {tool_name} completed successfully")
                        if result.get("result"):
                            print(f"📋 Result: {result['result'][:200]}...")
                        self.conversation_history.append(f"Assistant: Successfully executed {tool_name}")
            self.conversation_history.append(f"Assistant: {explanation}")
        except Exception as e:
            print(f"❌ Error processing request: {e}")
            logging.error(f"Gemini processing error: {e}")


async def get_clickable_elements_data(session):
    try:
        response = await session.call_tool("get_clickable_elements")
        if hasattr(response, "content") and response.content:
            for content_item in response.content:
                if hasattr(content_item, "text"):
                    try:
                        data = json.loads(content_item.text)
                        return data.get("elements", []), data.get("error")
                    except json.JSONDecodeError:
                        return [], content_item.text
        return [], "No response content"
    except Exception as e:
        return [], f"Failed to fetch elements: {e}"

async def get_user_input_for_param(session, selected_tool, param, definition, is_required=False):
    param_desc = definition.get("description", "")
    default_val = definition.get("default")
    choices = definition.get("enum")
    type_hint = definition.get("type", "string")

    if "click" in selected_tool.name.lower() and "selector" in param.lower():
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
                type_info = f" ({elem_type})" if elem_type else ""
                print(f"{i + 1:2d}. [{tag.upper()}{type_info}] {text}\n    Selector: {selector}")
            print("=" * 80)
            while True:
                user_input = input(f"Choose (1-{len(elements)}) | 'm' manual: ").strip()
                if user_input.lower() == 'm':
                    break
                try:
                    selected = int(user_input) - 1
                    if 0 <= selected < len(elements):
                        return elements[selected]["selector"]
                    else:
                        print(f"❌ Invalid selection. Enter 1-{len(elements)} or 'm'.")
                except ValueError:
                    print("❌ Please enter a valid number or 'm'.")

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

async def manual_tool_mode(session, all_tools):
    while True:
        visible_tools = show_tools_menu(all_tools)
        while True:
            try:
                selection = input("\nSelect tool: ").strip()
                if selection.lower() == 'b':
                    return
                elif selection.lower() == 'h':
                    print("\n📖 Help:\n- Enter tool number to run a tool\n- 'b' to go back to main menu\n- 'h' for this help")
                    continue
                selected_index = int(selection) - 1
                if 0 <= selected_index < len(visible_tools):
                    selected_tool = visible_tools[selected_index]
                    break
                else:
                    print(f"❌ Invalid selection. Enter 1-{len(visible_tools)}, 'h', or 'b'.")
            except ValueError:
                print("❌ Enter a number, 'h' for help, or 'b' to go back.")

        print(f"\n🔧 CONFIGURING: {selected_tool.name}\n📝 Description: {selected_tool.description}\n" + "-" * 50)
        args = {}
        schema = selected_tool.inputSchema
        if isinstance(schema, dict) and schema:
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
            print("✅ This tool requires no parameters.")

        print(f"\n⚡ EXECUTING: {selected_tool.name}")
        if args:
            print(f"📊 Arguments: {args}")
        print("-" * 50)
        try:
            result = await session.call_tool(selected_tool.name, arguments=args)
            print("📋 RESULT:")
            for content_item in getattr(result, "content", []):
                text = getattr(content_item, "text", None)
                if text is not None:
                    try:
                        data = json.loads(text)
                        print(json.dumps(data, indent=2))
                    except (json.JSONDecodeError, TypeError):
                        print(text)
                else:
                    print(content_item)
        except Exception as e:
            print(f"❌ Error executing tool: {e}")
            logging.error(f"Tool execution error: {e}")
        input("\n🔄 Press Enter to continue...")

async def ai_assistant_mode(session, all_tools):
    print("\n🤖 Starting AI Assistant Mode...")
    print("Type your requests in natural language. Examples:")
    print("- 'Go to google.com'")
    print("- 'Click the search button'")
    print("- 'Fill out the login form'")
    print("- 'Take a screenshot'")
    print("- 'What's on this page?'")
    print("\nType 'back' to return to main menu.\n")
    if not os.getenv('GEMINI_API_KEY'):
        print("❌ GEMINI_API_KEY not found in environment variables.")
        print("Please add your Gemini API key to your .env file:")
        print("GEMINI_API_KEY=your_api_key_here")
        input("Press Enter to continue...")
        return
    agent = GeminiMCPAgent(session, all_tools)
    while True:
        try:
            user_input = input("🗣️ You: ").strip()
            if user_input.lower() in ['back', 'exit', 'quit']:
                break
            if not user_input:
                continue
            await agent.handle_user_request(user_input)
        except KeyboardInterrupt:
            print("\n\n👋 Returning to main menu...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            logging.error(f"AI assistant error: {e}")

async def run_script():
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"], env=None)
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("🚀 Starting Enhanced MCP Browser Automation Client with AI...")
                print("⏳ Initializing MCP session...")
                await session.initialize()
                print("📋 Fetching available tools...")
                response = await session.list_tools()
                all_tools = response.tools
                if not all_tools:
                    print("❌ No tools available from the server.")
                    return
                while True:
                    show_main_menu()
                    try:
                        choice = input("\nSelect option (1-4): ").strip()
                        if choice == '1':
                            await ai_assistant_mode(session, all_tools)
                        elif choice == '2':
                            await manual_tool_mode(session, all_tools)
                        elif choice == '3':
                            print("\n📖 Help:")
                            print("1. AI Assistant Mode: Use natural language to control browser")
                            print("2. Manual Tool Selection: Direct tool access")
                            print("3. This help menu")
                            print("4. Quit the application")
                            print("\nFor AI mode, you need a GEMINI_API_KEY in your .env file")
                            input("Press Enter to continue...")
                        elif choice == '4':
                            print("👋 Goodbye!")
                            return
                        else:
                            print("❌ Invalid choice. Please enter 1, 2, 3, or 4.")
                    except KeyboardInterrupt:
                        print("\n👋 Goodbye!")
                        return
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        logging.error(f"MCP connection error: {e}")

if __name__ == "__main__":
    asyncio.run(run_script())
