from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class OrderItemResponse(BaseModel):
    """Snapshot details of an ordered item."""
    model_config = ConfigDict(from_attributes=True)
    menu_item_id: int | None = None
    item_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    special_request: str | None = None

class OrderCreateRequest(BaseModel):
    """Payload for placing an order with validation per order type."""
    session_id: UUID
    order_type: Literal["dine_in", "takeaway"]
    cart_version: int = Field(ge=1)
    table_number: str | None = None
    contact: str | None = None

    @model_validator(mode="after")
    def validate_order_type_details(self) -> "OrderCreateRequest":
        # Enforce exact contact/table presence matching DB constraints
        if self.order_type == "dine_in":
            if not self.table_number or not self.table_number.strip():
                raise ValueError("table_number is required for dine-in orders.")
            self.table_number = self.table_number.strip()
            self.contact = None
        elif self.order_type == "takeaway":
            if not self.contact or not self.contact.strip():
                raise ValueError("contact (name or phone) is required for takeaway orders.")
            self.contact = self.contact.strip()
            self.table_number = None
        return self

class OrderResponse(BaseModel):
    """Structured response returned upon successful order placement."""
    model_config = ConfigDict(from_attributes=True)
    order_id: int
    status: str
    order_type: str
    table_number: str | None = None
    contact: str | None = None
    total: Decimal
    items: list[OrderItemResponse]
    message: str = "Your order is placed. Our staff will share the final bill and payment QR with you."
