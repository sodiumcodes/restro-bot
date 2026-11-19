
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

class AgentState(TypedDict):
    # Conversation history
    messages: Annotated[list, add_messages]

    # Latest user input
    user_query: str

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
