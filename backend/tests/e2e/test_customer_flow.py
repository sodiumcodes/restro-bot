"""Full customer ordering lifecycle end-to-end tests."""
from decimal import Decimal
import pytest
from app.core.config import settings

pytestmark = pytest.mark.e2e

def test_full_customer_ordering_flow(client):
    # 1. Anonymous session creation
    session_res = client.post("/api/v1/sessions")
    assert session_res.status_code == 201
    sid = session_res.json()["session_id"]

    # 2. Initial empty cart retrieval
    cart_res = client.get(f"/api/v1/cart/{sid}")
    assert cart_res.status_code == 200 and cart_res.json()["version"] == 1

    # 3. Add items and update quantities with special requests
    add_res = client.post(f"/api/v1/cart/{sid}/items", json={"item_id": 1, "quantity": 1, "expected_version": 1})
    assert add_res.status_code == 200 and add_res.json()["version"] == 2

    patch_res = client.patch(f"/api/v1/cart/{sid}", json={"item_id": 1, "quantity": 2, "special_request": "extra crispy", "expected_version": 2})
    assert patch_res.status_code == 200 and patch_res.json()["total"] == "500.00"

    add_res2 = client.post(f"/api/v1/cart/{sid}/items", json={"item_id": 2, "quantity": 1, "expected_version": 3})
    assert add_res2.status_code == 200 and add_res2.json()["total"] == "720.00"

    # 4. Explicit order confirmation with dine-in details and idempotency key
    order_payload = {"session_id": sid, "order_type": "dine_in", "table_number": "7", "cart_version": 4}
    order_res = client.post("/api/v1/orders", json=order_payload, headers={"Idempotency-Key": "flow-key-1"})
    assert order_res.status_code == 201
    order_data = order_res.json()
    assert order_data["total"] == "720.00" and order_data["status"] == "placed"
    order_id = order_data["order_id"]

    # 5. Verify chat is locked after order completion
    chat_res = client.post("/api/v1/chat", json={"session_id": sid, "message": "hello"})
    assert chat_res.status_code == 409

    # 6. Verify staff can view and transition order lifecycle
    staff_headers = {"X-Staff-Key": settings.STAFF_API_KEY.strip()}
    orders_list = client.get("/api/v1/staff/orders?status=placed", headers=staff_headers)
    assert orders_list.status_code == 200
    assert any(o["order_id"] == order_id for o in orders_list.json())

    update_res = client.patch(f"/api/v1/staff/orders/{order_id}", json={"status": "preparing"}, headers=staff_headers)
    assert update_res.status_code == 200 and update_res.json()["status"] == "preparing"
