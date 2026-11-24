from typing import Literal
from pydantic import BaseModel, Field

class UserInputAnalysis(BaseModel):
    """Structured interpretation of the customer's latest message."""

    intent: Literal[
        "recommendation",
        "menu_question",
        "general_question",
        "preference_only",
        "cart_action",
        "unclear",
    ]
    dietary_preference: (
        Literal["veg", "non-veg", "egg", "no-preference"] | None
    ) = None

    allergy_status: (
        Literal["has_allergies", "none", "unknown"] | None
    ) = None
    allergens: list[str] | None = Field(default=None)