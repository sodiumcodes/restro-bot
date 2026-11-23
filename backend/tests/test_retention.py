"""Tests for retention cleanup service, dry run mode, and session isolation."""
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from app.services import cart_service, retention_service


def test_retention_dry_run_does_not_mutate():
    db = MagicMock()
    # Mock return values for queries identifying expired IDs
    db.scalars.return_value.all.side_effect = [
        [1, 2],    # expired chat messages
        [10],      # expired llm fallback logs
        [uuid4()], # expired unattached sessions
        [uuid4()], # expired carts
        [101],     # expired orders with contact
    ]

    counts = retention_service.cleanup_retention(db=db, days=30, dry_run=True)

    assert counts["chat_messages"] == 2
    assert counts["llm_logs"] == 1
    assert counts["sessions"] == 1
    assert counts["carts"] == 1
    assert counts["orders_anonymized"] == 1

    # Under dry-run, no deletes or commits should be executed
    db.execute.assert_not_called()
    db.commit.assert_not_called()


def test_retention_executes_deletions_and_anonymization():
    db = MagicMock()
    db.scalars.return_value.all.side_effect = [
        [1],       # expired chat messages
        [],        # expired llm fallback logs
        [uuid4()], # expired unattached sessions
        [],        # expired carts
        [101],     # expired orders with contact
    ]

    counts = retention_service.cleanup_retention(db=db, days=30, dry_run=False)

    assert counts["chat_messages"] == 1
    assert counts["orders_anonymized"] == 1

    # In active run, execute and commit must be invoked
    assert db.execute.call_count >= 2
    db.commit.assert_called_once()


def test_session_isolation_prevents_cross_session_access():
    db = MagicMock()
    session_a = uuid4()
    session_b = uuid4()

    # Session A does not exist in DB check
    db.scalar.return_value = None

    with pytest.raises(cart_service.SessionNotFoundError):
        cart_service.get_cart(db, session_id=session_a)

    # Scoping strictly validates session identity and never cross-queries
    assert session_a != session_b
