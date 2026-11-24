from uuid import UUID
from datetime import datetime
from typing import Literal
# BaseModel is used to create Pydantic models.
# Field is used to define validation rules for fields.
# field_validator is used to create custom validation logic.
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

# Schema for incoming chat requests from the client.
class ChatRequest(BaseModel):
    session_id: UUID

    # Message sent by the user.
    message: str = Field(
        min_length=1,
        max_length=500,
    )

    # Custom validator that runs BEFORE Pydantic's normal validation.
    @field_validator("message", mode="before")
    @classmethod
    def clean_message(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


# Schema for the response returned by the backend to the client.
class ChatResponse(BaseModel):
    session_id: UUID
    response: str

class ChatMessageResponse(BaseModel):
    """Schema representing one persisted conversation message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Schema for retrieving a session's conversation history."""

    session_id: UUID
    messages: list[ChatMessageResponse]
