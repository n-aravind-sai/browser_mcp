# Browser Automation MCP (Model Context Protocol) Server

A powerful browser automation server built using the Model Context Protocol (MCP) framework and Playwright. This project allows you to control a web browser programmatically through a clean, interactive command-line interface.

## 🚀 Features

- **Interactive Browser Control**: Start/stop browsers, navigate to websites, interact with elements
- **Visual & Headless Modes**: Choose between visible browser windows or invisible background operation
- **Web Scraping**: Extract text, take screenshots, evaluate JavaScript
- **Form Automation**: Fill forms, click buttons, wait for elements to load
- **Real-time Interaction**: Watch browser actions in real-time (when not in headless mode)
- **Error Handling**: Comprehensive error handling with detailed feedback

## 🛠️ Available Tools

1. **start_browser** - Initialize a browser session (headless or visible)
2. **stop_browser** - Clean shutdown of browser session
3. **navigate_to** - Navigate to any URL
4. **click_element** - Click on elements using CSS selectors
5. **fill_form** - Fill form fields with text
6. **extract_text** - Extract text content from elements
7. **take_screenshot** - Capture screenshots of the current page
8. **evaluate_javascript** - Execute custom JavaScript code
9. **wait_for_element** - Wait for elements to appear on the page

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## 🔧 Installation

1. **Clone or download the project files:**
   ```bash
   # Make sure you have these files:
   # - mcp_server.py
   # - mcp_client.py (or client.py)
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install required packages:**
   ```bash
   pip install mcp playwright python-dotenv
   ```

4. **Install Playwright browser:**
   ```bash
   playwright install chromium
   ```

## 🚀 Quick Start

1. **Start the interactive client:**
   ```bash
   python mcp_client.py
   ```

2. **Start a browser session:**
   - Select tool `1` (start_browser)
   - Choose `false` for headless to see the browser window
   - Choose `true` for headless to run invisibly

3. **Navigate to a website:**
   - Select tool `3` (navigate_to)
   - Enter URL: `https://example.com`

4. **Take a screenshot:**
   - Select tool `7` (take_screenshot)
   - Press Enter for default filename or specify custom path

5. **Continue with more operations or quit:**
   - Type `y` to run another tool
   - Type `n` or `q` to exit

## 💡 Usage Examples

### Basic Web Scraping
```
1. start_browser (headless: true)
2. navigate_to (url: https://news.ycombinator.com)
3. extract_text (selector: .titleline > a)
4. take_screenshot (path: hackernews.png)
```

### Form Automation
```
1. start_browser (headless: false)
2. navigate_to (url: https://example.com/login)
3. fill_form (selector: #username, value: myuser)
4. fill_form (selector: #password, value: mypass)
5. click_element (selector: #login-button)
```

### Dynamic Content Handling
```
1. start_browser (headless: false)
2. navigate_to (url: https://example.com)
3. click_element (selector: .load-more-button)
4. wait_for_element (selector: .new-content, timeout: 5000)
5. extract_text (selector: .new-content)
```

## 🎯 CSS Selectors Guide

Understanding CSS selectors is crucial for element interaction:

- **ID**: `#my-id` (elements with id="my-id")
- **Class**: `.my-class` (elements with class="my-class")
- **Tag**: `button` (all button elements)
- **Attribute**: `[type="submit"]` (elements with type="submit")
- **Combination**: `form .submit-button` (class submit-button inside form)

### Common Selectors
- Login forms: `#username`, `#password`, `[type="submit"]`
- Navigation: `.nav-item`, `.menu-link`
- Content: `.article-title`, `.post-content`
- Buttons: `button`, `.btn`, `[role="button"]`

## ⚙️ Configuration Options

### Browser Modes
- **Headless (true)**: Faster, uses less resources, good for automation
- **Visible (false)**: See what's happening, better for debugging

### Screenshot Options
- Default: `screenshot.png` in current directory
- Custom: Specify full path like `/path/to/my_screenshot.png`

### Timeout Settings
- Default element wait: 10 seconds
- Customizable per operation

## 🐛 Troubleshooting

### Common Issues

**"Browser not started" error:**
- Always run `start_browser` first before other operations
- Keep the client running between operations

**Element not found:**
- Use browser developer tools (F12) to find correct selectors
- Try waiting for elements with `wait_for_element` first
- Use visible mode to see what's happening

**Connection errors:**
- Ensure mcp_server.py is in the same directory
- Check that all dependencies are installed
- Verify virtual environment is activated

**Playwright errors:**
- Run `playwright install chromium` again
- Check antivirus isn't blocking browser installation

### Debug Tips
1. Use `headless: false` to see browser actions
2. Take screenshots to verify page state
3. Use `extract_text` to confirm page content
4. Check browser developer console for JavaScript errors

## 📁 Project Structure

```
browser_mcp/
├── mcp_server.py      # MCP server with browser automation tools
├── mcp_client.py      # Interactive client for tool execution
├── .env              # Environment variables (optional)
├── .venv/            # Virtual environment
└── README.md         # This file
```

## 🔒 Security Considerations

- Be respectful when automating websites
- Check robots.txt and terms of service
- Implement delays between requests for scraping
- Don't automate sensitive operations without proper security
- Keep credentials secure (use environment variables)

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests to improve this browser automation tool.

## 📄 License

This project is open source. Use responsibly and in accordance with website terms of service.

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section
2. Verify all installation steps
3. Test with simple operations first
4. Use visible mode to debug problems

## 🔮 Advanced Usage

### Environment Variables
Create a `.env` file for configuration:
```
BROWSER_HEADLESS=true
DEFAULT_TIMEOUT=10000
SCREENSHOT_PATH=./screenshots/
```

### JavaScript Execution
Use `evaluate_javascript` for complex operations:
```javascript
// Get all links
document.querySelectorAll('a').length

// Scroll to bottom
window.scrollTo(0, document.body.scrollHeight)

// Get page title
document.title
```

### Error Handling
The system provides detailed error messages. Common patterns:
- Network errors: Check internet connection and URL
- Selector errors: Verify element exists and selector syntax
- Timeout errors: Increase timeout or wait for page load

---

**Happy Automating! 🤖✨**