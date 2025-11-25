"""
Data models for Claude.ai conversations.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """Attachment in a message."""
    uuid: UUID = Field(alias="id")
    file_name: str
    file_type: str | None = None
    file_size: int | None = None
    extracted_content: str | None = None


class Message(BaseModel):
    """A single message in a conversation."""
    uuid: UUID
    text: str
    sender: Literal["human", "assistant"]
    index: int
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None = None
    chat_feedback: str | None = None
    attachments: list[Attachment] = []

    # Additional fields that might exist
    model: str | None = None
    thinking: str | None = None

    # For tree building - will be populated during tree construction
    parent_uuid: UUID | None = None
    children: list["Message"] = []


class Conversation(BaseModel):
    """A complete conversation with all messages."""
    uuid: UUID
    name: str
    summary: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime
    chat_messages: list[Message] = []

    # Additional metadata
    project_uuid: UUID | None = None


class MessageNode(BaseModel):
    """Tree node representing a message with its branches."""
    message: Message
    children: list["MessageNode"] = []
    is_current_branch: bool = False  # Whether this node is on the active branch


class ConversationTree(BaseModel):
    """Tree representation of a conversation showing all branches."""
    conversation: Conversation
    root: MessageNode | None = None
    all_messages: list[Message] = []
    branches: list[list[UUID]] = []  # List of message UUID paths representing branches


class Branch(BaseModel):
    """A single branch path through the conversation."""
    messages: list[Message]
    branch_id: str  # Generated identifier like "branch-1", "branch-2"
    diverges_at_index: int | None = None  # Where this branch diverges from main
    is_main: bool = False  # Whether this is the main/active branch
