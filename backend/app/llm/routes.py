from app.llm.state import AgentState


def route_after_preferences(state: AgentState) -> str:

    if state.get("preferences_complete", False):
        return "retrieve"

    return "clarify"
