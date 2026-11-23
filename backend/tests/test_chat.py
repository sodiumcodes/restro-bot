"""
Tests for chat message persistence and history conversion.
"""

from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from langchain_core.messages import AIMessage, HumanMessage

from app.database.models.chat import ChatMessage
from app.services.chat_service import (
    save_chat_message,
    get_chat_history,
    to_langchain_messages,
)


def test_save_user_message():
    """Verify that a user message is persisted successfully."""

    db = MagicMock()
    session_id = uuid4()

    message = save_chat_message(
        db=db,
        session_id=session_id,
        role="user",
        content="  I want a vegetarian pizza.  ",
    )

    db.add.assert_called_once_with(message)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(message)

    assert message.session_id == session_id
    assert message.role == "user"
    assert message.content == "I want a vegetarian pizza."


def test_save_assistant_message():
    """Verify that an assistant response is persisted."""

    db = MagicMock()
    session_id = uuid4()

    message = save_chat_message(
        db=db,
        session_id=session_id,
        role="assistant",
        content="Sure! I can help you with that.",
    )

    assert message.role == "assistant"
    assert message.content == "Sure! I can help you with that."

    db.commit.assert_called_once()


def test_save_message_rejects_invalid_role():
    """Verify that unsupported message roles are rejected."""

    db = MagicMock()

    with pytest.raises(ValueError):
        save_chat_message(
            db=db,
            session_id=uuid4(),
            role="system",
            content="Invalid role",
        )

    db.add.assert_not_called()


def test_save_message_rolls_back_on_failure():
    """Verify transaction rollback when database persistence fails."""

    db = MagicMock()
    db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError):
        save_chat_message(
            db=db,
            session_id=uuid4(),
            role="user",
            content="Hello",
        )

    db.rollback.assert_called_once()


def test_get_chat_history():
    """Verify that messages are returned chronologically."""

    db = MagicMock()
    session_id = uuid4()

    first = MagicMock(spec=ChatMessage)
    second = MagicMock(spec=ChatMessage)
    third = MagicMock(spec=ChatMessage)

    # Database query returns newest messages first.
    db.execute.return_value.scalars.return_value.all.return_value = [
        third,
        second,
        first,
    ]

    messages = get_chat_history(
        db=db,
        session_id=session_id,
        limit=3,
    )

    assert messages == [first, second, third]


def test_convert_to_langchain_messages():
    """Verify database messages are converted correctly."""

    user_message = ChatMessage(
        id=1,
        role="user",
        content="Hello",
        session_id=uuid4(),
    )

    assistant_message = ChatMessage(
        id=2,
        role="assistant",
        content="Hi! How can I help?",
        session_id=user_message.session_id,
    )

    messages = to_langchain_messages(
        [user_message, assistant_message]
    )

    assert len(messages) == 2

    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)

    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi! How can I help?"

    assert messages[0].id == "db-1"
    assert messages[1].id == "db-2"
