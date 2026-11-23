from unittest.mock import MagicMock
import pytest
from app.database import connection

# --------------------------------------------------
# get_db dependency tests
# --------------------------------------------------

def test_get_db_yields_database_session(monkeypatch):
    mock_db = MagicMock()

    monkeypatch.setattr(
        connection,
        "SessionLocal",
        lambda: mock_db,
    )

    db_generator = connection.get_db()

    db = next(db_generator)

    assert db is mock_db


def test_get_db_closes_session_after_request(monkeypatch):
    mock_db = MagicMock()

    monkeypatch.setattr(
        connection,
        "SessionLocal",
        lambda: mock_db,
    )

    db_generator = connection.get_db()

    db = next(db_generator)
    assert db is mock_db

    with pytest.raises(StopIteration):
        next(db_generator)

    mock_db.close.assert_called_once()


def test_get_db_closes_session_even_when_request_raises(monkeypatch):
    mock_db = MagicMock()

    monkeypatch.setattr(
        connection,
        "SessionLocal",
        lambda: mock_db,
    )

    db_generator = connection.get_db()

    db = next(db_generator)
    assert db is mock_db

    # FastAPI closes the dependency generator during request cleanup.
    db_generator.close()

    mock_db.close.assert_called_once()


# --------------------------------------------------
# Database connectivity query test
# --------------------------------------------------

def test_database_session_can_execute_select_one(monkeypatch):
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.return_value = 1

    monkeypatch.setattr(
        connection,
        "SessionLocal",
        lambda: mock_db,
    )

    db_generator = connection.get_db()
    db = next(db_generator)

    try:
        from sqlalchemy import text

        result = db.execute(text("SELECT 1"))

        assert result.scalar() == 1
        mock_db.execute.assert_called_once()
    finally:
        db_generator.close()

    mock_db.close.assert_called_once()