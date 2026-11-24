
"""
Chat message service for Cafe Chatbot.

Responsibilities:
    - Persist user and assistant messages.
    - Retrieve conversation history.
    - Convert persisted messages into LangChain messages
      when a conversation needs to be restored.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from app.database.models.chat import ChatMessage

logger = logging.getLogger(__name__)


def save_chat_message(
    db: DBSession,
    session_id: UUID,
    role: str,
    content: str,
) -> ChatMessage:
    """
    Save a single chat message to the database.

    Args:
        db: Active database session.
        session_id: Associated customer session.
        role: Message sender ('user' or 'assistant').
        content: Message content.

    Returns:
        The persisted ChatMessage object.

    Raises:
        ValueError: If the role or content is invalid.
        Exception: If database persistence fails.
    """

    if role not in {"user", "assistant"}:
        raise ValueError("Invalid chat message role.")

    content = content.strip()

    if not content:
        raise ValueError("Chat message cannot be empty.")

    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
    )

    try:
        db.add(message)
        db.commit()
        db.refresh(message)

        logger.info(
            "Saved %s message for session %s",
            role,
            session_id,
        )

        return message

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to save %s message for session %s",
            role,
            session_id,
        )

        raise


def get_chat_history(
    db: DBSession,
    session_id: UUID,
    limit: int | None = 100,
) -> list[ChatMessage]:
    """
    Retrieve the most recent messages for a chat session.

    Messages are returned in chronological order so that
    they can be displayed or restored as conversation context.

    Args:
        db: Active database session.
        session_id: Associated customer session.
        limit: Maximum number of messages to retrieve.
               None retrieves the complete history.

    Returns:
        List of ChatMessage objects.
    """

    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(
            ChatMessage.created_at.desc(),
            ChatMessage.id.desc(),
        )
    )

    if limit is not None:
        if limit < 1:
            raise ValueError("History limit must be positive.")

        statement = statement.limit(limit)

    messages = db.execute(statement).scalars().all()

    # The query retrieves newest messages first. Reverse them
    # to preserve the original conversation order.
    return list(reversed(messages))


def to_langchain_messages(
    messages: list[ChatMessage],
) -> list[HumanMessage | AIMessage]:
    """
    Convert database messages into LangChain message objects.

    Database message IDs are retained as message IDs to
    maintain stable identity when LangGraph restores history.

    Args:
        messages: Persisted conversation messages.

    Returns:
        Chronologically ordered LangChain messages.
    """

    langchain_messages: list[HumanMessage | AIMessage] = []

    for message in messages:

        if message.role == "user":
            langchain_messages.append(
                HumanMessage(
                    id=f"db-{message.id}",
                    content=message.content,
                )
            )

        elif message.role == "assistant":
            langchain_messages.append(
                AIMessage(
                    id=f"db-{message.id}",
                    content=message.content,
                )
            )

    return langchain_messages
