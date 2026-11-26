"""Concurrency and idempotency end-to-end tests."""
import pytest

pytestmark = pytest.mark.e2e

def test_concurrent_cart_updates_same_version(client):
    # Setup session and add initial item to reach version 2
    sid = client.post("/api/v1/sessions").json()["session_id"]
    client.post(f"/api/v1/cart/{sid}/items", json={"item_id": 1, "quantity": 1, "expected_version": 1})

    # First update with version 2 succeeds and increments version to 3
    res1 = client.patch(f"/api/v1/cart/{sid}", json={"item_id": 1, "quantity": 2, "expected_version": 2})
    assert res1.status_code == 200
    assert res1.json()["version"] == 3

    # Stale second update with old version 2 is rejected with 409
    res2 = client.patch(f"/api/v1/cart/{sid}", json={"item_id": 1, "quantity": 3, "expected_version": 2})
    assert res2.status_code == 409
    assert res2.json()["detail"]["version"] == 3

def test_idempotent_order_confirmation(client):
    # Setup cart with 1 item
    sid = client.post("/api/v1/sessions").json()["session_id"]
    client.post(f"/api/v1/cart/{sid}/items", json={"item_id": 1, "quantity": 1, "expected_version": 1})

    payload = {"session_id": sid, "order_type": "dine_in", "table_number": "5", "cart_version": 2}
    headers = {"Idempotency-Key": "test-key-100"}

    # Initial order placement succeeds
    res1 = client.post("/api/v1/orders", json=payload, headers=headers)
    assert res1.status_code == 201
    order_id = res1.json()["order_id"]

    # Replaying same request with same key returns original order without duplicate
    res2 = client.post("/api/v1/orders", json=payload, headers=headers)
    assert res2.status_code == 201
    assert res2.json()["order_id"] == order_id

    # Reusing same key with different payload is rejected with 409
    conflict_payload = {**payload, "table_number": "99"}
    res3 = client.post("/api/v1/orders", json=conflict_payload, headers=headers)
    assert res3.status_code == 409

    # Confirming a completed session under a new key is rejected with 409
    res4 = client.post("/api/v1/orders", json=payload, headers={"Idempotency-Key": "test-key-200"})
    assert res4.status_code == 409
