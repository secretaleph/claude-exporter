"""
Data models for Claude.ai conversations.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Attachment(BaseModel):
    """Attachment in a message."""
    uuid: UUID = Field(alias="id")
    file_name: str
    file_type: str | None = None
    file_size: int | None = None
    extracted_content: str | None = None


class Message(BaseModel):
    """A single message in a conversation."""

    model_config = {"populate_by_name": True}

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

    # Parent relationship - mapped from API's parent_message_uuid field
    # The API uses a special null UUID (00000000-0000-4000-8000-000000000000) for root messages
    parent_uuid: UUID | None = Field(None, alias="parent_message_uuid")

    # Children list - will be populated during tree construction
    # Excluded from serialization to avoid circular references (use parent_uuid instead)
    children: list["Message"] = Field(default=[], exclude=True)

    @field_validator("parent_uuid", mode="before")
    @classmethod
    def convert_null_uuid(cls, v: Any) -> UUID | None:
        """Convert the API's special null UUID to None."""
        if v is None:
            return None
        # The API uses this special UUID for root messages
        NULL_UUID = "00000000-0000-4000-8000-000000000000"
        if isinstance(v, str) and v == NULL_UUID:
            return None
        if isinstance(v, UUID) and str(v) == NULL_UUID:
            return None
        return v


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
    # Exclude root from serialization to avoid circular references/deep recursion
    # The flat message list with parent_uuid is sufficient for reconstruction
    root: MessageNode | None = Field(default=None, exclude=True)
    all_messages: list[Message] = Field(default=[], exclude=True)
    branches: list[list[UUID]] = []  # List of message UUID paths representing branches
    orphaned_chains: list[list[Message]] = []  # Chains of messages not connected to main tree


class Branch(BaseModel):
    """A single branch path through the conversation."""
    messages: list[Message]
    branch_id: str  # Generated identifier like "branch-1", "branch-2"
    diverges_at_index: int | None = None  # Where this branch diverges from main
    is_main: bool = False  # Whether this is the main/active branch
