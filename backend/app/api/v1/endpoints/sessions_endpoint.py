from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.router import session_router as router
from app.database.connection import get_db
from app.database.models.order import Order
from app.schemas.session_schema import (
    SessionCreateResponse,
    SessionStatusResponse,
)
from app.services.session_service import (
    create_chat_session,
    get_chat_session,
)

@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=201,
)
def create_session(
    db: Session = Depends(get_db),
):
    chat_session = create_chat_session(db)

    return SessionCreateResponse(
        session_id=chat_session.id
    )


@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
):
    chat_session = get_chat_session(
        db=db,
        session_id=session_id,
    )

    if chat_session is None:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found.",
        )

    # An order means the ordering session has ended.
    order_exists = db.scalar(
        select(Order.id)
        .where(Order.session_id == session_id)
        .limit(1)
    )

    return SessionStatusResponse(
        session_id=chat_session.id,
        status="closed" if order_exists else "active",
    )
