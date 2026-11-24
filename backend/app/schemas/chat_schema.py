from decimal import Decimal
from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from app.schemas.cart_schema import CartResponse

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

class ChatSuggestion(BaseModel):
    """Structured menu item suggestion returned alongside assistant reply."""
    item_id: int
    name: str
    price: Decimal
    veg_type: str | None = None
    description: str | None = None


# Schema for the response returned by the backend to the client.
class ChatResponse(BaseModel):
    session_id: UUID
    response: str
    suggestions: list[ChatSuggestion] = Field(default_factory=list)
    cart: CartResponse | None = None

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
