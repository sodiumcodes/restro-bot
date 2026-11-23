"""Tests for staff authentication, order management, availability, and menu review."""
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app.core import security
from app.database.models import MenuItem, Order
from app.services import staff_service


def test_auth_security(monkeypatch):
    monkeypatch.setattr(security.settings, "STAFF_API_KEY", "correct-key")
    # Correct key passes
    assert security.verify_staff_key("correct-key") == "correct-key"
    # Missing key raises 401
    with pytest.raises(HTTPException) as exc: security.verify_staff_key(None)
    assert exc.value.status_code == 401
    # Wrong key raises 401
    with pytest.raises(HTTPException) as exc: security.verify_staff_key("wrong-key")
    assert exc.value.status_code == 401
    # Unconfigured key raises 401
    monkeypatch.setattr(security.settings, "STAFF_API_KEY", None)
    with pytest.raises(HTTPException) as exc: security.verify_staff_key("correct-key")
    assert exc.value.status_code == 401


def test_order_listing_and_not_found():
    db = MagicMock()
    order = Order(id=1, status="placed", order_type="dine_in", table_number="3", total_amount=Decimal("100.00"), items=[])
    db.scalars.return_value.all.return_value = [order]
    orders = staff_service.list_orders(db, status="placed")
    assert len(orders) == 1 and orders[0].order_id == 1
    # Unknown order raises 404
    db.get.return_value = None
    with pytest.raises(staff_service.OrderNotFoundError):
        staff_service.get_order(db, 999)


def test_order_status_transitions():
    db = MagicMock()
    order = Order(id=1, status="placed", order_type="dine_in", table_number="3", total_amount=Decimal("100.00"), items=[])
    db.get.return_value = order
    # Valid transition: placed -> preparing
    res = staff_service.update_order_status(db, 1, "preparing")
    assert res.status == "preparing"
    # Invalid transition: preparing -> placed
    with pytest.raises(staff_service.InvalidStatusTransitionError):
        staff_service.update_order_status(db, 1, "placed")


def test_availability_toggle():
    db = MagicMock()
    item = MenuItem(id=1, name="Tea", price=Decimal("50.00"), is_available=True, inferred_fields=[], needs_review=False, deleted_at=None)
    db.scalar.return_value = item
    res = staff_service.toggle_item_availability(db, 1, False)
    assert res.is_available is False and item.is_available is False
    # Unknown item raises MenuItemNotFoundError
    db.scalar.return_value = None
    with pytest.raises(staff_service.MenuItemNotFoundError):
        staff_service.toggle_item_availability(db, 999, True)


def test_menu_review_and_content_hash():
    db = MagicMock()
    item = MenuItem(
        id=2, name="Pasta", description="Creamy pasta", price=Decimal("220.00"), category="Mains", veg_type="veg",
        spice_level="mild", ingredients=["flour"], allergens=["dairy"], is_available=True,
        inferred_fields=["allergens"], needs_review=True, content_hash="old-hash", deleted_at=None
    )
    db.scalar.return_value = item
    db.scalars.return_value.all.return_value = [item]
    # List review items
    assert len(staff_service.list_review_items(db)) == 1
    # Review update confirms allergens and removes from inferred
    res, hash_changed = staff_service.review_menu_item(db, 2, {"allergens": ["dairy", "gluten"], "needs_review": False})
    assert res.needs_review is False and "allergens" not in res.inferred_fields and hash_changed is True
