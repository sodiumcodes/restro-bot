from langgraph.graph import StateGraph, END

from app.llm.state import AgentState
from app.llm.nodes.user_input import (
    build_preference_extraction_node,
    build_retrieval_node,
    build_response_generation_node,
    ask_clarification,
)
from app.llm.routes import route_after_preferences


def build_graph(llm, retrieval_fn):

    graph = StateGraph(AgentState)

    # Build nodes
    preference_node = build_preference_extraction_node(llm)
    retrieval_node = build_retrieval_node(retrieval_fn)
    response_node = build_response_generation_node(llm)

    # Register nodes
    graph.add_node("user_input", preference_node)
    graph.add_node("clarification", ask_clarification)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("response", response_node)

    # Entry point
    graph.set_entry_point("user_input")

    # Conditional routing
    graph.add_conditional_edges(
        "user_input",
        route_after_preferences,
        {
            "retrieve": "retrieval",
            "clarify": "clarification",
        },
    )

    # Remaining connections
    graph.add_edge("clarification", END)
    graph.add_edge("retrieval", "response")
    graph.add_edge("response", END)

    return graph.compile()
