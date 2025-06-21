import asyncio
import logging
import json
import os
import re
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    import google.generativeai as genai
except ImportError:
    print("❌ Error: google-generativeai not installed. Run: pip install google-generativeai")
    exit(1)

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    print(f"❌ Error configuring Gemini: {e}")
    print("💡 Try: pip install --upgrade google-generativeai")
    exit(1)

class ToolMatcher:
    """Maps natural language requests to MCP tools"""
    
    def __init__(self, available_tools):
        self.available_tools = available_tools
        self.tool_mappings = self._create_tool_mappings()
    
    def _create_tool_mappings(self):
        """Create mappings between natural language patterns and tools"""
        mappings = {}
        
        for tool in self.available_tools:
            tool_name = tool.name.lower()
            
            # Browser control mappings
            if 'start' in tool_name and 'browser' in tool_name:
                mappings['start_browser'] = {
                    'tool': tool,
                    'keywords': ['start browser', 'open browser', 'launch browser', 'begin session'],
                    'extract_params': self._extract_start_browser_params
                }
            elif 'stop' in tool_name and 'browser' in tool_name:
                mappings['stop_browser'] = {
                    'tool': tool,
                    'keywords': ['stop browser', 'close browser', 'end session', 'quit browser'],
                    'extract_params': lambda x: {}
                }
            
            # Navigation mappings
            elif 'navigate' in tool_name or 'goto' in tool_name:
                mappings['navigate'] = {
                    'tool': tool,
                    'keywords': ['go to', 'navigate to', 'visit', 'open page', 'load page'],
                    'extract_params': self._extract_url_params
                }
            
            # Interaction mappings
            elif 'click' in tool_name:
                mappings['click'] = {
                    'tool': tool,
                    'keywords': ['click', 'click on', 'press', 'tap'],
                    'extract_params': self._extract_selector_params
                }
            elif 'fill' in tool_name or 'form' in tool_name:
                mappings['fill'] = {
                    'tool': tool,
                    'keywords': ['fill', 'type', 'enter text', 'input', 'write'],
                    'extract_params': self._extract_fill_params
                }
            
            # Data extraction mappings
            elif 'text' in tool_name or 'extract' in tool_name:
                mappings['extract'] = {
                    'tool': tool,
                    'keywords': ['get text', 'extract text', 'read', 'fetch text'],
                    'extract_params': self._extract_selector_params
                }
            elif 'screenshot' in tool_name:
                mappings['screenshot'] = {
                    'tool': tool,
                    'keywords': ['screenshot', 'capture', 'take picture', 'save image'],
                    'extract_params': self._extract_screenshot_params
                }
            
            # JavaScript and waiting
            elif 'javascript' in tool_name or 'evaluate' in tool_name:
                mappings['javascript'] = {
                    'tool': tool,
                    'keywords': ['run javascript', 'execute js', 'evaluate'],
                    'extract_params': self._extract_js_params
                }
            elif 'wait' in tool_name:
                mappings['wait'] = {
                    'tool': tool,
                    'keywords': ['wait for', 'wait until', 'await element'],
                    'extract_params': self._extract_wait_params
                }
        
        return mappings
    
    def _extract_start_browser_params(self, text):
        """Extract parameters for start_browser"""
        params = {}
        if 'headless' in text.lower() or 'background' in text.lower():
            params['headless'] = True
        elif 'visible' in text.lower() or 'show' in text.lower():
            params['headless'] = False
        return params
    
    def _extract_url_params(self, text):
        """Extract URL from text"""
        # Look for URLs in the text
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        if urls:
            return {'url': urls[0]}
        
        # Look for domain-like patterns
        domain_pattern = r'(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
        domains = re.findall(domain_pattern, text)
        if domains:
            url = domains[0]
            if not url.startswith('http'):
                url = 'https://' + url
            return {'url': url}
        
        return {}
    
    def _extract_selector_params(self, text):
        """Extract CSS selector from text"""
        # Look for quoted selectors
        quoted_pattern = r'["\']([^"\']+)["\']'
        matches = re.findall(quoted_pattern, text)
        if matches:
            return {'selector': matches[0]}
        
        # Look for common selector patterns
        if '#' in text:
            parts = text.split('#')
            if len(parts) > 1:
                selector = '#' + parts[1].split()[0]
                return {'selector': selector}
        
        if 'class' in text.lower():
            # Try to extract class name
            words = text.split()
            for i, word in enumerate(words):
                if word.lower() == 'class' and i + 1 < len(words):
                    return {'selector': '.' + words[i + 1]}
        
        return {}
    
    def _extract_fill_params(self, text):
        """Extract selector and value for fill operations"""
        params = self._extract_selector_params(text)
        
        # Try to extract the value to fill
        with_pattern = r'with\s+["\']([^"\']+)["\']'
        matches = re.findall(with_pattern, text)
        if matches:
            params['value'] = matches[0]
        
        return params
    
    def _extract_screenshot_params(self, text):
        """Extract screenshot path"""
        # Look for file paths or names
        path_pattern = r'["\']([^"\']*\.png)["\']'
        matches = re.findall(path_pattern, text)
        if matches:
            return {'path': matches[0]}
        
        # Look for "save as" or "save to" patterns
        save_pattern = r'save (?:as|to) ([a-zA-Z0-9_-]+\.png)'
        matches = re.findall(save_pattern, text, re.IGNORECASE)
        if matches:
            return {'path': matches[0]}
        
        return {}
    
    def _extract_js_params(self, text):
        """Extract JavaScript code"""
        # Look for quoted JavaScript
        js_pattern = r'["\']([^"\']+)["\']'
        matches = re.findall(js_pattern, text)
        if matches:
            return {'expression': matches[0]}
        
        return {}
    
    def _extract_wait_params(self, text):
        """Extract wait parameters"""
        params = self._extract_selector_params(text)
        
        # Extract timeout if specified
        timeout_pattern = r'(\d+)\s*(?:seconds?|ms|milliseconds?)'
        matches = re.findall(timeout_pattern, text)
        if matches:
            timeout = int(matches[0])
            if 'second' in text:
                timeout *= 1000  # Convert to milliseconds
            params['timeout'] = timeout
        
        return params
    
    def match_tool(self, user_input):
        """Match user input to a tool and extract parameters"""
        if not self.tool_mappings:
            return None, {}
            
        user_input_lower = user_input.lower()
        
        best_match = None
        best_score = 0
        
        for tool_key, mapping in self.tool_mappings.items():
            score = 0
            for keyword in mapping['keywords']:
                if keyword in user_input_lower:
                    score += len(keyword)  # Longer matches get higher scores
            
            if score > best_score:
                best_score = score
                best_match = mapping
        
        if best_match and best_score > 0:
            try:
                params = best_match['extract_params'](user_input)
                return best_match['tool'], params
            except Exception as e:
                print(f"⚠️ Error extracting parameters: {e}")
                return best_match['tool'], {}
        
        return None, {}

