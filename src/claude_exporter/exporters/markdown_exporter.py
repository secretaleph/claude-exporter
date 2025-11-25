"""
Markdown exporter - exports conversation with branch visualization.
"""
from pathlib import Path
from typing import Any

from ..models import Branch, ConversationTree, Message, MessageNode
from ..tree_builder import TreeBuilder


class MarkdownExporter:
    """Exports conversation as Markdown with visual branch indicators."""

    def __init__(self, include_metadata: bool = True):
        """
        Initialize Markdown exporter.

        Args:
            include_metadata: Whether to include conversation metadata in output
        """
        self.include_metadata = include_metadata

    def export(self, tree: ConversationTree, output_path: Path) -> None:
        """
        Export conversation tree to single Markdown file showing all branches.

        Args:
            tree: ConversationTree to export
            output_path: Path to output Markdown file
        """
        content = self._build_markdown(tree)
        output_path.write_text(content)

    def _build_markdown(self, tree: ConversationTree) -> str:
        """Build Markdown content from conversation tree."""
        lines = []

        # Header
        lines.append(f"# {tree.conversation.name}\n")

        # Metadata
        if self.include_metadata:
            lines.append("## Conversation Metadata\n")
            lines.append(f"- **ID**: `{tree.conversation.uuid}`")
            lines.append(f"- **Model**: {tree.conversation.model or 'Unknown'}")
            lines.append(f"- **Created**: {tree.conversation.created_at}")
            lines.append(f"- **Updated**: {tree.conversation.updated_at}")
            if tree.conversation.summary:
                lines.append(f"- **Summary**: {tree.conversation.summary}")
            lines.append("")

        # Branch summary
        num_branches = len(tree.branches)
        if num_branches > 1:
            lines.append(f"## Branch Overview\n")
            lines.append(f"This conversation has **{num_branches} branches**.\n")

            # Build and extract branches for summary (pass tree to avoid rebuilding)
            tree_builder = TreeBuilder(tree.conversation)
            branches = tree_builder.extract_branch_objects(tree)

            for branch in branches:
                marker = "🌟 **Main**" if branch.is_main else f"🌿 Branch {branch.branch_id}"
                diverge_info = (
                    f" (diverges at message {branch.diverges_at_index})"
                    if branch.diverges_at_index is not None
                    else ""
                )
                lines.append(f"- {marker}: {len(branch.messages)} messages{diverge_info}")

            lines.append("")

        # Messages
        lines.append("## Conversation\n")

        if not tree.root:
            lines.append("*No messages in conversation*")
            return "\n".join(lines)

        # Render tree with branches
        self._render_tree_node(tree.root, lines, depth=0, branch_path=[])

        # Render orphaned chains if any
        if tree.orphaned_chains:
            lines.append("\n\n---\n")
            lines.append("## Orphaned Message Chains\n")
            lines.append(f"*{len(tree.orphaned_chains)} disconnected conversation chain(s) found. ")
            lines.append("These are typically from regenerated or edited messages.*\n")

            for chain_idx, chain in enumerate(tree.orphaned_chains, 1):
                lines.append(f"\n### Orphaned Chain {chain_idx}")
                lines.append(f"*{len(chain)} message(s), starting at index {chain[0].index}*\n")

                for msg in chain:
                    lines.append(f"\n#### {msg.sender.title()}")
                    if self.include_metadata:
                        lines.append(f"*Message ID: `{msg.uuid}` | Index: {msg.index}*")

                    for line in msg.text.split("\n"):
                        lines.append(line)

                    if msg.attachments:
                        lines.append("\n**Attachments:**")
                        for att in msg.attachments:
                            lines.append(f"- 📎 `{att.file_name}` ({att.file_type})")

                    lines.append("")

        return "\n".join(lines)

    def _render_tree_node(
        self,
        node: MessageNode,
        lines: list[str],
        depth: int,
        branch_path: list[str]
    ) -> None:
        """
        Recursively render message node with branch indicators.

        Args:
            node: Current MessageNode
            lines: List to append output lines to
            depth: Current depth in tree (for indentation)
            branch_path: Path of branch IDs leading to this node
        """
        msg = node.message

        # Add branch indicator if we're at a divergence point
        if len(node.children) > 1:
            lines.append(f"\n{'  ' * depth}**[Branch Point]**")

        # Render message
        lines.append(f"\n{'  ' * depth}### {msg.sender.title()}")

        if self.include_metadata:
            lines.append(f"{'  ' * depth}*Message ID: `{msg.uuid}` | Index: {msg.index}*")

        # Message content with proper indentation
        for line in msg.text.split("\n"):
            lines.append(f"{'  ' * depth}{line}")

        # Show attachments if any
        if msg.attachments:
            lines.append(f"\n{'  ' * depth}**Attachments:**")
            for att in msg.attachments:
                lines.append(f"{'  ' * depth}- 📎 `{att.file_name}` ({att.file_type})")

        # Render children
        if not node.children:
            # Leaf node
            return

        if len(node.children) == 1:
            # Single child - no branching
            self._render_tree_node(node.children[0], lines, depth, branch_path)
        else:
            # Multiple children - branches
            for idx, child in enumerate(node.children):
                branch_id = f"B{idx + 1}"
                new_path = branch_path + [branch_id]

                lines.append(f"\n{'  ' * depth}---")
                lines.append(f"{'  ' * depth}**Branch {branch_id}**")
                lines.append(f"{'  ' * depth}---")

                self._render_tree_node(child, lines, depth + 1, new_path)

                if idx < len(node.children) - 1:
                    lines.append(f"\n{'  ' * depth}---\n")


