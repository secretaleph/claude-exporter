"""
JSON exporter - exports complete conversation tree as JSON.
"""
import json
from pathlib import Path

from ..models import ConversationTree


class JSONExporter:
    """Exports conversation as JSON with complete tree structure."""

    def export(self, tree: ConversationTree, output_path: Path) -> None:
        """
        Export conversation tree to JSON file.

        Args:
            tree: ConversationTree to export
            output_path: Path to output JSON file
        """
        # Convert to dict using Pydantic's model_dump
        data = tree.model_dump(mode="json")

        # Write to file with pretty formatting
        output_path.write_text(json.dumps(data, indent=2, default=str))

    def export_compact(self, tree: ConversationTree, output_path: Path) -> None:
        """
        Export conversation tree to compact JSON (no indentation).

        Args:
            tree: ConversationTree to export
            output_path: Path to output JSON file
        """
        data = tree.model_dump(mode="json")
        output_path.write_text(json.dumps(data, separators=(',', ':'), default=str))
