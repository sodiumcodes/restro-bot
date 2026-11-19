from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages

DietaryPreference = Literal[
    "veg",
    "non-veg",
    "egg",
    "no-preference"
]
AllergyStatus = Literal[
    "has_allergies",
    "none",
    "unknown"
]
Intent = Literal[
    "recommendation",
    "menu_question",
    "general_question",
    "preference_only",
    "cart_action",
    "unclear",
]

class AgentState(TypedDict):
    # Conversation history
    messages: Annotated[list, add_messages]

    # Latest user input
    user_query: str

    # Customer intent
    intent: Intent
    
    # User preferences
    dietary_preference: DietaryPreference | None
    allergy_status: AllergyStatus
    allergens: list[str]

    # Workflow information
    preferences_complete: bool

    # Retrieval results
    retrieved_items: list[dict]

    # Final chatbot response
    response: str
