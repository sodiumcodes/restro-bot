"""
Session service for Cafe Chatbot.

Responsibilities:
    - Create new chat sessions.
    - Retrieve existing chat sessions.
    - Validate session IDs.
    - Update session activity timestamps.
    - Provide a session ID for LangGraph thread management.
"""

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from app.database.models.session import ChatSession

class SessionNotFoundError(Exception):
    """Raised when the requested chat session does not exist."""


def create_chat_session(db: DBSession) -> ChatSession:
    """
    Create and persist a new chat session.
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

        return chat_session

    except Exception:
        db.rollback()
        raise


def get_chat_session(
    db: DBSession,
    session_id: UUID,
) -> ChatSession | None:
    """
    Retrieve a chat session using its UUID.
    Args:
        db: Active database session.
        session_id: Unique chat session identifier.

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

    If a session ID is provided but does not exist,
    raise SessionNotFoundError instead of silently
    creating a different session.
    """

    if session_id is None:
        return create_chat_session(db)

    chat_session = get_chat_session(db, session_id)

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
    Update the last_active timestamp of a session.
    Returns:
        Updated ChatSession object.
    """

    chat_session = get_chat_session(db, session_id)

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
        raise