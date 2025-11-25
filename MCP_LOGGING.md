# MCP Tool Logging & Injection

This document explains how to log MCP tool calls and inject them into exported conversations for research and analysis.

## Overview

Claude.ai's API doesn't preserve structured tool use data - it only shows placeholder text like "This block is not supported on your current device yet."

**Solution**: Log tool calls server-side in your MCP server, then correlate them with conversation messages using timestamps.

## Quick Start

### 1. Add Logging to Your MCP Server

Log every tool call to a JSONL file with this format:

```json
{"timestamp": "2025-11-06T07:44:35.123456Z", "tool": "web_fetch", "params": {"url": "https://example.com"}, "conversation_id": "a9e256a8-7dd6-41b6-b8f9-5ace3452c6b8", "status": "success", "result": {"content": "..."}, "execution_time_ms": 1234}
```

See [Handoff Document](#implementation-guide) below for implementation details.

### 2. Export Conversation

```bash
# Export conversation to JSON
claude-export export CONVERSATION_ID -f json
```

### 3. Inject Tool Logs

```bash
# Inject MCP logs into the conversation
claude-export inject-tool-logs \
  --conversation exports/CONVERSATION_ID.json \
  --mcp-logs ~/.mcp-server/logs/tool_calls.jsonl \
  --output exports/conv_with_tools.md
```

## Result

Placeholders like this:
```
This block is not supported on your current device yet.
```

Get replaced with rich tool details:
```markdown
**✓ Tool: `web_fetch`**

**Parameters:**
{
  "url": "https://www.anthropic.com/engineering/code-execution-with-mcp",
  "prompt": "Fetch and summarize the article"
}

**Result:**
{
  "content": "Article about code execution with MCP servers...",
  "word_count": 2500
}

*Execution time: 1234ms*
```

## JSONL Log Format

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 with microseconds in UTC (e.g., `2025-11-06T07:44:35.123456Z`) |
| `tool` | string | Tool name |
| `params` | object | Tool parameters as JSON |
| `status` | string | Either `"success"` or `"error"` |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | string | Claude conversation UUID (for filtering) |
| `result` | any | Tool return value (can be truncated if large) |
| `error` | string | Error message if status is "error" |
| `execution_time_ms` | number | Execution time in milliseconds |
| `model` | string | Claude model that made the call |
| `session_id` | string | MCP session identifier |

### Example Log Entries

**Successful tool call:**
```json
{"timestamp": "2025-11-06T07:44:35.123456Z", "tool": "generate_funscript", "params": {"duration": 30, "intensity": "medium"}, "conversation_id": "a9e256a8-7dd6-41b6-b8f9-5ace3452c6b8", "status": "success", "result": {"points": [{"pos": 50, "at": 0}, {"pos": 80, "at": 500}]}, "execution_time_ms": 1523}
```

**Failed tool call:**
```json
{"timestamp": "2025-11-06T07:45:12.789012Z", "tool": "web_fetch", "params": {"url": "https://example.com"}, "conversation_id": "a9e256a8-7dd6-41b6-b8f9-5ace3452c6b8", "status": "error", "error": "Connection timeout", "execution_time_ms": 5000}
```

**Tool call with truncated result:**
```json
{"timestamp": "2025-11-06T07:46:00.000000Z", "tool": "fetch_large_document", "params": {"doc_id": "123"}, "conversation_id": "a9e256a8-7dd6-41b6-b8f9-5ace3452c6b8", "status": "success", "result": {"_truncated": true, "preview": "First 1000 chars..."}, "execution_time_ms": 2340}
```

## How Correlation Works

The injection algorithm matches tool calls to messages using timestamps:

1. For each assistant message at time `T_msg`
2. Find tool calls where: `T_prev_msg < tool.timestamp <= T_msg`
3. Replace placeholder text with tool details

**Example:**
- Human message at `07:44:25.390742`
- Assistant message at `07:44:51.004544`
- Tool call at `07:44:35.123456` → belongs to assistant message

**Why microsecond precision matters:** Multiple tool calls can happen within the same second. Microseconds ensure accurate ordering.

## CLI Reference

### `inject-tool-logs`

Inject MCP tool call details into exported conversation.

**Usage:**
```bash
claude-export inject-tool-logs [OPTIONS]
```

**Options:**
- `-c, --conversation PATH` - Path to exported conversation JSON (required)
- `-m, --mcp-logs PATH` - Path to MCP tool logs in JSONL format (required)
- `-o, --output PATH` - Output path for enhanced file (required)
- `-f, --format [markdown|json]` - Output format (default: markdown)

**Examples:**

Basic usage:
```bash
claude-export inject-tool-logs \
  -c exports/conv.json \
  -m ~/.mcp-server/logs/tool_calls.jsonl \
  -o exports/conv_with_tools.md
```

Export as JSON with tool details:
```bash
claude-export inject-tool-logs \
  -c exports/conv.json \
  -m logs/tools.jsonl \
  -o exports/conv_enhanced.json \
  -f json
```

## Implementation Guide

### Python MCP Server

```python
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
log_dir = Path.home() / ".mcp-server" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("mcp_tools")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(log_dir / "tool_calls.jsonl")
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def log_tool_call(tool_name, params, func, conversation_id=None):
    """Wrapper that logs tool execution."""
    start_time = datetime.utcnow()
    log_entry = {
        "timestamp": start_time.isoformat() + "Z",
        "tool": tool_name,
        "params": params,
        "conversation_id": conversation_id,
    }

    try:
        result = func(**params)
        log_entry["status"] = "success"
        log_entry["result"] = truncate_if_large(result)
        return result
    except Exception as e:
        log_entry["status"] = "error"
        log_entry["error"] = str(e)
        raise
    finally:
        end_time = datetime.utcnow()
        log_entry["execution_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        logger.info(json.dumps(log_entry))

def truncate_if_large(data, max_len=1000):
    """Truncate large results for logging."""
    serialized = json.dumps(data)
    if len(serialized) > max_len:
        return {"_truncated": True, "preview": serialized[:max_len]}
    return data

# Use in tool handlers
@mcp_server.tool("generate_funscript")
def generate_funscript_handler(duration: int, intensity: str, conversation_id: str = None):
    return log_tool_call(
        "generate_funscript",
        {"duration": duration, "intensity": intensity},
        lambda duration, intensity: actual_generate_funscript(duration, intensity),
        conversation_id
    )
```

### TypeScript/JavaScript MCP Server

```typescript
import fs from 'fs';
import path from 'path';

const logDir = path.join(process.env.HOME!, '.mcp-server', 'logs');
fs.mkdirSync(logDir, { recursive: true });
const logFile = path.join(logDir, 'tool_calls.jsonl');

function logToolCall<T>(
  toolName: string,
  params: any,
  func: () => Promise<T>,
  conversationId?: string
): Promise<T> {
  const startTime = new Date();
  const logEntry: any = {
    timestamp: startTime.toISOString(),
    tool: toolName,
    params,
    conversation_id: conversationId,
  };

  return func()
    .then(result => {
      logEntry.status = 'success';
      logEntry.result = truncateIfLarge(result);
      return result;
    })
    .catch(error => {
      logEntry.status = 'error';
      logEntry.error = error.message;
      throw error;
    })
    .finally(() => {
      const endTime = new Date();
      logEntry.execution_time_ms = endTime.getTime() - startTime.getTime();
      fs.appendFileSync(logFile, JSON.stringify(logEntry) + '\n');
    });
}

function truncateIfLarge(data: any, maxLen: number = 1000): any {
  const serialized = JSON.stringify(data);
  if (serialized.length > maxLen) {
    return { _truncated: true, preview: serialized.substring(0, maxLen) };
  }
  return data;
}
```

## Tips

### Log Rotation

For production use, implement log rotation:

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    log_dir / "tool_calls.jsonl",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
```

### Filtering Logs

Filter logs for specific conversation:

```bash
# Extract logs for one conversation
grep 'a9e256a8-7dd6-41b6-b8f9-5ace3452c6b8' tool_calls.jsonl > conv_logs.jsonl

# Use filtered logs
claude-export inject-tool-logs -c conv.json -m conv_logs.jsonl -o output.md
```

### Privacy

Be careful logging sensitive data:

```python
def sanitize_params(params):
    """Remove sensitive data before logging."""
    safe_params = params.copy()
    for key in ['password', 'api_key', 'token']:
        if key in safe_params:
            safe_params[key] = '[REDACTED]'
    return safe_params

# Use in logging
log_entry["params"] = sanitize_params(params)
```

## Research Use Cases

This logging system is perfect for:

- **Tool usage analysis**: Which tools are called, how often, success rates
- **Latency profiling**: Execution time tracking per tool
- **Error analysis**: Tool failure patterns and error messages
- **Workflow analysis**: Tool call sequences and patterns
- **A/B testing**: Compare tool usage across different prompts/models
- **Data collection**: Build datasets of LLM-tool interactions

For haptic device research: Track Funscript generation patterns, parameter choices, success rates, and temporal patterns of LLM-mediated touch.

## Troubleshooting

**No tool calls found:**
- Check log file path is correct
- Verify logs use JSONL format (one JSON per line)
- Check `conversation_id` matches

**Wrong tool calls injected:**
- Verify timestamp accuracy (use UTC, include microseconds)
- Check conversation export includes correct timestamps
- Ensure clocks are synchronized if distributed

**Placeholder not replaced:**
- Verify placeholder text is exactly: "This block is not supported on your current device yet."
- Check tool call timestamps fall within message time windows
- Try with `--format json` to inspect the data structure

## See Also

- [Main README](README.md) - General exporter documentation
- [Quick Start Guide](QUICKSTART.md) - Basic usage examples
