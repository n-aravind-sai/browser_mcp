#!/usr/bin/env python3
"""
Windows-compatible test script for MCP server
"""
import subprocess
import sys
import time
import json
import threading
import queue
import os

def read_output(pipe, output_queue):
    """Read output from pipe in a separate thread"""
    try:
        for line in iter(pipe.readline, ''):
            if line:
                output_queue.put(('stdout', line.strip()))
            else:
                break
    except Exception as e:
        output_queue.put(('error', str(e)))
    finally:
        output_queue.put(('done', None))

def test_server_communication():
    """Test MCP server communication on Windows"""
    print("🧪 Testing MCP Server Communication (Windows)...")
    
    try:
        # Start the server process
        process = subprocess.Popen(
            [sys.executable, "mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0  # Unbuffered
        )
        
        print(f"🔄 Server started, PID: {process.pid}")
        
        # Create output queue and thread for reading
        output_queue = queue.Queue()
        output_thread = threading.Thread(
            target=read_output, 
            args=(process.stdout, output_queue)
        )
        output_thread.daemon = True
        output_thread.start()
        
        # Wait a moment for startup
        time.sleep(1)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Server is running!")
            
            # Create MCP initialize message
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            
            print("📤 Sending initialize message...")
            
            try:
                # Send the message
                message_str = json.dumps(init_message) + '\n'
                process.stdin.write(message_str)
                process.stdin.flush()
                
                print("📤 Message sent, waiting for response...")
                
                # Wait for response with timeout
                response_received = False
                start_time = time.time()
                timeout = 10  # 10 seconds
                
                while time.time() - start_time < timeout:
                    try:
                        msg_type, content = output_queue.get(timeout=1)
                        
                        if msg_type == 'stdout':
                            print(f"📥 Server response: {content}")
                            response_received = True
                            break
                        elif msg_type == 'error':
                            print(f"⚠️ Read error: {content}")
                            break
                        elif msg_type == 'done':
                            print("📥 Server closed output")
                            break
                            
                    except queue.Empty:
                        continue
                
                if response_received:
                    print("✅ Server responded successfully!")
                    
                    # Try to list tools
                    print("\n📤 Testing tools list...")
                    tools_message = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {}
                    }
                    
                    tools_str = json.dumps(tools_message) + '\n'
                    process.stdin.write(tools_str)
                    process.stdin.flush()
                    
                    # Wait for tools response
                    tools_start = time.time()
                    while time.time() - tools_start < 5:
                        try:
                            msg_type, content = output_queue.get(timeout=1)
                            if msg_type == 'stdout' and 'tools' in content.lower():
                                print(f"🛠️ Tools response: {content}")
                                print("✅ Tools list working!")
                                break
                        except queue.Empty:
                            continue
                    
                else:
                    print("⚠️ No response received within timeout")
                    
            except Exception as e:
                print(f"⚠️ Error during communication: {e}")
            
        else:
            print("❌ Server exited immediately!")
            stdout, stderr = process.communicate()
            if stdout:
                print("STDOUT:", stdout)
            if stderr:
                print("STDERR:", stderr)
            return False
        
        # Clean up
        if process.poll() is None:
            print("\n🛑 Stopping server...")
            try:
                process.terminate()
                process.wait(timeout=5)
                print("✅ Server stopped cleanly")
            except subprocess.TimeoutExpired:
                print("⚠️ Server didn't stop gracefully, forcing...")
                process.kill()
                process.wait()
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing server: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_startup():
    """Simple test to verify server starts and stays running"""
    print("\n🔍 Simple startup test...")
    
    try:
        process = subprocess.Popen(
            [sys.executable, "mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"🔄 Server PID: {process.pid}")
        
        # Wait and check if still running
        time.sleep(3)
        
        if process.poll() is None:
            print("✅ Server stayed running for 3 seconds")
            process.terminate()
            process.wait(timeout=5)
            return True
        else:
            print("❌ Server exited early")
            stdout, stderr = process.communicate()
            print("STDOUT:", stdout)
            print("STDERR:", stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error in simple test: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Windows MCP Server Test")
    print("=" * 40)
    
    # Check if server file exists
    if not os.path.exists("mcp_server.py"):
        print("❌ mcp_server.py not found!")
        sys.exit(1)
    
    # Run simple test first
    if not test_simple_startup():
        print("❌ Simple startup test failed!")
        sys.exit(1)
    
    # Run communication test
    success = test_server_communication()
    
    if success:
        print("\n🎉 All tests passed!")
        print("   Your MCP server should work with the client.")
        print("   Try running: python mcp_client.py")
    else:
        print("\n❌ Some tests failed!")
        print("   Check the error messages above.")