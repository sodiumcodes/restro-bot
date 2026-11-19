from typing import Literal
from pydantic import BaseModel, Field
# --------------------------------------------------
# Structured output schema
# --------------------------------------------------

class PreferenceExtraction(BaseModel):
    dietary_preference: (
        Literal["veg", "non-veg", "egg", "no-preference"] | None
    ) = None

    allergy_status: (
        Literal["has_allergies", "none", "unknown"] | None
    ) = None

    allergens: list[str] | None = Field(default=None)