class MarkdownSplitExporter:
    """Exports each branch as a separate Markdown file."""

    def __init__(self, include_metadata: bool = True):
        """
        Initialize split Markdown exporter.

        Args:
            include_metadata: Whether to include conversation metadata in output
        """
        self.include_metadata = include_metadata

    def export(self, tree: ConversationTree, output_dir: Path) -> list[Path]:
        """
        Export each branch to separate Markdown files.

        Args:
            tree: ConversationTree to export
            output_dir: Directory to write Markdown files to

        Returns:
            List of created file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build branches (pass the existing tree to avoid rebuilding)
        tree_builder = TreeBuilder(tree.conversation)
        branches = tree_builder.extract_branch_objects(tree)

        created_files = []

        for branch in branches:
            filename = (
                f"{self._sanitize_filename(tree.conversation.name)}_{branch.branch_id}.md"
            )
            file_path = output_dir / filename

            content = self._build_branch_markdown(tree, branch)
            file_path.write_text(content)

            created_files.append(file_path)

        # Also create an index file
        index_path = output_dir / "index.md"
        index_content = self._build_index(tree, branches)
        index_path.write_text(index_content)
        created_files.append(index_path)

        return created_files

    def _build_branch_markdown(self, tree: ConversationTree, branch: Branch) -> str:
        """Build Markdown content for a single branch."""
        lines = []

        # Header
        marker = "Main Branch" if branch.is_main else branch.branch_id.title()
        lines.append(f"# {tree.conversation.name} - {marker}\n")

        # Metadata
        if self.include_metadata:
            lines.append("## Metadata\n")
            lines.append(f"- **Conversation ID**: `{tree.conversation.uuid}`")
            lines.append(f"- **Branch**: {branch.branch_id}")
            lines.append(f"- **Messages in branch**: {len(branch.messages)}")
            if branch.diverges_at_index is not None:
                lines.append(f"- **Diverges at index**: {branch.diverges_at_index}")
            lines.append(f"- **Model**: {tree.conversation.model or 'Unknown'}")
            lines.append("")

        # Messages
        lines.append("## Messages\n")

        for msg in branch.messages:
            lines.append(f"### {msg.sender.title()}\n")
            lines.append(msg.text)

            # Show attachments
            if msg.attachments:
                lines.append("\n**Attachments:**")
                for att in msg.attachments:
                    lines.append(f"- 📎 `{att.file_name}` ({att.file_type})")

            lines.append("")

        return "\n".join(lines)

    def _build_index(self, tree: ConversationTree, branches: list[Branch]) -> str:
        """Build index file listing all branches."""
        lines = []

        lines.append(f"# {tree.conversation.name} - Branch Index\n")
        lines.append("## Overview\n")
        lines.append(f"- **Total branches**: {len(branches)}")
        lines.append(f"- **Created**: {tree.conversation.created_at}")
        lines.append(f"- **Updated**: {tree.conversation.updated_at}")
        lines.append("")

        lines.append("## Branches\n")

        for branch in branches:
            marker = "🌟" if branch.is_main else "🌿"
            filename = (
                f"{self._sanitize_filename(tree.conversation.name)}_{branch.branch_id}.md"
            )
            lines.append(f"{marker} [{branch.branch_id.title()}](./{filename}) - "
                        f"{len(branch.messages)} messages")

        return "\n".join(lines)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize filename by removing/replacing invalid characters."""
        # Replace invalid characters with underscores
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')

        # Limit length
        max_length = 100
        if len(name) > max_length:
            name = name[:max_length]

        return name.strip()
