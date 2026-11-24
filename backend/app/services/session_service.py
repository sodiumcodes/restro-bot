"""
Session service for Cafe Chatbot.

Responsibilities:
    - Create new chat sessions.
    - Retrieve existing chat sessions.
    - Validate session IDs.
    - Update session activity timestamps.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from app.database.models.session import ChatSession


logger = logging.getLogger(__name__)

class SessionNotFoundError(Exception):
    """Raised when the requested chat session does not exist."""

def create_chat_session(db: DBSession) -> ChatSession:
    """
    Create and persist a new customer chat session.
    Args:
        db: Active database session.
    Returns:
        Newly created ChatSession object.
    """

    chat_session = ChatSession()
    try:
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        logger.info(
            "Created chat session %s",
            chat_session.id,
        )
        return chat_session

    except Exception:
        db.rollback()
        logger.exception("Failed to create chat session")
        raise


def get_chat_session(
    db: DBSession,
    session_id: UUID,
) -> ChatSession | None:
    """
    Retrieve a chat session using its UUID.
    Args:
        db: Active database session.
        session_id: Unique session identifier.
    Returns:
        ChatSession if found, otherwise None.
    """

    statement = select(ChatSession).where(
        ChatSession.id == session_id
    )

    return db.execute(statement).scalar_one_or_none()


def get_or_create_chat_session(
    db: DBSession,
    session_id: UUID | None = None,
) -> ChatSession:
    """
    Retrieve an existing session or create a new one.
    A supplied but invalid session ID must never silently
    result in a new session.
    """

    if session_id is None:
        return create_chat_session(db)

    chat_session = get_chat_session(
        db=db,
        session_id=session_id,
    )

    if chat_session is None:
        raise SessionNotFoundError(
            f"Chat session '{session_id}' does not exist."
        )

    return chat_session


def update_session_activity(
    db: DBSession,
    session_id: UUID,
) -> ChatSession:
    """
    Update the last_active timestamp of a chat session.
    Uses timezone-aware UTC timestamps for consistency.
    """

    chat_session = get_chat_session(
        db=db,
        session_id=session_id,
    )

    if chat_session is None:
        raise SessionNotFoundError(
            f"Chat session '{session_id}' does not exist."
        )

    try:
        chat_session.last_active = datetime.now(timezone.utc)

        db.commit()
        db.refresh(chat_session)

        return chat_session

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to update activity for session %s",
            session_id,
        )

        raise
