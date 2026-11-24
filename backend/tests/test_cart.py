"""Tests for cart service covering mutations, DB pricing, concurrency, and validation."""
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from app.database.models import Cart, MenuItem
from app.services import cart_service


def _mock_db(item=None, order_exists=False, session_exists=True, cart=None):
    db = MagicMock()
    # Mock session and existing order checks
    db.scalar.side_effect = lambda stmt: (
        (uuid4() if session_exists else None) if "sessions" in str(stmt).lower()
        else ((1 if order_exists else None) if "orders" in str(stmt).lower() else None)
    )
    db.get.side_effect = lambda model, id_: item if model is MenuItem and item and item.id == id_ else (cart if model is Cart else None)
    db.scalars.return_value.all.return_value = [item] if item else []
    return db


def test_add_item_and_db_totals():
    sid, item = uuid4(), MenuItem(id=1, name="Coffee", price=Decimal("150.00"), is_available=True, deleted_at=None)
    cart = Cart(session_id=sid, state={"lines": []}, version=1)
    db = _mock_db(item=item, cart=cart)
    res = cart_service.add_item(db, sid, item_id=1, quantity=2, special_request="no sugar", expected_version=1)
    assert res.version == 2 and res.total == Decimal("300.00")
    assert res.lines[0].line_total == Decimal("300.00") and res.lines[0].special_request == "no sugar"


def test_update_item():
    sid, item = uuid4(), MenuItem(id=1, name="Coffee", price=Decimal("150.00"), is_available=True, deleted_at=None)
    cart = Cart(session_id=sid, state={"lines": [{"item_id": 1, "quantity": 1}]}, version=2)
    db = _mock_db(item=item, cart=cart)
    res = cart_service.update_item(db, sid, item_id=1, quantity=3, special_request="extra hot", expected_version=2)
    assert res.version == 3 and res.total == Decimal("450.00") and res.lines[0].quantity == 3


def test_remove_item():
    sid, item = uuid4(), MenuItem(id=1, name="Coffee", price=Decimal("150.00"), is_available=True, deleted_at=None)
    cart = Cart(session_id=sid, state={"lines": [{"item_id": 1, "quantity": 1}]}, version=2)
    db = _mock_db(item=item, cart=cart)
    res = cart_service.remove_item(db, sid, item_id=1, expected_version=2)
    assert res.version == 3 and len(res.lines) == 0 and res.total == Decimal("0.00")


def test_unavailable_item_rejected():
    sid, item = uuid4(), MenuItem(id=2, name="Cake", price=Decimal("200.00"), is_available=False, deleted_at=None)
    db = _mock_db(item=item, cart=Cart(session_id=sid, state={"lines": []}, version=1))
    with pytest.raises(cart_service.MenuItemError, match="unavailable"):
        cart_service.add_item(db, sid, item_id=2, quantity=1, special_request=None, expected_version=1)


def test_max_quantity_rejected():
    sid, item = uuid4(), MenuItem(id=1, name="Coffee", price=Decimal("150.00"), is_available=True, deleted_at=None)
    db = _mock_db(item=item, cart=Cart(session_id=sid, state={"lines": []}, version=1))
    with pytest.raises(cart_service.MenuItemError, match="between 1 and 10"):
        cart_service.add_item(db, sid, item_id=1, quantity=11, special_request=None, expected_version=1)


def test_stale_version_raises_409():
    sid, item = uuid4(), MenuItem(id=1, name="Coffee", price=Decimal("150.00"), is_available=True, deleted_at=None)
    cart = Cart(session_id=sid, state={"lines": [{"item_id": 1, "quantity": 1}]}, version=3)
    db = _mock_db(item=item, cart=cart)
    with pytest.raises(cart_service.StaleCartVersionError) as exc_info:
        cart_service.add_item(db, sid, item_id=1, quantity=1, special_request=None, expected_version=2)
    assert exc_info.value.current_cart.version == 3


def test_session_with_existing_order_rejected():
    sid = uuid4()
    db = _mock_db(order_exists=True)
    with pytest.raises(cart_service.SessionClosedError):
        cart_service.get_cart(db, sid)


def test_unknown_session_rejected():
    sid = uuid4()
    db = _mock_db(session_exists=False)
    with pytest.raises(cart_service.SessionNotFoundError):
        cart_service.get_cart(db, sid)
