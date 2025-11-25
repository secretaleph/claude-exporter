"""
Investigation script to explore Claude.ai API structure and understand branch data.
"""
import json
import sys
from pathlib import Path
from typing import Any

import click
import httpx
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.tree import Tree

console = Console()


def extract_cookies_from_browser(domain: str = "claude.ai") -> dict[str, str]:
    """Extract session cookies from browser for Claude.ai."""
    try:
        import browser_cookie3

        # Try different browsers in order
        for browser_fn in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge]:
            try:
                cookies = browser_fn(domain_name=domain)
                cookie_dict = {cookie.name: cookie.value for cookie in cookies}
                if "sessionKey" in cookie_dict:
                    return cookie_dict
            except Exception:
                continue

        console.print("[yellow]Warning: Could not extract cookies from browser.[/yellow]")
        return {}
    except ImportError:
        console.print("[yellow]Warning: browser_cookie3 not available.[/yellow]")
        return {}


def fetch_conversation(conversation_id: str, org_id: str, cookies: dict[str, str]) -> dict[str, Any]:
    """Fetch conversation data from Claude.ai API."""
    url = f"https://claude.ai/api/organizations/{org_id}/chat_conversations/{conversation_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    console.print(f"[cyan]Fetching conversation from: {url}[/cyan]")

    with httpx.Client(cookies=cookies, headers=headers, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def analyze_message_structure(messages: list[dict]) -> None:
    """Analyze message structure to understand parent-child relationships."""
    console.print("\n[bold cyan]Message Structure Analysis:[/bold cyan]")

    if not messages:
        console.print("[red]No messages found![/red]")
        return

    # Analyze first message structure
    first_msg = messages[0]
    console.print("\n[yellow]Sample message keys:[/yellow]")
    console.print(JSON(json.dumps(list(first_msg.keys()), indent=2)))

    # Look for parent/sibling indicators
    parent_indicators = ["parent", "parent_id", "parent_uuid", "parent_message_uuid"]
    sibling_indicators = ["siblings", "alternatives", "branches"]

    found_parent = [key for key in parent_indicators if key in first_msg]
    found_sibling = [key for key in sibling_indicators if key in first_msg]

    if found_parent:
        console.print(f"\n[green]✓ Found parent reference keys: {found_parent}[/green]")
    else:
        console.print("\n[red]✗ No obvious parent reference keys found[/red]")

    if found_sibling:
        console.print(f"[green]✓ Found sibling/branch keys: {found_sibling}[/green]")
    else:
        console.print("[red]✗ No obvious sibling/branch keys found[/red]")

    # Check message index and ordering
    indices = [msg.get("index", "?") for msg in messages]
    console.print(f"\n[yellow]Message indices: {indices}[/yellow]")

    # Check for duplicate indices (indication of branches)
    index_counts = {}
    for idx in indices:
        if idx != "?":
            index_counts[idx] = index_counts.get(idx, 0) + 1

    duplicates = {idx: count for idx, count in index_counts.items() if count > 1}
    if duplicates:
        console.print(f"[green]✓ Found duplicate indices (branches!): {duplicates}[/green]")
    else:
        console.print("[yellow]No duplicate indices found[/yellow]")


def build_message_tree(messages: list[dict]) -> Tree:
    """Try to build a tree visualization of messages."""
    tree = Tree("[bold]Conversation Tree[/bold]")

    for i, msg in enumerate(messages):
        sender = msg.get("sender", "unknown")
        index = msg.get("index", "?")
        uuid = msg.get("uuid", "")[:8]
        text_preview = msg.get("text", "")[:50].replace("\n", " ")

        label = f"[{i}] {sender} (idx={index}, uuid={uuid}): {text_preview}..."
        tree.add(label)

    return tree


def save_raw_data(data: dict, output_path: Path) -> None:
    """Save raw JSON data for detailed inspection."""
    output_path.write_text(json.dumps(data, indent=2))
    console.print(f"\n[green]✓ Raw data saved to: {output_path}[/green]")


@click.command()
@click.option("--conversation-id", "-c", required=True, help="Claude.ai conversation ID")
@click.option("--org-id", "-o", required=True, help="Claude.ai organization ID")
@click.option("--session-key", "-s", help="Session key cookie (or will try to extract from browser)")
@click.option("--output", "-f", type=click.Path(), help="Output file for raw JSON data")
def main(conversation_id: str, org_id: str, session_key: str | None, output: str | None):
    """
    Investigate Claude.ai API structure to understand how branches are stored.

    Example usage:
        claude-investigate -c CONV_ID -o ORG_ID
        claude-investigate -c CONV_ID -o ORG_ID -s SESSION_KEY -f output.json
    """
    console.print(Panel.fit(
        "[bold cyan]Claude.ai API Investigation Tool[/bold cyan]\n"
        "This tool fetches conversation data and analyzes its structure",
        border_style="cyan"
    ))

    # Get cookies
    if session_key:
        cookies = {"sessionKey": session_key}
    else:
        console.print("[yellow]No session key provided, attempting to extract from browser...[/yellow]")
        cookies = extract_cookies_from_browser()

        if not cookies:
            console.print("[red]Error: No session key found. Please provide one with --session-key[/red]")
            sys.exit(1)

    try:
        # Fetch conversation
        data = fetch_conversation(conversation_id, org_id, cookies)

        console.print("\n[bold green]✓ Successfully fetched conversation data![/bold green]")

        # Show top-level keys
        console.print("\n[bold cyan]Top-level keys:[/bold cyan]")
        console.print(JSON(json.dumps(list(data.keys()), indent=2)))

        # Analyze messages
        messages = data.get("chat_messages", [])
        console.print(f"\n[bold cyan]Found {len(messages)} messages[/bold cyan]")

        if messages:
            analyze_message_structure(messages)

            # Build tree visualization
            console.print("\n")
            console.print(build_message_tree(messages))

        # Save raw data if requested
        if output:
            save_raw_data(data, Path(output))
        else:
            console.print("\n[yellow]Tip: Use --output to save raw JSON for detailed inspection[/yellow]")

    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP Error {e.response.status_code}: {e.response.text}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
