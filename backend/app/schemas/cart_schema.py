from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

# expected_version is the cart concurrency version number the client last received from the server. We need it in cart_schema for optimistic concurrency control so the backend can detect stale writes from concurrent edits or retries and reject them with HTTP 409 instead of silently overwriting newer items.

class CartItemAdd(BaseModel):
    """Schema to add an item to the session cart."""
    item_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    special_request: str | None = Field(default=None, max_length=255)
    expected_version: int = Field(ge=1)

    @field_validator("special_request", mode="before")
    @classmethod
    def clean_special_request(cls, value: str | None) -> str | None:
        # Strip whitespace and store empty notes as None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return value

class CartItemUpdate(BaseModel):
    """Schema to update an existing cart item's quantity or special request."""
    item_id: int = Field(gt=0)
    quantity: int | None = Field(default=None, ge=0)
    special_request: str | None = Field(default=None, max_length=255)
    expected_version: int = Field(ge=1)

    @field_validator("special_request", mode="before")
    @classmethod
    def clean_special_request(cls, value: str | None) -> str | None:
        # Strip whitespace and store empty notes as None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return value

class CartItemRemove(BaseModel):
    """Schema to explicitly remove an item from the cart."""
    item_id: int = Field(gt=0)
    expected_version: int = Field(ge=1)

class CartLineResponse(BaseModel):
    """Snapshot of a single cart line with calculated totals."""
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    special_request: str | None = None

class CartResponse(BaseModel):
    """Full cart response including optimistic concurrency version and totals."""
    session_id: UUID
    version: int
    lines: list[CartLineResponse] = Field(default_factory=list)
    total: Decimal = Field(default=Decimal("0.00"))

    @property
    def items(self) -> list[CartLineResponse]:
        # Alias for lines to support interchangeable naming
        return self.lines