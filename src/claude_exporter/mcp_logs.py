"""
MCP log parser and correlation with conversation messages.
"""
from datetime import datetime
from pathlib import Path
from typing import Any

import json
from pydantic import BaseModel, Field


class MCPToolCall(BaseModel):
    """Represents a single MCP tool call from logs."""
    timestamp: datetime
    tool: str
    params: dict[str, Any]
    conversation_id: str | None = None
    status: str
    result: Any | None = None
    error: str | None = None
    execution_time_ms: int | None = None
    model: str | None = None
    session_id: str | None = None


class MCPLogParser:
    """Parser for MCP tool call logs in JSONL format."""

    @staticmethod
    def parse_log_file(log_path: Path) -> list[MCPToolCall]:
        """
        Parse JSONL log file into list of tool calls.

        Args:
            log_path: Path to JSONL log file

        Returns:
            List of MCPToolCall objects, sorted by timestamp
        """
        tool_calls = []

        with open(log_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    tool_call = MCPToolCall.model_validate(data)
                    tool_calls.append(tool_call)
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON on line {line_num}: {e}")
                except Exception as e:
                    print(f"Warning: Failed to parse line {line_num}: {e}")

        # Sort by timestamp
        tool_calls.sort(key=lambda t: t.timestamp)
        return tool_calls

    @staticmethod
    def filter_by_conversation(
        tool_calls: list[MCPToolCall],
        conversation_id: str
    ) -> list[MCPToolCall]:
        """
        Filter tool calls for a specific conversation.

        Args:
            tool_calls: List of all tool calls
            conversation_id: Conversation UUID to filter by

        Returns:
            List of tool calls for this conversation
        """
        return [
            tc for tc in tool_calls
            if tc.conversation_id == conversation_id or tc.conversation_id is None
        ]


class ToolCallCorrelator:
    """Correlates MCP tool calls with conversation messages using timestamps."""

    @staticmethod
    def inject_into_tree(tree: Any, correlations: dict[str, list[MCPToolCall]]) -> None:
        """
        Inject tool calls into messages in the tree structure.

        Traverses the MessageNode tree and modifies message text in place.

        Args:
            tree: ConversationTree object
            correlations: Dictionary mapping message UUID to tool calls
        """
        def traverse_and_inject(node: Any) -> None:
            msg_id = str(node.message.uuid)
            if msg_id in correlations:
                node.message.text = ToolCallCorrelator.inject_tool_calls_into_text(
                    node.message.text,
                    correlations[msg_id]
                )

            for child in node.children:
                traverse_and_inject(child)

        if tree.root:
            traverse_and_inject(tree.root)

    @staticmethod
    def correlate_to_messages(
        messages: list[Any],  # Message objects from conversation
        tool_calls: list[MCPToolCall]
    ) -> dict[str, list[MCPToolCall]]:
        """
        Correlate tool calls to messages based on timestamps.

        Strategy:
        - Tool calls between message[i-1].created_at and message[i].created_at
          belong to message[i]

        Args:
            messages: List of Message objects (sorted by created_at)
            tool_calls: List of MCPToolCall objects (sorted by timestamp)

        Returns:
            Dictionary mapping message UUID to list of tool calls
        """
        correlations = {}

        for i, msg in enumerate(messages):
            # Skip human messages (they don't make tool calls)
            if msg.sender == "human":
                continue

            # Get time window for this message
            if i == 0:
                # First message - use any tool calls before it
                start_time = datetime.min
            else:
                start_time = messages[i - 1].created_at

            end_time = msg.created_at

            # Find tool calls in this time window
            msg_tool_calls = [
                tc for tc in tool_calls
                if start_time < tc.timestamp <= end_time
            ]

            if msg_tool_calls:
                correlations[str(msg.uuid)] = msg_tool_calls

        return correlations

    @staticmethod
    def format_tool_call_markdown(tool_call: MCPToolCall) -> str:
        """
        Format a tool call as markdown for display.

        Args:
            tool_call: MCPToolCall to format

        Returns:
            Markdown string representation
        """
        lines = []

        # Header
        status_icon = "✓" if tool_call.status == "success" else "✗"
        lines.append(f"**{status_icon} Tool: `{tool_call.tool}`**")

        # Parameters
        if tool_call.params:
            lines.append("\n**Parameters:**")
            params_json = json.dumps(tool_call.params, indent=2)
            lines.append(f"```json\n{params_json}\n```")

        # Result or error
        if tool_call.status == "success" and tool_call.result is not None:
            lines.append("\n**Result:**")
            # Handle different result types
            if isinstance(tool_call.result, dict) and tool_call.result.get("_truncated"):
                preview = tool_call.result.get("preview", "")
                lines.append(f"```\n{preview}...\n[truncated]\n```")
            elif isinstance(tool_call.result, (dict, list)):
                result_json = json.dumps(tool_call.result, indent=2)
                # Truncate very long results
                if len(result_json) > 1000:
                    result_json = result_json[:1000] + "\n...\n[truncated for display]"
                lines.append(f"```json\n{result_json}\n```")
            else:
                result_str = str(tool_call.result)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "..."
                lines.append(f"```\n{result_str}\n```")

        elif tool_call.status == "error" and tool_call.error:
            lines.append(f"\n**Error:** `{tool_call.error}`")

        # Execution time
        if tool_call.execution_time_ms is not None:
            lines.append(f"\n*Execution time: {tool_call.execution_time_ms}ms*")

        return "\n".join(lines)

    @staticmethod
    def inject_tool_calls_into_text(
        message_text: str,
        tool_calls: list[MCPToolCall]
    ) -> str:
        """
        Replace placeholder text with tool call details.

        Looks for patterns like:
        - "This block is not supported on your current device yet."
        - Code blocks with that text

        Args:
            message_text: Original message text
            tool_calls: Tool calls to inject

        Returns:
            Message text with placeholders replaced
        """
        if not tool_calls:
            return message_text

        # Look for the placeholder pattern
        placeholder_pattern = "This block is not supported on your current device yet."

        # Replace each occurrence with a tool call
        result_text = message_text
        for tool_call in tool_calls:
            if placeholder_pattern in result_text:
                tool_markdown = ToolCallCorrelator.format_tool_call_markdown(tool_call)

                # Try replacing with code block wrapper first
                code_block_placeholder = f"```\n{placeholder_pattern}\n```"
                if code_block_placeholder in result_text:
                    result_text = result_text.replace(
                        code_block_placeholder,
                        f"\n{tool_markdown}\n",
                        1
                    )
                else:
                    # Try without the code block
                    result_text = result_text.replace(
                        placeholder_pattern,
                        tool_markdown,
                        1
                    )

        return result_text
