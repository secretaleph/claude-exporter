"""
CLI interface for Claude conversation exporter.
"""
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .api import ClaudeAPIClient
from .attachments import AttachmentHandler
from .exporters import JSONExporter, MarkdownExporter, MarkdownSplitExporter
from .models import Conversation, ConversationTree
from .tree_builder import TreeBuilder
from .mcp_logs import MCPLogParser, ToolCallCorrelator

console = Console()


@click.group()
def cli():
    """Claude.ai Conversation Exporter - Export conversations with full branch support."""
    pass


@cli.command(name="export")
@click.argument("conversation_id")
@click.option(
    "--org-id",
    help="Organization ID (will auto-detect if not provided)"
)
@click.option(
    "--session-key",
    "-s",
    help="Session key cookie (will try to extract from browser if not provided)"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "markdown", "split", "all"]),
    default="markdown",
    help="Export format: json (complete tree), markdown (single file with branches), "
         "split (separate files per branch), all (all formats)"
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(),
    default="./exports",
    help="Output directory or file path"
)
@click.option(
    "--no-attachments",
    is_flag=True,
    help="Skip downloading attachments and artifacts"
)
@click.option(
    "--no-metadata",
    is_flag=True,
    help="Exclude metadata from markdown exports"
)
def export(
    conversation_id: str,
    org_id: str | None,
    session_key: str | None,
    format: str,
    output_path: str,
    no_attachments: bool,
    no_metadata: bool
):
    """
    Export a Claude.ai conversation with full branch support.

    CONVERSATION_ID: The UUID of the conversation to export

    Examples:

        Export as markdown with auto-detected credentials:
        $ claude-export CONV_ID

        Export all formats with explicit credentials:
        $ claude-export CONV_ID -o ORG_ID -s SESSION_KEY -f all

        Export to specific directory without attachments:
        $ claude-export CONV_ID --output ./my-exports --no-attachments
    """
    console.print(Panel.fit(
        "[bold cyan]Claude.ai Conversation Exporter[/bold cyan]\n"
        "Exporting with full branch support and formatting preservation",
        border_style="cyan"
    ))

    try:
        # Initialize API client
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Initializing...", total=None)

            # Get API client
            if session_key:
                api_client = ClaudeAPIClient(session_key=session_key)
            else:
                progress.update(task, description="[cyan]Extracting browser cookies...")
                api_client = ClaudeAPIClient()

            # Get org ID if not provided
            if not org_id:
                progress.update(task, description="[cyan]Detecting organization...")
                org_id = api_client.get_default_org_id()
                console.print(f"[green]✓[/green] Using organization: {org_id}")

            # Fetch conversation
            progress.update(task, description="[cyan]Fetching conversation...")
            data = api_client.get_conversation(org_id, conversation_id)

            console.print(f"[green]✓[/green] Fetched conversation: {data.get('name', 'Untitled')}")

            # Parse into models
            progress.update(task, description="[cyan]Parsing conversation structure...")
            conversation = Conversation.model_validate(data)

            console.print(f"[green]✓[/green] Found {len(conversation.chat_messages)} messages")

            # Build tree
            progress.update(task, description="[cyan]Building conversation tree...")
            tree_builder = TreeBuilder(conversation)
            tree = tree_builder.build_tree()

            num_branches = len(tree.branches)
            console.print(f"[green]✓[/green] Identified {num_branches} branch(es)")

            # Setup output
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Download attachments and artifacts if requested
            attachment_handler = None
            if not no_attachments:
                progress.update(task, description="[cyan]Downloading attachments and artifacts...")
                attachment_handler = AttachmentHandler(api_client, output_dir)

                # Download attachments for all messages
                total_attachments = 0
                total_artifacts = 0

                for msg in conversation.chat_messages:
                    # Download attachments
                    downloaded = attachment_handler.download_message_attachments(
                        msg, org_id, conversation_id
                    )
                    total_attachments += len(downloaded)

                    # Extract artifacts
                    artifacts = attachment_handler.extract_artifacts(msg, msg.index, conversation_id)
                    total_artifacts += len(artifacts)

                if total_attachments > 0:
                    console.print(f"[green]✓[/green] Downloaded {total_attachments} attachment(s)")
                if total_artifacts > 0:
                    console.print(f"[green]✓[/green] Extracted {total_artifacts} code artifact(s)")

            # Export based on format
            progress.update(task, description="[cyan]Exporting...")

            formats_to_export = []
            if format == "all":
                formats_to_export = ["json", "markdown", "split"]
            else:
                formats_to_export = [format]

            for fmt in formats_to_export:
                if fmt == "json":
                    json_exporter = JSONExporter()
                    json_path = output_dir / f"{conversation_id}.json"
                    json_exporter.export(tree, json_path)
                    console.print(f"[green]✓[/green] Exported JSON to: {json_path}")

                elif fmt == "markdown":
                    md_exporter = MarkdownExporter(include_metadata=not no_metadata)
                    md_path = output_dir / f"{conversation_id}.md"
                    md_exporter.export(tree, md_path)
                    console.print(f"[green]✓[/green] Exported Markdown to: {md_path}")

                elif fmt == "split":
                    split_exporter = MarkdownSplitExporter(include_metadata=not no_metadata)
                    split_dir = output_dir / f"{conversation_id}_branches"
                    created_files = split_exporter.export(tree, split_dir)
                    console.print(
                        f"[green]✓[/green] Exported {len(created_files)} branch files to: {split_dir}"
                    )

        console.print("\n[bold green]Export complete![/bold green]")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--session-key",
    "-s",
    help="Session key cookie (will try to extract from browser if not provided)"
)
def list_conversations(session_key: str | None):
    """List all conversations for the authenticated user."""
    try:
        # Initialize API client
        if session_key:
            api_client = ClaudeAPIClient(session_key=session_key)
        else:
            console.print("[cyan]Extracting browser cookies...[/cyan]")
            api_client = ClaudeAPIClient()

        # Get org ID
        org_id = api_client.get_default_org_id()
        console.print(f"[green]✓[/green] Using organization: {org_id}\n")

        # Get conversations
        conversations = api_client.get_conversations(org_id)

        console.print(f"[bold]Found {len(conversations)} conversations:[/bold]\n")

        for conv in conversations[:20]:  # Show first 20
            conv_id = conv.get("uuid", "unknown")
            name = conv.get("name", "Untitled")
            updated = conv.get("updated_at", "")
            console.print(f"• {name}")
            console.print(f"  ID: [cyan]{conv_id}[/cyan]")
            console.print(f"  Updated: {updated}\n")

        if len(conversations) > 20:
            console.print(f"[yellow]... and {len(conversations) - 20} more[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command(name="inject-tool-logs")
@click.option(
    "--conversation",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to exported conversation JSON file"
)
@click.option(
    "--mcp-logs",
    "-m",
    required=True,
    type=click.Path(exists=True),
    help="Path to MCP tool call logs (JSONL format)"
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output path for enhanced markdown file"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Output format"
)
def inject_tool_logs(conversation: str, mcp_logs: str, output: str, format: str):
    """
    Inject MCP tool call details into conversation export.

    Correlates tool calls from MCP server logs with conversation messages
    based on timestamps, replacing placeholder text with detailed tool information.

    Example:
        claude-export inject-tool-logs \\
            --conversation exports/conv.json \\
            --mcp-logs ~/.mcp-server/logs/tool_calls.jsonl \\
            --output exports/conv_with_tools.md
    """
    console.print(Panel.fit(
        "[bold cyan]MCP Tool Log Injection[/bold cyan]\n"
        "Correlating tool calls with conversation messages",
        border_style="cyan"
    ))

    try:
        import json

        # Load conversation JSON
        console.print("[cyan]Loading conversation...[/cyan]")
        with open(conversation, 'r') as f:
            conv_data = json.load(f)

        # Parse as ConversationTree
        tree = ConversationTree.model_validate(conv_data)
        console.print(f"[green]✓[/green] Loaded conversation: {tree.conversation.name}")
        console.print(f"[green]✓[/green] Messages: {len(tree.all_messages)}")

        # Parse MCP logs
        console.print("[cyan]Parsing MCP logs...[/cyan]")
        tool_calls = MCPLogParser.parse_log_file(Path(mcp_logs))
        console.print(f"[green]✓[/green] Found {len(tool_calls)} total tool calls")

        # Filter for this conversation
        conv_tool_calls = MCPLogParser.filter_by_conversation(
            tool_calls,
            str(tree.conversation.uuid)
        )
        console.print(f"[green]✓[/green] {len(conv_tool_calls)} tool calls for this conversation")

        # Correlate tool calls to messages
        console.print("[cyan]Correlating tool calls to messages...[/cyan]")
        correlations = ToolCallCorrelator.correlate_to_messages(
            tree.all_messages,
            conv_tool_calls
        )

        total_injected = sum(len(calls) for calls in correlations.values())
        console.print(f"[green]✓[/green] Correlated {total_injected} tool calls to messages")

        # Inject tool calls into message text (in the tree structure)
        console.print("[cyan]Injecting tool details...[/cyan]")
        ToolCallCorrelator.inject_into_tree(tree, correlations)
        console.print(f"[green]✓[/green] Injected {total_injected} tool call(s)")

        # Export with enhanced content
        console.print("[cyan]Exporting...[/cyan]")
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "markdown":
            exporter = MarkdownExporter(include_metadata=True)
            exporter.export(tree, output_path)
            console.print(f"[green]✓[/green] Exported enhanced markdown to: {output_path}")
        else:
            # Export as JSON with modified text
            output_path.write_text(json.dumps(tree.model_dump(mode="json"), indent=2, default=str))
            console.print(f"[green]✓[/green] Exported enhanced JSON to: {output_path}")

        console.print("\n[bold green]Tool injection complete![/bold green]")

        # Show summary
        if correlations:
            console.print("\n[bold]Tool calls by message:[/bold]")
            for msg_id, calls in correlations.items():
                msg = next(m for m in tree.all_messages if str(m.uuid) == msg_id)
                tools = ", ".join(tc.tool for tc in calls)
                console.print(f"  Message {msg.index}: {tools}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
