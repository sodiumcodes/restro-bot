"""
LangGraph workflow for Cafe Chatbot.
Responsibilities:
    - Define the agent workflow.
    - Register all agent nodes.
    - Configure conditional routing.
    - Compile the graph with an in-memory checkpointer.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from app.llm.state import AgentState
from backend.app.llm.nodes.user_input_node import (
    build_user_input_node,
    build_retrieval_node,
    build_response_generation_node,
    ask_clarification,
)
from app.llm.routes import route_after_user_input

def build_graph(llm, retrieval_fn, checkpointer=None):
    """
    Build and compile the Cafe Chatbot agent graph.
    Args:
        llm: Configured language model.
        retrieval_fn: Menu retrieval function.
        checkpointer: Optional LangGraph checkpointer.
                      Defaults to InMemorySaver.

    Returns:
        Compiled LangGraph application.
    """

    # Initialize the checkpointer if one isn't provided.
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Create state graph.
    graph = StateGraph(AgentState)

    # ---------------------------------------------
    # Build nodes
    # ---------------------------------------------

    user_input_node = build_user_input_node(llm)
    retrieval_node = build_retrieval_node(retrieval_fn)
    response_node = build_response_generation_node(llm)

    # ---------------------------------------------
    # Register nodes
    # ---------------------------------------------

    graph.add_node("user_input", user_input_node)
    graph.add_node("clarification", ask_clarification)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("response", response_node)

    # ---------------------------------------------
    # Entry point
    # ---------------------------------------------

    graph.set_entry_point("user_input")

    # ---------------------------------------------
    # Conditional routing
    # ---------------------------------------------

    graph.add_conditional_edges(
        "user_input",
        route_after_user_input,
        {
            "clarify": "clarification",
            "retrieve": "retrieval",
            "respond": "response",
        },
    )

    # ---------------------------------------------
    # Remaining edges
    # ---------------------------------------------

    graph.add_edge("clarification", END)
    graph.add_edge("retrieval", "response")
    graph.add_edge("response", END)

    # ---------------------------------------------
    # Compile with checkpointer
    # ---------------------------------------------

    return graph.compile(checkpointer=checkpointer)
