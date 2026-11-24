
"""
LangGraph workflow for Cafe Chatbot.

Responsibilities:
    - Define the agent workflow.
    - Register all agent nodes.
    - Configure conditional routing.
    - Compile the graph with an in-memory checkpointer.

The checkpointer maintains conversation state separately
for each customer session using its thread_id.
"""

from typing import Any, Callable

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from app.llm.state import AgentState
from app.llm.nodes.user_input_node import (
    build_user_input_node,
    build_retrieval_node,
    build_response_generation_node,
    ask_clarification,
)
from app.llm.routes import route_after_user_input


def build_graph(
    llm: Any,
    retrieval_fn: Callable[
        [str, str, list[str], str],
        list[dict],
    ],
    checkpointer: Any | None = None,
):
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

    # Use the supplied checkpointer or create a new one.
    if checkpointer is None:
        checkpointer = InMemorySaver()

    # Initialize the state graph.
    graph = StateGraph(AgentState)

    # Build workflow nodes.
    user_input_node = build_user_input_node(llm)
    retrieval_node = build_retrieval_node(retrieval_fn)
    response_node = build_response_generation_node(llm)

    # Register nodes.
    graph.add_node("user_input", user_input_node)
    graph.add_node("clarification", ask_clarification)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("response", response_node)

    # Define the entry point.
    graph.set_entry_point("user_input")

    # Route the workflow according to the interpreted intent.
    graph.add_conditional_edges(
        "user_input",
        route_after_user_input,
        {
            "clarify": "clarification",
            "retrieve": "retrieval",
            "respond": "response",
        },
    )

    # Define the remaining workflow transitions.
    graph.add_edge("clarification", END)
    graph.add_edge("retrieval", "response")
    graph.add_edge("response", END)

    # Compile once during application startup.
    # The same compiled instance must be shared across requests.
    return graph.compile(
        checkpointer=checkpointer,
    )
