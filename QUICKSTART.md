# Quick Start Guide

## 5-Minute Setup

### 1. Install

```bash
# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

### 2. Get Your Conversation ID

Open Claude.ai and navigate to any conversation. The URL looks like:
```
https://claude.ai/chat/abc123-def456-...
```

Copy the UUID (the `abc123-def456-...` part).

### 3. Export!

```bash
# Let the tool auto-detect everything
uv run claude-export YOUR_CONVERSATION_ID

# Or if installed with pip
claude-export YOUR_CONVERSATION_ID
```

That's it! Your conversation will be exported to `./exports/`.

## Common Use Cases

### Export a conversation with branches

```bash
claude-export abc123
```

This creates:
- `./exports/abc123.md` - Full conversation with all branches visualized

### Export everything (JSON + all markdown formats)

```bash
claude-export abc123 -f all
```

This creates:
- `./exports/abc123.json` - Complete data structure
- `./exports/abc123.md` - Single markdown with branches
- `./exports/abc123_branches/` - Separate file per branch

### List all your conversations

```bash
uv run claude-export list-conversations
```

### Export without downloading attachments (faster)

```bash
claude-export abc123 --no-attachments
```

### Export to a specific directory

```bash
claude-export abc123 -o ~/Documents/claude-exports
```

## Understanding the Output

### Single Markdown File (`conversation.md`)

```markdown
# Conversation Title

## Branch Overview
This conversation has 2 branches.

## Conversation

### Human
Original question...

### Assistant
First response...

**[Branch Point]**

---
**Branch B1**
---

  ### Human
  Edited question...

---
**Branch B2**
---

  ### Human
  Different edit...
```

### Split Markdown Files

```
exports/
├── index.md                    # Overview with links
├── conversation_branch-1.md    # Main branch
└── conversation_branch-2.md    # Alternative branch
```

### JSON Export

Complete tree structure with:
- All messages with full metadata
- Parent-child relationships
- Branch paths
- Attachments and artifacts

## Troubleshooting

### "Could not extract session cookies"

**Solution**: Provide session key manually

1. Open Claude.ai in Chrome/Firefox/Edge
2. Open DevTools (F12)
3. Go to Application → Cookies → `claude.ai`
4. Copy the `sessionKey` value
5. Run:
   ```bash
   claude-export abc123 -s YOUR_SESSION_KEY
   ```

### "HTTP 401 Error"

Your session expired. Log into Claude.ai again and retry.

### Can't find conversation ID

1. Open Claude.ai
2. Click on the conversation
3. Look at the URL - the ID is at the end:
   `https://claude.ai/chat/THIS-IS-THE-ID`

## Next Steps

- See [README.md](README.md) for full documentation
- Report issues on GitHub
- Star the repo if you find it useful!
