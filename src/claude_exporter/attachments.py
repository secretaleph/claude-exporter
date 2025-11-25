"""
Attachment and artifact handler for downloading and saving files.
"""
from pathlib import Path
from typing import Any

from .api import ClaudeAPIClient
from .models import Attachment, Message


class AttachmentHandler:
    """Handles downloading and organizing attachments and artifacts."""

    def __init__(self, api_client: ClaudeAPIClient, output_dir: Path):
        """
        Initialize attachment handler.

        Args:
            api_client: Claude API client for downloading
            output_dir: Base directory for saving attachments
        """
        self.api_client = api_client
        self.output_dir = output_dir
        self.attachments_dir = output_dir / "attachments"
        self.artifacts_dir = output_dir / "artifacts"

    def download_message_attachments(
        self,
        message: Message,
        org_id: str,
        conversation_id: str
    ) -> dict[str, Path]:
        """
        Download all attachments for a message.

        Args:
            message: Message containing attachments
            org_id: Organization ID
            conversation_id: Conversation ID

        Returns:
            Dictionary mapping attachment UUID to file path
        """
        if not message.attachments:
            return {}

        self.attachments_dir.mkdir(parents=True, exist_ok=True)

        downloaded = {}

        for attachment in message.attachments:
            try:
                file_path = self._download_attachment(
                    attachment,
                    org_id,
                    conversation_id,
                    message.uuid
                )
                downloaded[str(attachment.uuid)] = file_path
            except Exception as e:
                print(f"Warning: Failed to download attachment {attachment.file_name}: {e}")

        return downloaded

    def _download_attachment(
        self,
        attachment: Attachment,
        org_id: str,
        conversation_id: str,
        message_uuid: Any
    ) -> Path:
        """Download a single attachment."""
        # Create subdirectory for this message
        message_dir = self.attachments_dir / str(message_uuid)[:8]
        message_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_filename = self._sanitize_filename(attachment.file_name)
        file_path = message_dir / safe_filename

        # Download
        content = self.api_client.download_attachment(
            org_id,
            conversation_id,
            str(attachment.uuid)
        )

        file_path.write_bytes(content)
        return file_path

    def extract_artifacts(self, message: Message, message_index: int) -> dict[str, Path]:
        """
        Extract code artifacts from message text.

        Claude often includes code in markdown code blocks that should be saved as artifacts.

        Args:
            message: Message to extract artifacts from
            message_index: Index of message for naming

        Returns:
            Dictionary mapping artifact name to file path
        """
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        artifacts = {}
        text = message.text

        # Simple code block extraction (could be enhanced with more sophisticated parsing)
        import re

        # Match markdown code blocks with language
        pattern = r"```(\w+)?\n(.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)

        for idx, match in enumerate(matches):
            language = match.group(1) or "txt"
            code = match.group(2)

            # Only save if it's substantial code (more than 2 lines)
            if len(code.split("\n")) > 2:
                # Generate filename
                ext = self._get_extension_for_language(language)
                filename = f"message_{message_index}_artifact_{idx + 1}.{ext}"
                file_path = self.artifacts_dir / filename

                file_path.write_text(code)
                artifacts[filename] = file_path

        return artifacts

    @staticmethod
    def _get_extension_for_language(language: str) -> str:
        """Map language identifier to file extension."""
        ext_map = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rust": "rs",
            "ruby": "rb",
            "php": "php",
            "swift": "swift",
            "kotlin": "kt",
            "html": "html",
            "css": "css",
            "json": "json",
            "yaml": "yaml",
            "yml": "yml",
            "xml": "xml",
            "sql": "sql",
            "bash": "sh",
            "shell": "sh",
            "markdown": "md",
            "md": "md",
        }
        return ext_map.get(language.lower(), language.lower())

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize filename by removing/replacing invalid characters."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        return filename.strip()
