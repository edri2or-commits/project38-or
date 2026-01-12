# MCP Tools API Documentation

Model Context Protocol (MCP) Tools provide agents with safe, sandboxed capabilities to interact with the outside world.

**Overview:**
- **Browser Server**: Playwright-based web automation
- **Filesystem Server**: Sandboxed file operations
- **Notification Server**: Telegram and n8n webhooks
- **Tool Registry**: Access control and usage tracking

---

## Architecture

```
Agent Code (isolated subprocess)
    ↓
ToolRegistry (access control + rate limiting)
    ↓
┌────────────────┬──────────────────┬─────────────────┐
│ BrowserServer  │ FilesystemServer │ NotifServer     │
│ (Playwright)   │ (sandboxed)      │ (Telegram/n8n)  │
└────────────────┴──────────────────┴─────────────────┘
    ↓               ↓                  ↓
Web Pages      /workspace/{id}/    External APIs
```

---

## Browser Server

Playwright-based web automation for agents.

### BrowserServer

```python
from src.mcp import BrowserServer

server = BrowserServer(headless=True)
await server.start()
```

**Methods:**

#### `start()`

Start browser instance.

```python
await server.start()
```

**Raises:** `RuntimeError` if playwright not installed or already running.

#### `stop()`

Stop browser and cleanup resources.

```python
await server.stop()
```

#### `navigate(url, wait_until="domcontentloaded")`

Navigate to URL.

```python
result = await server.navigate("https://example.com")
print(result.url, result.success)
```

