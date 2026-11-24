"""Tests for order placement, validation, snapshots, and idempotency."""
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from app.database.models import Cart, MenuItem, Order, OrderIdempotency
from app.schemas.order_schema import OrderCreateRequest
from app.services import order_service


def _mock_db(item=None, order_exists=False, session_exists=True, cart=None, existing_idem=None):
    db = MagicMock()
    def _scalar(stmt):
        s = str(stmt).lower()
        if "order_idempotency" in s: return existing_idem
        if "orders" in s: return 1 if order_exists else None
        if "sessions" in s: return uuid4() if session_exists else None
        return None
    db.scalar.side_effect = _scalar
    db.get.side_effect = lambda model, id_: item if model is MenuItem and item and item.id == id_ else (cart if model is Cart else None)
    db.scalars.return_value.all.return_value = [item] if item else []
    def _add(obj):
        if hasattr(obj, "id") and not obj.id: obj.id = 101
    db.add.side_effect = _add
    return db


def test_successful_dine_in_and_takeaway():
    sid = uuid4()
    item = MenuItem(id=1, name="Coffee", price=Decimal("150.00"), is_available=True, deleted_at=None)
    cart = Cart(session_id=sid, state={"lines": [{"item_id": 1, "quantity": 2}]}, version=1)
    db = _mock_db(item=item, cart=cart)
    res_dine = order_service.create_order(db, sid, "dine_in", 1, table_number="4", contact=None, idempotency_key="k1")
    assert res_dine.order_id == 101 and res_dine.total == Decimal("300.00") and res_dine.table_number == "4" and cart.state["lines"] == []
    cart.state = {"lines": [{"item_id": 1, "quantity": 1}]}
    res_take = order_service.create_order(db, sid, "takeaway", 2, table_number=None, contact="99999", idempotency_key="k2")
    assert res_take.order_type == "takeaway" and res_take.contact == "99999"


def test_schema_validates_table_and_contact():
    sid = uuid4()
    with pytest.raises(ValueError, match="table_number is required"):
        OrderCreateRequest(session_id=sid, order_type="dine_in", cart_version=1, table_number=None)
    with pytest.raises(ValueError, match="contact"):
        OrderCreateRequest(session_id=sid, order_type="takeaway", cart_version=1, contact="")


def test_empty_and_stale_cart():
    sid = uuid4()
    db = _mock_db(cart=Cart(session_id=sid, state={"lines": []}, version=1))
    with pytest.raises(order_service.EmptyCartError):
        order_service.create_order(db, sid, "dine_in", 1, "1", None, "k1")
    db_stale = _mock_db(cart=Cart(session_id=sid, state={"lines": [{"item_id": 1, "quantity": 1}]}, version=3))
    with pytest.raises(order_service.StaleCartError):
        order_service.create_order(db_stale, sid, "dine_in", 1, "1", None, "k2")


def test_unavailable_item_and_db_price_recalculation():
    sid = uuid4()
    item_unavail = MenuItem(id=2, name="Soup", price=Decimal("120.00"), is_available=False, deleted_at=None)
    cart = Cart(session_id=sid, state={"lines": [{"item_id": 2, "quantity": 1}]}, version=1)
    with pytest.raises(order_service.ItemUnavailableError, match="no longer available"):
        order_service.create_order(_mock_db(item=item_unavail, cart=cart), sid, "dine_in", 1, "1", None, "k1")
    item_new_price = MenuItem(id=1, name="Coffee", price=Decimal("175.00"), is_available=True, deleted_at=None)
    cart2 = Cart(session_id=sid, state={"lines": [{"item_id": 1, "quantity": 2}]}, version=1)
    res = order_service.create_order(_mock_db(item=item_new_price, cart=cart2), sid, "dine_in", 1, "1", None, "k2")
    assert res.total == Decimal("350.00") and res.items[0].unit_price == Decimal("175.00")


def test_idempotency_same_and_different_payload():
    sid = uuid4()
    req_hash = order_service._hash_request({"session_id": str(sid), "order_type": "dine_in", "table": "1", "contact": None})
    existing_order = Order(id=55, session_id=sid, order_type="dine_in", table_number="1", status="placed", total_amount=Decimal("100.00"), items=[])
    existing_rec = OrderIdempotency(session_id=sid, idempotency_key="key-x", request_hash=req_hash, order=existing_order)
    db = _mock_db(existing_idem=existing_rec)
    res = order_service.create_order(db, sid, "dine_in", 1, "1", None, "key-x")
    assert res.order_id == 55
    with pytest.raises(order_service.IdempotencyConflictError):
        order_service.create_order(db, sid, "dine_in", 1, "99", None, "key-x")


def test_unknown_session_and_second_order():
    sid = uuid4()
    with pytest.raises(order_service.OrderSessionNotFoundError):
        order_service.create_order(_mock_db(session_exists=False), sid, "dine_in", 1, "1", None, "k1")
    with pytest.raises(order_service.OrderSessionClosedError):
        order_service.create_order(_mock_db(order_exists=True), sid, "dine_in", 1, "1", None, "k2")
