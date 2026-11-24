
"""
Tests for customer session management.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.database.models.session import ChatSession
from app.services import session_service


def test_create_chat_session():
    """Verify that a new chat session is created."""

    db = MagicMock()

    chat_session = session_service.create_chat_session(db)

    db.add.assert_called_once_with(chat_session)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(chat_session)

    assert isinstance(chat_session, ChatSession)


def test_create_session_rolls_back_on_failure():
    """Verify rollback when session creation fails."""

    db = MagicMock()
    db.commit.side_effect = RuntimeError("Database failure")

    with pytest.raises(RuntimeError):
        session_service.create_chat_session(db)

    db.rollback.assert_called_once()


def test_get_chat_session():
    """Verify that an existing session can be retrieved."""

    db = MagicMock()
    session_id = uuid4()

    expected_session = MagicMock(spec=ChatSession)

    db.execute.return_value.scalar_one_or_none.return_value = (
        expected_session
    )

    result = session_service.get_chat_session(
        db=db,
        session_id=session_id,
    )

    assert result == expected_session
    db.execute.assert_called_once()


def test_get_missing_chat_session():
    """Verify that a missing session returns None."""

    db = MagicMock()

    db.execute.return_value.scalar_one_or_none.return_value = None

    result = session_service.get_chat_session(
        db=db,
        session_id=uuid4(),
    )

    assert result is None


def test_get_or_create_existing_session(monkeypatch):
    """Verify that an existing session is reused."""

    db = MagicMock()
    session_id = uuid4()

    expected_session = MagicMock(spec=ChatSession)

    monkeypatch.setattr(
        session_service,
        "get_chat_session",
        lambda db, session_id: expected_session,
    )

    result = session_service.get_or_create_chat_session(
        db=db,
        session_id=session_id,
    )

    assert result == expected_session


def test_get_or_create_missing_session(monkeypatch):
    """Verify that an invalid supplied ID raises an exception."""

    db = MagicMock()

    monkeypatch.setattr(
        session_service,
        "get_chat_session",
        lambda db, session_id: None,
    )

    with pytest.raises(session_service.SessionNotFoundError):
        session_service.get_or_create_chat_session(
            db=db,
            session_id=uuid4(),
        )


def test_update_session_activity(monkeypatch):
    """Verify that the last activity timestamp is updated."""

    db = MagicMock()
    chat_session = MagicMock(spec=ChatSession)

    monkeypatch.setattr(
        session_service,
        "get_chat_session",
        lambda db, session_id: chat_session,
    )

    result = session_service.update_session_activity(
        db=db,
        session_id=uuid4(),
    )

    assert result == chat_session

    assert isinstance(
        chat_session.last_active,
        datetime,
    )

    assert chat_session.last_active.tzinfo is not None

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(chat_session)
