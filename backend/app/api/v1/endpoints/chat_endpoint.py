"""
Chat API endpoints for Cafe Chatbot.
Responsibilities:
    - Validate customer sessions.
    - Validate ordering-session status.
    - Persist incoming customer messages.
    - Execute the LangGraph workflow.
    - Persist assistant responses.
"""

import logging
from uuid import UUID
from fastapi import Depends, HTTPException, Request
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.router import chat_router as router
from app.database.connection import get_db
from app.database.models.order import Order
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat_service import get_chat_history, save_chat_message, to_langchain_messages
from app.services.session_service import get_chat_session, update_session_activity

logger = logging.getLogger(__name__)

@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Process a customer message through the LangGraph workflow.

    The customer's message is persisted before graph execution.
    The assistant's response is persisted only after successful
    generation.
    """

    session_id: UUID = payload.session_id

    # Step 1: Validate the customer session.
    chat_session = get_chat_session(
        db=db,
        session_id=session_id,
    )

    if chat_session is None:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found.",
        )

    # Step 2: Prevent further chat after an order is placed.
    order_exists = db.scalar(
        select(Order.id)
        .where(Order.session_id == session_id)
        .limit(1)
    )

    if order_exists:
        raise HTTPException(
            status_code=409,
            detail="This ordering session has already been completed.",
        )

    # Step 3: Persist the customer's message.
    save_chat_message(
        db=db,
        session_id=session_id,
        role="user",
        content=payload.message,
    )

    # Step 4: Update session activity.
    update_session_activity(
        db=db,
        session_id=session_id,
    )

    # Step 5: Retrieve the compiled LangGraph workflow.
    graph = request.app.state.graph

    # Every customer session maps to one LangGraph thread.
    config = {
        "configurable": {
            "thread_id": str(session_id),
        }
    }

    # Step 6: Check whether LangGraph already has a checkpoint.
    # If it does, only the latest message should be supplied.
    # Otherwise, restore the persisted conversation messages.
    try:
        graph_state = await graph.aget_state(config)

        if graph_state.values:
            graph_messages = [
                HumanMessage(content=payload.message)
            ]
        else:
            history = get_chat_history(
                db=db,
                session_id=session_id,
                limit=None,
            )

            graph_messages = to_langchain_messages(history)

        # Step 7: Prepare the graph input.
        graph_input = {
            "user_query": payload.message,
            "messages": graph_messages,
        }

        # Step 8: Execute the asynchronous LangGraph workflow.
        result = await graph.ainvoke(
            graph_input,
            config=config,
        )

        response_text = result.get("response")

        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError(
                "LangGraph did not return a valid response."
            )

        # Step 9: Persist the assistant's response.
        save_chat_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=response_text,
        )

        # Step 10: Return the response.
        return ChatResponse(
            session_id=session_id,
            response=response_text,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Chat processing failed for session %s",
            session_id,
        )

        raise HTTPException(
            status_code=503,
            detail="Unable to process your message right now. Please try again.",
        ) from exc
