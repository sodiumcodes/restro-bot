"""
Session API endpoints for Cafe Chatbot.
Responsibilities:
    - Create customer sessions.
    - Retrieve session status.
    - Retrieve persisted conversation history.
"""

from uuid import UUID
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.router import session_router as router
from app.core.rate_limit import session_limiter
from app.database.connection import get_db
from app.database.models.order import Order
from app.schemas.chat_schema import ChatHistoryResponse, ChatMessageResponse
from app.schemas.session_schema import SessionCreateResponse, SessionStatusResponse
from app.services.chat_service import get_chat_history
from app.services.session_service import create_chat_session, get_chat_session


@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=201,
)
def create_session(
    request: Request,
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    """Create a new customer chat session."""
    session_limiter.check(request)

    chat_session = create_chat_session(db)

    return SessionCreateResponse(
        session_id=chat_session.id,
    )


@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
) -> SessionStatusResponse:
    """Retrieve the current status of a customer session."""

    chat_session = get_chat_session(
        db=db,
        session_id=session_id,
    )

    if chat_session is None:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found.",
        )

    # An existing order means the ordering session is closed.
    order_exists = db.scalar(
        select(Order.id)
        .where(Order.session_id == session_id)
        .limit(1)
    )

    return SessionStatusResponse(
        session_id=chat_session.id,
        status="closed" if order_exists else "active",
    )


@router.get(
    "/{session_id}/messages",
    response_model=ChatHistoryResponse,
)
def get_session_messages(
    session_id: UUID,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
) -> ChatHistoryResponse:
    """
    Retrieve the most recent messages for a session.

    Messages are returned in chronological order.
    """

    # Validate the session before retrieving its messages.
    chat_session = get_chat_session(
        db=db,
        session_id=session_id,
    )

    if chat_session is None:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found.",
        )

    messages = get_chat_history(
        db=db,
        session_id=session_id,
        limit=limit,
    )

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            ChatMessageResponse.model_validate(message)
            for message in messages
        ],
    )
