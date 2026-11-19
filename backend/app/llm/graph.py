from langgraph.graph import StateGraph, END
from app.llm.state import AgentState
from app.llm.nodes.user_input import (
    build_user_input_node,
    build_retrieval_node,
    build_response_generation_node,
    ask_clarification,
)
from app.llm.routes import route_after_user_input

def build_graph(llm, retrieval_fn):

    graph = StateGraph(AgentState)

    # Build nodes
    user_input_node = build_user_input_node(llm)
    retrieval_node = build_retrieval_node(retrieval_fn)
    response_node = build_response_generation_node(llm)

    # Register nodes
    graph.add_node("user_input", user_input_node)
    graph.add_node("clarification", ask_clarification)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("response", response_node)

    # Entry point
    graph.set_entry_point("user_input")

    # Conditional routing after understanding user input
    graph.add_conditional_edges(
        "user_input",
        route_after_user_input,
        {
            "clarify": "clarification",
            "retrieve": "retrieval",
            "respond": "response",
        },
    )

    # Connect remaining nodes
    graph.add_edge("clarification", END)
    graph.add_edge("retrieval", "response")
    graph.add_edge("response", END)

    return graph.compile()
