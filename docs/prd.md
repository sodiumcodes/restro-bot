# Product Requirements Document (PRD)

**Product:** Cafe Ordering Chatbot (v1)
**Status:** Draft

## 1. Overview

A chat-only ordering assistant for one cafe/restaurant. Customers order by chatting with the bot instead of using an app or waiting for staff. The bot's responsibility ends when the order is placed; billing and payment happen outside the system, handled by staff.

## 2. Goals

- Let a customer go from "I'm hungry" to a placed order using natural language only.
- Suggest relevant, currently available dishes accurately.
- Present a clear, correct order summary before the order is placed.
- Give staff a reliable list of incoming orders.
- Be safe about allergens and dietary claims: only state what the data says.

## 3. Non-goals (out of scope for v1)

Payments and QR generation, user accounts/login, loyalty, multi-branch support, voice, delivery tracking, customer-facing order status tracking, recommendations based on history, multilingual support, multi-order sessions or consolidated billing.

## 4. Users

- **Customer:** anyone visiting the cafe (dine-in or takeaway). Anonymous, no login.
- **Staff:** cafe employees who view/update orders, manage availability, and review menu data. (Secondary user, minimal UI.)

**Scope:** one individual cafe. If it has branches, still treated as a single cafe.

## 5. User flow

1. **Request:** customer states a need in chat.
2. **Suggest:** bot checks availability and suggests matching items.
3. **Select:** customer chooses one or more dishes, quantities, optional special requests.
4. **Summary:** bot shows a receipt-style summary: item, special requests, quantity, unit price, line total, final amount.
5. **Decision:**
   - **Confirm:** customer presses the Confirm button, the order is placed, and a confirmation screen says staff will share the final bill and payment QR.
   - **Change:** customer asks for changes or special requests, and the flow returns to step 2.

Order identification: dine-in requires a table number; takeaway requires a name or phone number. This exists only so staff can find the customer.

## 6. Functional requirements

### Chat and menu
- FR-1: Accept free-text requests in English.
- FR-2: Retrieve candidates via semantic search, filtered first by structured fields (available, veg, category, etc.).
- FR-3: Only suggest items that are currently available. If an item becomes unavailable mid-order, notify the user and offer alternatives.
- FR-4: Handle vague requests ("something light") by suggesting options or asking at most one clarifying question.
- FR-5: Politely decline requests for items not on the menu and off-topic questions.

### Cart and summary
- FR-6: Maintain a cart per anonymous session (items, quantities, per-item special requests), persisted server-side.
- FR-7: Compute all prices and totals in backend code from database prices.
- FR-8: Special requests are stored as free text per item, flagged for staff, and never promised as guaranteed.
- FR-9: Show the summary with all required details before confirmation.
- FR-9a: UI quantity and special-request edits update the persisted cart through a dedicated backend cart mutation endpoint, without an LLM round trip.
- FR-9b: Cart mutations use optimistic concurrency control; stale updates are rejected and the client refreshes the current cart.

### Order placement
- FR-10: Order placement happens only via an explicit Confirm action calling a backend endpoint.
- FR-11: Re-validate availability and prices at confirmation time and use database prices.
- FR-12: Require order type (dine-in/takeaway) and the matching contact field before placing.
- FR-13: Confirmation screen states staff will share the final bill and payment QR.
- FR-13a: Order confirmation is idempotent; retries of the same confirmation request must return the original order rather than create duplicates.

### Staff
- FR-14: Staff can list incoming orders and update status: placed, preparing, ready, completed.
- FR-15: Staff can toggle item availability without re-embedding.
- FR-16: Staff can see menu items flagged for review (inferred fields, especially allergens).

### Menu ingestion
- FR-17: Menu loaded from an Excel sheet; required columns: name, price, description.
- FR-18: Optional columns: category, veg/non-veg, spice level, prep time, ingredients, allergens, available.
- FR-19: Missing optional fields are extracted from descriptions by the LLM, stored as nullable and marked **inferred**.
- FR-20: The ingestion script is validating, idempotent, and re-runnable; embeddings regenerate only when item text changes.

### Safety and guardrails
- FR-21: Input guardrails: prompt-injection detection, off-topic detection, profanity filter, length limit.
- FR-22: Output guardrails: every dish and price in a response is validated against the database; no invented items; no medical or allergy guarantees; stay on topic.
- FR-23: If a data field is empty, the bot says "not specified, please check with staff."

### Reliability
- FR-24: `llm_router` falls back across an ordered list of models/providers on rate limit (429) or timeout, and logs every fallback.

## 7. Non-functional requirements

- **Correctness:** zero tolerance for wrong totals; totals are deterministic code.
- **Latency:** typical bot reply under ~4 seconds on the free tier (target, not guarantee).
- **Availability under free-tier limits:** graceful degradation through model fallback, with a friendly error if all are exhausted.
- **Security:** API keys only in environment variables; staff endpoints protected by a shared v1 key; customer session IDs are identifiers, not authentication, so every request must validate and be scoped to its session; rate-limit chat, session creation, and cart/order mutations. Individual staff authentication and role-based permissions are future hardening.
- **Concurrency:** concurrent cart changes must not silently overwrite newer state; use a cart version and reject stale writes.
- **Idempotency:** duplicate Confirm submissions/retries with the same idempotency key must not create multiple orders.
- **Privacy/retention:** retain chat messages and customer contact details for 30 days by default, then delete/anonymize them through a scheduled cleanup process. Make the period configurable and resolve any exceptions before launch.
- **Maintainability:** embedding provider and LLM provider each behind a small interface.
- **Privacy:** contact details are used only for staff identification.

## 8. Success metrics

- Order completion rate (sessions reaching Confirm / sessions with at least one item added).
- Retrieval quality on the evaluation set (see `evaluation.md`).
- Bill accuracy: 100% of orders match database prices.
- Hallucination rate: 0 invented dishes/prices reaching users.
- Fallback rate of LLM models (monitoring signal).
- Staff-reported mismatches (e.g., wrong orders).

## 9. Assumptions and risks

| Item | Notes |
|---|---|
| Groq free-tier limits | Several simultaneous users may hit limits; mitigated by `llm_router`. |
| OpenRouter embeddings | Availability and cost vary; local sentence-transformers is the fallback. |
| Messy menu data | LLM-inferred fields can be wrong; marked inferred, staff review required for allergens. |
| Allergen safety | Bot never guarantees; defers to staff when uncertain. |
| Cart update races | Optimistic version checks reject stale cart mutations; frontend refreshes current state. |
| Duplicate confirmation | Idempotency key plus a database uniqueness constraint prevents duplicate orders on retries. |
| Session misuse | UUIDs are not treated as authentication; enforce session scoping and rate limits. |
| Retention job failure | Monitor the scheduled cleanup job and document the 30-day retention policy before launch. |

## 10. Roadmap

- **v1 (this PRD):** chat ordering, order placement, staff order view, menu ingestion.
- **v1.1:** table QR codes prefilling table number; customer-facing order status.
- **v2:** payments/QR integration, multi-order sessions and consolidated bills, order history.
- **Later:** multilingual, voice, multi-branch, loyalty and personalised recommendations.
