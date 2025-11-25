# Claude.ai Conversation Exporter

Export Claude.ai conversations with **full branch support** and **perfect formatting preservation**.

## Features

- **Complete Branch Export**: Exports ALL conversation branches, not just the active one
- **Multiple Export Formats**: JSON, Markdown (single file or split per branch)
- **Perfect Formatting**: Preserves code blocks, tables, LaTeX, and all markdown
- **Rich Content Support**: Downloads attachments and extracts code artifacts
- **Auto-Authentication**: Automatically extracts session cookies from your browser

## Quick Start

```bash
# Install with uv
uv sync

# Export a conversation
uv run claude-export export CONVERSATION_ID

# Export all formats
uv run claude-export export CONVERSATION_ID -f all
```

## Installation

```bash
git clone https://github.com/yourusername/claude-exporter.git
cd claude-exporter
uv sync
```

## Usage

### Export a Conversation

```bash
claude-export export CONVERSATION_ID [OPTIONS]
```

**Options:**
- `--format, -f`: Export format (json|markdown|split|all) [default: markdown]
- `--output, -o`: Output directory [default: ./exports]
- `--org-id`: Organization ID (auto-detected if not provided)
- `--session-key, -s`: Session key cookie (auto-extracted if not provided)
- `--no-attachments`: Skip downloading attachments
- `--no-metadata`: Exclude metadata from markdown

**Examples:**
```bash
# Basic export
claude-export export abc123

# Export all formats
claude-export export abc123 -f all

# Export without attachments
claude-export export abc123 --no-attachments
```

### List Conversations

```bash
claude-export list-conversations
```

## Getting Conversation IDs

Open Claude.ai and navigate to any conversation. The URL looks like:
```
https://claude.ai/chat/abc123-def456-...
```

The UUID at the end is your conversation ID.

## Authentication

The tool automatically extracts session cookies from Chrome, Firefox, Edge, or Safari.

**Manual authentication:**
1. Open Claude.ai in your browser
2. Open DevTools (F12) → Application → Cookies → claude.ai
3. Copy the `sessionKey` value
4. Use: `claude-export export CONV_ID -s YOUR_SESSION_KEY`

## Output Formats

### JSON Format
Complete conversation tree with all metadata, branches, and relationships. Perfect for programmatic access.

### Markdown (Single File)
All branches in one file with visual indicators showing divergence points.

### Split Markdown
Separate file per branch + index file. Clean separation for linear reading.

## Output Structure

```
exports/
├── conversation-id.json              # JSON export
├── conversation-id.md                # Markdown export
├── conversation-id_branches/         # Split markdown export
│   ├── index.md
│   ├── conversation_branch-1.md
│   └── conversation_branch-2.md
├── attachments/                      # Downloaded attachments
│   └── msg-uuid/
│       └── file.pdf
└── artifacts/                        # Extracted code artifacts
    └── message_1_artifact_1.py
```

## Advanced Features

### Tool Use Logging (for Researchers)

If you're researching LLM-tool interactions, you can log tool calls from your MCP server and inject them into exported conversations. This replaces placeholder text like "This block is not supported on your current device yet" with detailed tool information.

See **[MCP_LOGGING.md](MCP_LOGGING.md)** for implementation details.

## Documentation

- **[Quick Start Guide](QUICKSTART.md)** - 5-minute setup
- **[MCP Logging Guide](MCP_LOGGING.md)** - Advanced tool logging (optional)

## Why This Exporter?

Existing Claude.ai exporters have critical problems:
1. **They don't export all branches** - only the currently active branch
2. **They mess up formatting** - manual HTML parsing breaks tables and code

This exporter solves both by:
- Building a complete conversation tree from API data
- Preserving exact formatting from Claude's internal representation
- Providing multiple export formats for different needs

## Limitations

- Requires active Claude.ai session (session cookies)
- Uses unofficial API (may break if Claude.ai changes their API)
- Cloudflare protection requires special handling

## License

MIT License - See LICENSE file

## Contributing

Contributions welcome! Areas for improvement:
- Support for more browsers in cookie extraction
- Enhanced artifact detection
- Interactive HTML export format
- Bulk export functionality

## Acknowledgments

Built with httpx, cloudscraper, click, rich, and pydantic.

---

**Note**: This tool uses the unofficial Claude.ai API. It is not affiliated with or endorsed by Anthropic.
