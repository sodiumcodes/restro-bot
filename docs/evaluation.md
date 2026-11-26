# Evaluation Plan

Goal: catch regressions in retrieval, ordering correctness, safety, and guardrails cheaply and repeatably.

## 1. Test set

30 to 50 scripted conversations stored in `backend/tests/eval/conversations.yaml`, each with turns and expected outcomes. Use a fixed test menu (`data/test_menu.xlsx`) including some items with missing optional fields and some unavailable items.

| Category | Count (target) | What it checks |
|---|---|---|
| Retrieval and suggestions | 10 | Relevant, available, correctly filtered items |
| Cart building and modification | 8 | Add, remove, change quantity, special requests |
| Summary and totals | 5 | Correct line totals and final amount |
| Order placement | 4 | Confirm flow, validation, conflict on unavailable item |
| Missing data and allergens | 5 | "Not specified" behavior, no guarantees |
| Unhappy paths | 6 | Not on menu, ambiguous, off-topic, unavailable mid-order |
| Guardrails | 6 | Prompt injection, profanity, length, invented dishes |
| Router fallback | 2 | Simulated 429 triggers fallback and a log entry |

## 2. Automated checks

**Deterministic (unit/integration tests, run on every change)**
- Totals equal the sum of DB prices times quantities.
- Cart PATCH updates quantity and special requests without invoking the LLM; quantity 0 removes a line.
- Cart mutation with the current version succeeds and increments the version; a stale version returns `409` and does not overwrite the newer cart.
- Two concurrent mutations against the same cart version cannot both silently overwrite state.
- Repeating an order request with the same idempotency key and same payload returns the same order ID and creates only one order.
- Reusing an idempotency key with a different payload returns `409`.
- Order cannot be placed without the Confirm endpoint.
- Dine-in requires table; takeaway requires contact.
- Unavailable items are never suggested or ordered.
- Ingestion: rejects missing required columns; idempotent; re-embeds only changed items; availability toggle doesn't re-embed.
- Output validator rejects a reply containing a dish or price not in the DB.

**Retrieval metrics** (on labeled queries with expected items)
- Recall@5: expected item appears in top 5.
- Filter correctness: 100% of returned items satisfy hard filters (available, veg).

**LLM-behavior checks** (run against a real or stubbed model; judged by assertions or an LLM judge)
- No invented dishes or prices.
- No allergy guarantees.
- Correct "not specified" phrasing for empty fields.
- Special requests recorded but not promised.

## 3. Pass criteria

| Metric | Threshold |
|---|---|
| Bill accuracy | 100% |
| Orders placed without Confirm action | 0 |
| Invented dish or price reaching the user | 0 |
| Unavailable item suggested | 0 |
| Allergen guarantee statements | 0 |
| Prompt-injection cases handled safely | 100% |
| Recall@5 on retrieval set | ≥ 90% |
| Overall conversation pass rate | ≥ 90% |
| Fallback triggers correctly on simulated 429 | 100% |

## 4. Process

1. Run the deterministic suite in CI on every commit.
2. Run the full conversation set before each release, and whenever the prompt, model list, embedding model, or menu schema changes.
3. Record results with date and model versions in `docs/eval-results/` (or CI artifacts).
4. Add a new test for every bug found in production.

## 5. Manual checks before going live

- Staff review of all `needs_review` items, especially inferred allergens.
- Test run of the full flow on a phone (dine-in and takeaway).
- Load test with a few simultaneous chats and concurrent cart updates to observe rate limiting, version conflicts, and fallback.
- Verify session IDs are validated and every customer endpoint is scoped to the owning session; verify rate limits on session creation and cart/order mutations.
- Verify the scheduled retention job deletes chat messages and clears/anonymizes contact details older than 30 days.
- Benchmark HNSW against exact vector search using the representative menu; retain HNSW only if it provides a measurable benefit without unacceptable retrieval-quality loss.
- Confirm the confirmation screen mentions the staff-provided bill and QR.

## 6. Running Tests

### Unit Tests
Run standard unit tests (fast, in-memory mocks):
```bash
cd backend
python -m pytest -m "not e2e"
```

### End-to-End & Integration Tests
Run end-to-end customer flow, concurrency, conversation, and security tests against the test PostgreSQL database:
```bash
cd backend
python -m pytest -m e2e
```

### Full Test Suite
Run the entire test suite (all unit and e2e integration tests):
```bash
cd backend
python -m pytest
```