**Args:**
- `url` (str): URL to navigate to (must start with http:// or https://)
- `wait_until` (str): When to consider navigation complete (`load`, `domcontentloaded`, `networkidle`)

**Returns:** `BrowserResult` with `success`, `url`, `duration`

**Raises:** `ValueError` if URL is invalid

#### `click(selector, timeout=5000)`

Click on element.

```python
result = await server.click("button.submit")
```

**Args:**
- `selector` (str): CSS selector for element
- `timeout` (int): Wait timeout in milliseconds (default: 5000)

**Returns:** `BrowserResult`

#### `extract_text(selector=None)`

Extract text from page or element.

```python
# Extract from specific element
result = await server.extract_text("h1")
print(result.data)  # "Welcome to Example"

# Extract entire page
result = await server.extract_text()
```

**Args:**
- `selector` (str, optional): CSS selector (None = entire page HTML)

**Returns:** `BrowserResult` with text in `data` field

#### `screenshot(path=None, full_page=False)`

Capture screenshot.

```python
# Save to file
result = await server.screenshot("/tmp/page.png")

# Get bytes
result = await server.screenshot()
screenshot_bytes = result.data
```

**Args:**
- `path` (str, optional): File path to save (None = return bytes)
- `full_page` (bool): Capture full scrollable page (default: False)

**Returns:** `BrowserResult` with screenshot bytes or path in `data`

#### `fill_form(selector, value)`

Fill form field.

```python
await server.fill_form("input[name='email']", "test@example.com")
```

**Args:**
- `selector` (str): CSS selector for input field
- `value` (str): Value to enter

**Returns:** `BrowserResult`

#### `wait_for_element(selector, timeout=10000)`

Wait for element to appear.

```python
result = await server.wait_for_element(".dynamic-content")
```

**Args:**
- `selector` (str): CSS selector
- `timeout` (int): Wait timeout in milliseconds (default: 10000)

**Returns:** `BrowserResult`

**Properties:**
- `is_running` (bool): Whether server is running
- `current_url` (str | None): Current page URL

### BrowserResult

Result from browser operations.

**Attributes:**
- `tool` (str): Tool that was used ("navigate", "click", etc.)
- `success` (bool): Whether operation succeeded
- `data` (Any): Extracted data (text, screenshot bytes, etc.)
- `error` (str | None): Error message if failed
- `url` (str | None): Current URL after operation
- `duration` (float): Operation duration in seconds
- `timestamp` (datetime): When operation completed

**Methods:**
- `to_dict()`: Serialize to dictionary

---

## Filesystem Server

Sandboxed file operations for agents.

### Security Features

- **Sandbox Isolation**: Each agent has isolated workspace at `/workspace/agent_{id}/`
- **Path Traversal Prevention**: No `..` or absolute paths allowed
- **File Size Limits**: Max 10MB per file
- **No Symlinks**: Symlink following disabled

### FilesystemServer

```python
from src.mcp import FilesystemServer

server = FilesystemServer(agent_id=1)
```

**Methods:**

#### `read_file(path, encoding="utf-8")`

Read file from sandbox.

```python
result = await server.read_file("output.txt")
print(result.data)  # File content
```

**Args:**
- `path` (str): Relative path within sandbox
- `encoding` (str): Text encoding (default: utf-8)

**Returns:** `FilesystemResult` with file content in `data`

**Raises:** `FileNotFoundError` if file not found

#### `write_file(path, content, encoding="utf-8", overwrite=True)`

Write file to sandbox.

```python
result = await server.write_file("output.txt", "Hello, World!")
```

**Args:**
- `path` (str): Relative path within sandbox
- `content` (str): File content
- `encoding` (str): Text encoding (default: utf-8)
- `overwrite` (bool): Allow overwriting existing files (default: True)

**Returns:** `FilesystemResult` with file size in `data`

**Raises:** `ValueError` if file too large or path invalid

#### `list_files(path=".", pattern="*")`

List files in directory.

```python
result = await server.list_files()
for file in result.data:
    print(file["name"], file["size"], file["is_dir"])
```

**Args:**
- `path` (str): Relative directory path (default: ".")
- `pattern` (str): Glob pattern (default: "*")

**Returns:** `FilesystemResult` with file list in `data`

#### `delete_file(path, recursive=False)`

Delete file or directory.

```python
# Delete file
await server.delete_file("temp.txt")

# Delete directory recursively
await server.delete_file("temp_dir", recursive=True)
```

**Args:**
- `path` (str): Relative path within sandbox
- `recursive` (bool): Delete directories recursively (default: False)

**Returns:** `FilesystemResult`

#### `create_dir(path)`

Create directory.

```python
result = await server.create_dir("data/processed")
```

**Args:**
- `path` (str): Relative directory path

**Returns:** `FilesystemResult`

#### `file_info(path)`

Get file information.

```python
result = await server.file_info("output.txt")
info = result.data
print(info["size"], info["modified"])
```

**Args:**
- `path` (str): Relative path within sandbox

**Returns:** `FilesystemResult` with file metadata in `data`:
  - `path`: Relative path
  - `name`: File name
  - `size`: File size in bytes
  - `is_dir`: Is directory
  - `is_file`: Is file
  - `modified`: Last modified timestamp (ISO 8601)
  - `created`: Created timestamp (ISO 8601)

#### `cleanup_sandbox()`

Delete ALL files in agent sandbox.

```python
success = await server.cleanup_sandbox()
```

**WARNING:** This deletes ALL files for this agent!

**Returns:** True if successful, False otherwise

**Properties:**
- `sandbox_root` (Path): Absolute path to agent sandbox

### FilesystemResult

Result from filesystem operations.

**Attributes:**
- `tool` (str): Tool that was used ("read_file", "write_file", etc.)
- `success` (bool): Whether operation succeeded
- `data` (Any): Operation result (file content, file list, etc.)
- `error` (str | None): Error message if failed
- `path` (str | None): Absolute path of file/directory
- `duration` (float): Operation duration in seconds
- `timestamp` (datetime): When operation completed

---

## Notification Server

Telegram and n8n webhook integration for agents.

### NotificationServer

```python
from src.mcp import NotificationServer
from src.secrets_manager import SecretManager

secrets = SecretManager()
telegram_token = secrets.get_secret("TELEGRAM-BOT-TOKEN")
n8n_url = secrets.get_secret("N8N-API")

server = NotificationServer(
    telegram_token=telegram_token,
    n8n_webhook_url=n8n_url
)
```

**Methods:**

#### `send_telegram(chat_id, message, parse_mode="Markdown")`

Send Telegram message.

```python
result = await server.send_telegram(
    chat_id=123456789,
    message="✅ Task completed successfully!"
)
```

**Args:**
- `chat_id` (int | str): Telegram chat ID or @username
- `message` (str): Message text
- `parse_mode` (str): Parse mode (`Markdown`, `HTML`, or `None`)

**Returns:** `NotificationResult` with Telegram API response in `data`

#### `send_n8n_webhook(payload, webhook_url=None)`

Send data to n8n webhook.

```python
result = await server.send_n8n_webhook({
    "agent_id": 1,
    "status": "completed",
    "result": {"processed": 100}
})
```

**Args:**
- `payload` (dict): JSON payload to send
- `webhook_url` (str, optional): Webhook URL (uses default if not provided)

**Returns:** `NotificationResult` with webhook response in `data`

#### `close()`

Close HTTP client.

```python
await server.close()
```

**Context Manager:**

```python
async with NotificationServer(telegram_token=token) as server:
    await server.send_telegram(chat_id=123, message="Hello!")
```

### Convenience Functions

#### `send_telegram_notification(message, chat_id, telegram_token)`

Send Telegram notification (convenience function).

```python
from src.mcp.notifications import send_telegram_notification

success = await send_telegram_notification(
    "Task completed!",
    chat_id=123456789,
    telegram_token=token
)
```

**Returns:** True if successful, False otherwise

#### `send_n8n_notification(payload, webhook_url)`

Send n8n webhook notification (convenience function).

```python
from src.mcp.notifications import send_n8n_notification

success = await send_n8n_notification(
    {"status": "completed"},
    webhook_url=webhook_url
)
```

**Returns:** True if successful, False otherwise

### NotificationResult

Result from notification operations.

**Attributes:**
- `tool` (str): Tool that was used ("send_telegram", "send_n8n_webhook")
- `success` (bool): Whether operation succeeded
- `data` (Any): Response data from notification service
- `error` (str | None): Error message if failed
- `duration` (float): Operation duration in seconds
- `timestamp` (datetime): When operation completed

---

## Tool Registry

Centralized registry for agent tool access, rate limiting, and usage tracking.

### ToolRegistry

```python
from src.mcp import ToolRegistry, ToolLimits

limits = ToolLimits(
    max_requests_per_minute=60,
    max_requests_per_hour=1000,
    max_browser_sessions=2,
    max_file_size_mb=10,
    max_notifications_per_hour=100
)

registry = ToolRegistry(limits=limits)
```

**Methods:**

#### `register_agent(agent_id, allowed_tools, telegram_token=None, n8n_webhook_url=None)`

Register agent and their allowed tools.

```python
await registry.register_agent(
    agent_id=1,
    allowed_tools=["browser", "filesystem", "notifications"],
    telegram_token="123:ABC",
    n8n_webhook_url="https://n8n.example.com/webhook/..."
)
```

**Args:**
- `agent_id` (int): Agent ID
- `allowed_tools` (list[str]): List of tool types ("browser", "filesystem", "notifications")
- `telegram_token` (str, optional): Telegram token (required if notifications enabled)
- `n8n_webhook_url` (str, optional): n8n webhook URL (required if notifications enabled)

**Raises:** `ValueError` if invalid tool types provided

#### `unregister_agent(agent_id)`

Unregister agent and cleanup resources.

```python
await registry.unregister_agent(agent_id=1)
```

#### `get_browser(agent_id)`

Get browser server for agent.

```python
browser = await registry.get_browser(agent_id=1)
await browser.start()
result = await browser.navigate("https://example.com")
```

**Returns:** `BrowserServer` instance

**Raises:**
- `ValueError` if agent not registered or lacks browser access
- `RuntimeError` if rate limit exceeded or max concurrent browsers reached

#### `get_filesystem(agent_id)`

Get filesystem server for agent.

```python
fs = await registry.get_filesystem(agent_id=1)
result = await fs.write_file("output.txt", "Hello!")
```

**Returns:** `FilesystemServer` instance

**Raises:**
- `ValueError` if agent not registered or lacks filesystem access
- `RuntimeError` if rate limit exceeded

#### `get_notifications(agent_id)`

Get notification server for agent.

```python
notif = await registry.get_notifications(agent_id=1)
result = await notif.send_telegram(chat_id=123, message="Done!")
```

**Returns:** `NotificationServer` instance

**Raises:**
- `ValueError` if agent not registered or lacks notification access
- `RuntimeError` if rate limit exceeded

#### `record_usage(agent_id, tool_type, operation, success, duration=0.0, data=None)`

Record tool usage for analytics.

```python
registry.record_usage(
    agent_id=1,
    tool_type="browser",
    operation="navigate",
    success=True,
    duration=1.5
)
```

#### `get_usage_stats(agent_id=None, since=None)`

Get usage statistics.

```python
# Get stats for specific agent
stats = await registry.get_usage_stats(agent_id=1)
print(stats["total_operations"], stats["success_rate"])

# Get stats for all agents
all_stats = await registry.get_usage_stats()
```

**Args:**
- `agent_id` (int, optional): Filter by agent (None = all agents)
- `since` (datetime, optional): Filter by time (None = all time)

**Returns:** Dictionary with usage statistics:
- `total_operations`: Total operations
- `successful`: Successful operations
- `failed`: Failed operations
- `success_rate`: Success rate percentage
- `by_tool`: Operations by tool type
- `by_operation`: Operations by operation name
- `total_duration`: Total duration in seconds

#### `cleanup()`

Cleanup all resources.

```python
await registry.cleanup()
```

### ToolLimits

Rate limits for tool usage.

**Attributes:**
- `max_requests_per_minute` (int): Max operations per minute (default: 60)
- `max_requests_per_hour` (int): Max operations per hour (default: 1000)
- `max_browser_sessions` (int): Max concurrent browser sessions (default: 2)
- `max_file_size_mb` (int): Max file size in MB (default: 10)
- `max_notifications_per_hour` (int): Max notifications per hour (default: 100)

### ToolUsage

Record of tool usage by agent.

**Attributes:**
- `agent_id` (int): Agent ID
- `tool_type` (str): Type of tool used
- `operation` (str): Specific operation (navigate, read_file, etc.)
- `success` (bool): Whether operation succeeded
- `duration` (float): Operation duration in seconds
- `timestamp` (datetime): When operation occurred
- `data` (dict): Additional usage data (bytes transferred, etc.)

---

## Complete Example

```python
from src.mcp import ToolRegistry, ToolLimits
from src.secrets_manager import SecretManager

async def agent_execution():
    # Setup secrets
    secrets = SecretManager()
    telegram_token = secrets.get_secret("TELEGRAM-BOT-TOKEN")
    n8n_url = secrets.get_secret("N8N-API")

    # Setup registry
    limits = ToolLimits(
        max_requests_per_minute=30,
        max_browser_sessions=1
    )
    registry = ToolRegistry(limits=limits)

    # Register agent
    await registry.register_agent(
        agent_id=1,
        allowed_tools=["browser", "filesystem", "notifications"],
        telegram_token=telegram_token,
        n8n_webhook_url=n8n_url
    )

    # Get tools
    browser = await registry.get_browser(agent_id=1)
    fs = await registry.get_filesystem(agent_id=1)
    notif = await registry.get_notifications(agent_id=1)

    # Execute agent task
    try:
        # Browse web
        await browser.start()
        nav_result = await browser.navigate("https://example.com")
        text_result = await browser.extract_text("h1")

        # Save to file
        await fs.write_file("scraped.txt", text_result.data)

        # Send notification
        await notif.send_telegram(
            chat_id=123456789,
            message=f"✅ Scraped data saved! URL: {nav_result.url}"
        )

        # Record usage
        registry.record_usage(
            agent_id=1,
            tool_type="browser",
            operation="navigate",
            success=True,
            duration=nav_result.duration
        )

    finally:
        await browser.stop()
        await registry.cleanup()

    # Get usage stats
    stats = await registry.get_usage_stats(agent_id=1)
    print(f"Total operations: {stats['total_operations']}")
    print(f"Success rate: {stats['success_rate']}%")

# Run agent
import asyncio
asyncio.run(agent_execution())
```

---

## Error Handling

All MCP tools return result objects with `success` boolean and optional `error` string.

```python
result = await fs.read_file("nonexistent.txt")
if not result.success:
    print(f"Error: {result.error}")
else:
    print(result.data)
```

**Common Errors:**

### Browser

- `RuntimeError("BrowserServer not started")` - Call `start()` first
- `ValueError("Invalid URL")` - URL must start with http:// or https://
- `RuntimeError("playwright not installed")` - Run `pip install playwright && playwright install chromium`

### Filesystem

- `ValueError("Path escapes sandbox")` - Path contains `..` or is absolute
- `ValueError("File too large")` - File exceeds 10MB limit
- `FileNotFoundError` - File doesn't exist

### Notifications

- `"Telegram token not configured"` - No telegram_token provided
- `"n8n webhook URL not configured"` - No n8n_webhook_url provided
- `httpx.HTTPStatusError` - API returned error status

### Registry

- `ValueError("Agent not registered")` - Call `register_agent()` first
- `ValueError("does not have access")` - Tool not in `allowed_tools`
- `RuntimeError("exceeded rate limit")` - Too many requests

---

## Best Practices

### Security

1. **Always use ToolRegistry**: Don't create tool servers directly - use registry for access control
2. **Validate agent permissions**: Only grant tools that agents actually need
3. **Monitor usage**: Check `get_usage_stats()` regularly for anomalies
4. **Sandbox isolation**: Each agent gets isolated `/workspace/agent_{id}/` directory
5. **Rate limiting**: Configure `ToolLimits` based on agent trust level

### Performance

1. **Browser resource usage**: Limit concurrent browsers (default: 2)
2. **File size limits**: Keep files under 10MB (configurable)
3. **Connection pooling**: NotificationServer reuses HTTP client
4. **Async operations**: All operations are async for concurrency
5. **Cleanup**: Always call `await browser.stop()` and `await registry.cleanup()`

### Monitoring

```python
# Get usage stats
stats = await registry.get_usage_stats(agent_id=1)

# Check for failures
if stats["success_rate"] < 80:
    print(f"WARNING: Agent {agent_id} has low success rate")

# Check rate limit violations
if stats["total_operations"] > expected:
    print(f"WARNING: Agent {agent_id} making excessive requests")
```

---

## Dependencies

```bash
# Install MCP Tools dependencies
pip install playwright httpx

# Install Playwright browser (Chromium)
playwright install chromium
```

---

## Testing

Run tests with mocking:

```bash
pytest tests/test_mcp.py -v
```

All tests use mocking to avoid requiring Playwright installation or real network calls.

---

## Integration with Agent Harness

MCP Tools integrate with the Agent Harness for 24/7 agent execution:

```python
from src.harness import execute_agent_code
from src.mcp import get_tool_registry

# Agent code with MCP tools
agent_code = """
from src.mcp import get_tool_registry

class Agent:
    def __init__(self, config):
        self.agent_id = config["agent_id"]
        self.registry = get_tool_registry()

    async def execute(self):
        # Get tools
        fs = await self.registry.get_filesystem(self.agent_id)
        notif = await self.registry.get_notifications(self.agent_id)

        # Do work
        await fs.write_file("output.txt", "Result!")
        await notif.send_telegram(123456789, "Done!")

        return {"status": "success"}
"""

# Execute agent with tools
result = await execute_agent_code(
    agent_code,
    config={"agent_id": 1},
    timeout=300
)
```

---

## Troubleshooting

### Browser won't start

**Problem:** `RuntimeError: playwright not installed`

**Solution:**
```bash
pip install playwright
playwright install chromium
```

### Filesystem access denied

**Problem:** `ValueError: Path escapes sandbox: /etc/passwd`

**Solution:** Use relative paths only. Sandbox is `/workspace/agent_{id}/`

### Rate limit exceeded

**Problem:** `RuntimeError: Agent 1 exceeded rate limit for browser`

**Solution:** Wait or increase `ToolLimits.max_requests_per_minute`

### Telegram sending fails

**Problem:** `httpx.HTTPStatusError: 401 Unauthorized`

**Solution:** Check `TELEGRAM-BOT-TOKEN` secret is valid

---

## API Reference Summary

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| `BrowserServer` | Web automation | `navigate()`, `click()`, `extract_text()`, `screenshot()` |
| `FilesystemServer` | File operations | `read_file()`, `write_file()`, `list_files()` |
| `NotificationServer` | Notifications | `send_telegram()`, `send_n8n_webhook()` |
| `ToolRegistry` | Access control | `register_agent()`, `get_browser()`, `get_usage_stats()` |

All tools return result objects with `.success`, `.data`, `.error` attributes.

---

For more information, see:
- [Agent Harness Documentation](harness.md)
- [Agent Factory Documentation](factory.md)
- [CLAUDE.md](../CLAUDE.md) - Project context and security rules
