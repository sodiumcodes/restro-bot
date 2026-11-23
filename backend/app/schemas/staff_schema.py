"""Schemas for staff order management, menu availability, and review endpoints."""
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class OrderStatusUpdate(BaseModel):
    """Schema for updating an order's lifecycle status."""
    status: Literal["placed", "preparing", "ready", "completed"]

class ItemAvailabilityUpdate(BaseModel):
    """Schema for toggling a menu item's availability."""
    is_available: bool

class MenuItemReviewUpdate(BaseModel):
    """Schema for confirming or correcting inferred fields and clearing needs_review."""
    allergens: list[str] | None = None
    veg_type: Literal["veg", "non-veg", "vegan", "egg"] | None = None
    spice_level: Literal["none", "mild", "medium", "hot"] | None = None
    ingredients: list[str] | None = None
    category: str | None = None
    needs_review: bool = False

class MenuItemStaffResponse(BaseModel):
    """Staff view of a menu item including availability and inferred field metadata."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: Decimal
    category: str | None = None
    veg_type: str | None = None
    spice_level: str | None = None
    ingredients: list[str] | None = None
    allergens: list[str] | None = None
    is_available: bool
    inferred_fields: list[str] = Field(default_factory=list)
    needs_review: bool