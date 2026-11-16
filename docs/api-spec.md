# API Spec

FastAPI auto-generates interactive docs at `/docs`; this file records the intended contract. Base path: `/api`. JSON everywhere.

**Auth:** customer endpoints use an anonymous `session_id`. Staff endpoints require header `X-Staff-Key: <STAFF_API_KEY>`.

## Customer endpoints

### `POST /api/sessions`
Create an anonymous session.
Response `201`: `{ "session_id": "uuid" }`

### `POST /api/chat`
Send a user message through guardrails and the LangGraph flow.

Request:
```json
{ "session_id": "uuid", "message": "something spicy and vegetarian" }
```
Response `200`:
```json
{
  "reply": "Here are a few options...",
  "suggestions": [
    { "item_id": 12, "name": "Paneer Tikka", "price": 220.00, "veg_type": "veg" }
  ],
  "cart": { "lines": [], "total": 0.00 },
  "summary": null,
  "stage": "suggesting"
}
```
`summary` is non-null when the bot shows the order summary (see cart shape below). Errors: `400` blocked/invalid input (with a friendly message), `404` unknown session, `429` rate limited, `503` all models unavailable.

### `GET /api/cart/{session_id}`
Current cart, including its concurrency version.

Response:
```json
{
  "session_id": "uuid",
  "version": 4,
  "lines": [
    {
      "item_id": 12, "name": "Paneer Tikka", "quantity": 2,
      "unit_price": 220.00, "line_total": 440.00,
      "special_request": "less spicy"
    }
  ],
  "total": 440.00
}
```
All numbers and the version are supplied by the backend.

### `PATCH /api/cart/{session_id}`
Update a cart line directly from the UI. This endpoint is for quantity steppers and special-request fields; these deterministic mutations do not go through the LLM.

Request:
```json
{
  "item_id": 12,
  "quantity": 2,
  "special_request": "less spicy",
  "expected_version": 4
}
```
`quantity` is the desired quantity, not a delta. Set it to `0` to remove the item. `special_request` may be omitted to leave it unchanged; send an empty string to clear it. The backend validates the item and quantity limit, recomputes totals from current database prices, and atomically updates the cart only if `expected_version` matches the current cart version. Each successful mutation increments the version.

Response `200`: same cart shape as `GET /api/cart/{session_id}`, with the new version. Errors: `404` unknown session/item, `409` stale cart version (return the current cart/version so the client can refresh and reconcile), `422` invalid quantity or request.

### `POST /api/orders`
Explicit confirmation. The only way to place an order. The request must include an `Idempotency-Key` header (a unique client-generated key for this confirmation attempt). Repeating the same key for the same session and same request returns the original order result; reusing it with a different request returns `409`.

Request:
```json
{
  "session_id": "uuid",
  "order_type": "dine_in",
  "table_number": "7",
  "contact": null
}
```
Rules: `dine_in` requires `table_number`; `takeaway` requires `contact` (name or phone). Re-validates availability and prices. The backend creates the order, order items, and idempotency record in one database transaction. A retry with the same key must not create another order.

Response `201`:
```json
{
  "order_id": 101,
  "status": "placed",
  "items": [ ... ],
  "total": 440.00,
  "message": "Your order is placed. Our staff will share the final bill and payment QR with you."
}
```
Errors: `409` an item is no longer available (body lists affected items), idempotency key reused with a different request, or a cart changed since the client last loaded it; `422` validation (missing table or contact, empty cart), `404` unknown session.

## Staff endpoints (require `X-Staff-Key`)

### `GET /api/staff/orders?status=placed`
List orders (newest first), with items, special requests, order type, table or contact.

### `PATCH /api/staff/orders/{order_id}`
`{ "status": "preparing" }` where status is one of `placed | preparing | ready | completed`.

### `PATCH /api/staff/menu/{item_id}/availability`
`{ "is_available": false }`. Does not trigger re-embedding.

### `GET /api/staff/menu/review`
Items with `needs_review = true` and their inferred fields.

### `PATCH /api/staff/menu/{item_id}`
Correct fields (e.g., allergens) and clear `needs_review`. Corrected fields are removed from `inferred_fields`.

### `POST /api/staff/menu/upload`
Upload an Excel file; runs the same ingestion as the CLI script. Returns a validation and ingestion report. (Optional for v1; CLI is the baseline.)

## Utility

### `GET /health`
`{ "status": "ok", "db": "ok" }`

## Error format

```json
{ "error": { "code": "item_unavailable", "message": "...", "details": {} } }
```

## Cross-cutting rules

- Per-session and per-IP rate limits on `/api/chat`; apply appropriate limits to session creation and cart/order mutations as well.
- Message length limit (`MAX_MESSAGE_LENGTH`).
- CORS limited to the frontend origin.
- `session_id` is an opaque identifier, not proof of identity. Generate it with a cryptographically secure UUID; validate that it exists and scope every customer read/write to that session. Never accept a session ID from a different resource or return another session's data.
- Rate-limit session creation and sensitive mutations to reduce abuse. Do not treat UUID unpredictability as a substitute for authorization checks.
- Staff endpoints currently use the shared `X-Staff-Key` for v1. Store it as a secret and compare it securely. Individual staff identities and role-based permissions are a later hardening step, not part of the current v1 contract.
- Retention: delete chat messages and purge/anonymize order contact details 30 days after creation using a scheduled cleanup job; make the period configurable and document any operational/legal exception before launch.