class GeminiMCPClient:
    """MCP Client with Gemini AI integration"""
    
    def __init__(self):
        self.client_session = None
        self.available_tools = []
        self.tool_matcher = None
        self.stdio_context = None
        
    async def initialize(self):
        """Initialize the MCP session and tools"""
        server_params = StdioServerParameters(
            command="python",
            args=["mcp_server.py"],
            env=None
        )
        
        try:
            print("🔄 Starting MCP server...")
            self.stdio_context = stdio_client(server_params)
            
            # Add timeout to prevent hanging
            print("🔄 Connecting to server...")
            read_stream, write_stream = await asyncio.wait_for(
                self.stdio_context.__aenter__(), 
                timeout=10.0
            )
            
            print("🔄 Creating client session...")
            self.client_session = ClientSession(read_stream, write_stream)
            
            print("🔄 Initializing session...")
            # Add timeout for initialization
            await asyncio.wait_for(
                self.client_session.initialize(), 
                timeout=10.0
            )
            
            print("🔄 Listing available tools...")
            # Get available tools with timeout
            response = await asyncio.wait_for(
                self.client_session.list_tools(),
                timeout=5.0
            )
            self.available_tools = response.tools
            self.tool_matcher = ToolMatcher(self.available_tools)
            
            print("✅ MCP session initialized with Gemini AI integration")
            print(f"🛠️ Available tools: {[tool.name for tool in self.available_tools]}")
            
        except asyncio.TimeoutError:
            print("❌ Timeout error: Server took too long to respond")
            print("💡 Check if:")
            print("   - mcp_server.py exists in current directory")
            print("   - All dependencies are installed (fastmcp, playwright)")
            print("   - Python can execute mcp_server.py directly")
            print("   - Try running: python mcp_server.py (should not exit immediately)")
            raise
        except Exception as e:
            print(f"❌ Error initializing MCP session: {e}")
            print(f"   Error type: {type(e).__name__}")
            print(f"💡 Debug steps:")
            print("   1. Test server independently: python mcp_server.py")
            print("   2. Check dependencies: pip list | grep -E '(fastmcp|playwright|mcp)'")
            print("   3. Verify file exists: ls -la mcp_server.py")
            raise
    
    async def process_user_input(self, user_input):
        """Process user input - either execute tool or get AI response"""
        
        if not self.tool_matcher:
            return "❌ Error: Tool matcher not initialized"
        
        # First, try to match input to a specific tool
        matched_tool, extracted_params = self.tool_matcher.match_tool(user_input)
        
        if matched_tool:
            return await self._execute_tool(matched_tool, extracted_params, user_input)
        else:
            # No specific tool matched, use Gemini for general response
            return await self._get_ai_response(user_input)
    
    async def _execute_tool(self, tool, params, original_input):
        """Execute a matched tool with extracted parameters"""
        
        # If we're missing required parameters, ask Gemini to help extract them
        schema = tool.inputSchema
        if isinstance(schema, dict) and "properties" in schema:
            required_params = schema.get("required", [])
            missing_params = [p for p in required_params if p not in params]
            
            if missing_params:
                # Use Gemini to extract missing parameters
                gemini_params = await self._extract_missing_params(tool, missing_params, original_input)
                params.update(gemini_params)
        
        try:
            print(f"\n🤖 Executing tool: {tool.name}")
            if params:
                print(f"📋 Parameters: {params}")
            
            result = await self.client_session.call_tool(tool.name, arguments=params)
            
            response = "✅ Tool executed successfully!\n"
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    # Fixed: Proper handling of different content types
                    if hasattr(content_item, 'text'):
                        response += f"📄 Result: {content_item.text}"
                    elif hasattr(content_item, 'type') and content_item.type == 'text':
                        # Handle different possible text attributes
                        text_content = getattr(content_item, 'text', None)
                        if text_content is None:
                            # Try other possible attributes for text content
                            for attr in ['content', 'value', 'data']:
                                if hasattr(content_item, attr):
                                    text_content = getattr(content_item, attr)
                                    break
                        response += f"📄 Result: {text_content or str(content_item)}"
                    else:
                        response += f"📄 Result: {str(content_item)}"
            else:
                # Handle case where result doesn't have content or content is empty
                response += f"📄 Result: {str(result)}"
            
            return response
            
        except Exception as e:
            error_msg = f"❌ Error executing {tool.name}: {str(e)}"
            print(error_msg)
            
            # Try to get a helpful AI response about the error
            ai_help = await self._get_error_help(tool.name, str(e), original_input)
            return f"{error_msg}\n\n🤖 AI Suggestion: {ai_help}"
    
    async def _extract_missing_params(self, tool, missing_params, user_input):
        """Use Gemini to extract missing parameters from user input"""
        
        prompt = f"""
        The user wants to use the tool '{tool.name}' with the following description:
        {tool.description}
        
        User input: "{user_input}"
        
        Missing required parameters: {missing_params}
        
        Tool schema: {tool.inputSchema}
        
        Please extract the missing parameters from the user input and return them as a JSON object.
        If you cannot extract a parameter, set it to null.
        Only return the JSON object, no other text.
        """
        
        try:
            response = model.generate_content(prompt)
            # Try to parse JSON from response
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"⚠️ Error extracting parameters with Gemini: {e}")
        
        return {}
    
    async def _get_ai_response(self, user_input):
        """Get AI response for general queries"""
        
        # Create context about available browser automation tools
        tools_context = "Available browser automation tools:\n"
        for tool in self.available_tools:
            tools_context += f"- {tool.name}: {tool.description}\n"
        
        prompt = f"""
        You are a helpful assistant for browser automation. The user has access to these tools:
        
        {tools_context}
        
        User input: "{user_input}"
        
        If the user is asking about browser automation but their request doesn't clearly map to a specific tool,
        provide helpful guidance about what they can do or ask clarifying questions.
        
        If the user is asking something unrelated to browser automation, respond naturally but briefly.
        
        Be conversational and helpful.
        """
        
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'max_output_tokens': 500,
                }
            )
            return f"🤖 AI Assistant: {response.text}"
        except Exception as e:
            return f"❌ Error getting AI response: {str(e)}"
    
    async def _get_error_help(self, tool_name, error, user_input):
        """Get AI help for tool execution errors"""
        
        prompt = f"""
        The user tried to use the browser automation tool '{tool_name}' but got an error:
        Error: {error}
        
        Original user input: "{user_input}"
        
        Please provide a helpful suggestion about what might have gone wrong and how to fix it.
        Keep it concise and actionable.
        """
        
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,
                    'max_output_tokens': 200,
                }
            )
            return response.text
        except Exception as e:
            return "Unable to provide AI assistance for this error."
    
    async def run_interactive_session(self):
        """Run interactive chat session"""
        
        print("\n" + "="*60)
        print("🚀 GEMINI-POWERED BROWSER AUTOMATION CLIENT")
        print("="*60)
        print("💬 You can:")
        print("   • Use natural language (e.g., 'open google.com')")
        print("   • Ask questions about browser automation")
        print("   • Get AI assistance with errors")
        print("   • Type 'help' for available tools")
        print("   • Type 'quit' to exit")
        print("="*60)
        
        while True:
            try:
                user_input = input("\n💭 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    print("\n🛠️ Available Tools:")
                    for tool in self.available_tools:
                        print(f"   • {tool.name}: {tool.description}")
                    continue
                
                if not user_input:
                    continue
                
                # Process the input
                response = await self.process_user_input(user_input)
                print(f"\n{response}")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                logging.error(f"Interactive session error: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.client_session:
            # Try to stop browser if it was started
            try:
                for tool in self.available_tools:
                    if 'stop' in tool.name.lower() and 'browser' in tool.name.lower():
                        await self.client_session.call_tool(tool.name, arguments={})
                        print("🛑 Browser stopped")
                        break
            except Exception as e:
                print(f"⚠️ Warning during browser cleanup: {e}")
        
        # Cleanup stdio context
        if self.stdio_context:
            try:
                await self.stdio_context.__aexit__(None, None, None)
                print("🧹 MCP connection closed")
            except Exception as e:
                print(f"⚠️ Warning during MCP cleanup: {e}")
        
        # Reset all attributes
        self.client_session = None
        self.stdio_context = None

async def main():
    """Main function"""
    client = GeminiMCPClient()
    
    try:
        print("🔍 Pre-flight checks...")
        
        # Check if server file exists
        if not os.path.exists("mcp_server.py"):
            print("❌ mcp_server.py not found in current directory!")
            print(f"   Current directory: {os.getcwd()}")
            print(f"   Files in directory: {os.listdir('.')}")
            return
        
        print("✅ Server file found")
        
        # Test if we can import required modules
        try:
            import fastmcp
            print("✅ fastmcp available")
        except ImportError:
            print("❌ fastmcp not installed. Run: pip install fastmcp")
            return
            
        try:
            import playwright
            print("✅ playwright available")
        except ImportError:
            print("❌ playwright not installed. Run: pip install playwright")
            return
        
        await client.initialize()
        await client.run_interactive_session()
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except asyncio.TimeoutError:
        print("\n❌ Operation timed out")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        print(f"   Traceback:\n{traceback.format_exc()}")
        logging.error(f"Main error: {e}")
    finally:
        print("🧹 Cleaning up...")
        await client.cleanup()

if __name__ == "__main__":
    print("🔧 Starting Gemini-powered MCP Browser Automation Client...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logging.error(f"Fatal error: {e}")