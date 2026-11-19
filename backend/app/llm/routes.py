from app.llm.state import AgentState

def route_after_user_input(state: AgentState) -> str:

    intent = state.get("intent", "unclear")
    # Menu-related requests require complete preferences.
    if intent in ("recommendation", "menu_question"):
        if not state.get("preferences_complete", False):
            return "clarify"
        return "retrieve"

    # These intents do not require menu retrieval.
    if intent in (
        "general_question",
        "preference_only",
        "cart_action",
    ):
        return "respond"

    # Unclear requests need clarification.
    return "clarify"
