# Data Model

## 1. Excel menu specification

| Column | Required | Notes |
|---|---|---|
| `name` | **Yes** | Unique per item (used for upsert) |
| `price` | **Yes** | Positive number |
| `description` | **Yes** | Free text; may contain spice, ingredients, etc. |
| `category` | No | e.g., Beverages, Mains |
| `veg_nonveg` | No | `veg` / `non-veg` / `vegan` / `egg` |
| `spice_level` | No | `none` / `mild` / `medium` / `hot` |
| `prep_time_minutes` | No | Integer |
| `ingredients` | No | Comma-separated |
| `allergens` | No | Comma-separated (e.g., nuts, dairy, gluten) |
| `available` | No | yes/no, default yes |

Validation: reject rows missing required columns or with invalid price; report all errors at once; never silently skip rows.

## 2. Provided versus inferred data

Optional fields not supplied by the cafe may be extracted from the description by the LLM during ingestion. They are stored nullable, recorded in `inferred_fields`, and `needs_review` is set if any allergen or dietary field was inferred. The bot treats empty fields as unknown.

## 3. Postgres schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE menu_items (
  id               SERIAL PRIMARY KEY,
  name             TEXT NOT NULL UNIQUE,
  description      TEXT NOT NULL,
  price            NUMERIC(10,2) NOT NULL CHECK (price >= 0),
  category         TEXT,
  veg_type         TEXT CHECK (veg_type IN ('veg','non-veg','vegan','egg')),
  spice_level      TEXT CHECK (spice_level IN ('none','mild','medium','hot')),
  prep_time_minutes INT,
  ingredients      TEXT[],
  allergens        TEXT[],
  is_available     BOOLEAN NOT NULL DEFAULT TRUE,
  inferred_fields  TEXT[] NOT NULL DEFAULT '{}',   -- e.g. {'veg_type','allergens'}
  needs_review     BOOLEAN NOT NULL DEFAULT FALSE,
  content_hash     TEXT NOT NULL,                  -- detects text changes for re-embedding
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE menu_embeddings (
  item_id        INT PRIMARY KEY REFERENCES menu_items(id) ON DELETE CASCADE,
  embedded_text  TEXT NOT NULL,
  model          TEXT NOT NULL,
  embedding      vector(384) NOT NULL          -- dimension must match EMBEDDING_DIM
);
CREATE INDEX ON menu_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE TABLE sessions (
  id           UUID PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
  id          BIGSERIAL PRIMARY KEY,
  session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE carts (
  session_id  UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  state       JSONB NOT NULL,      -- LangGraph state incl. cart lines
  version     BIGINT NOT NULL DEFAULT 1, -- incremented on every successful cart mutation
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
  id            SERIAL PRIMARY KEY,
  session_id    UUID NOT NULL REFERENCES sessions(id),
  order_type    TEXT NOT NULL CHECK (order_type IN ('dine_in','takeaway')),
  table_number  TEXT,              -- required for dine_in
  contact       TEXT,              -- name or phone, required for takeaway
  status        TEXT NOT NULL DEFAULT 'placed'
                CHECK (status IN ('placed','preparing','ready','completed')),
  total_amount  NUMERIC(10,2) NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((order_type = 'dine_in' AND table_number IS NOT NULL)
      OR (order_type = 'takeaway' AND contact IS NOT NULL))
);

-- One successful order per idempotency key within a customer session.
CREATE TABLE order_idempotency (
  session_id       UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  idempotency_key  TEXT NOT NULL,
  request_hash     TEXT NOT NULL, -- detects key reuse with a different request
  order_id         INT NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
  response         JSONB NOT NULL, -- response returned for safe retries
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (session_id, idempotency_key)
);

CREATE TABLE order_items (
  id               SERIAL PRIMARY KEY,
  order_id         INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  menu_item_id     INT REFERENCES menu_items(id) ON DELETE SET NULL,
  item_name        TEXT NOT NULL,          -- snapshot
  unit_price       NUMERIC(10,2) NOT NULL, -- snapshot
  quantity         INT NOT NULL CHECK (quantity > 0),
  special_request  TEXT,                   -- flagged for staff, not guaranteed
  line_total       NUMERIC(10,2) NOT NULL
);

CREATE TABLE llm_fallback_log (
  id          BIGSERIAL PRIMARY KEY,
  from_model  TEXT NOT NULL,
  to_model    TEXT,
  reason      TEXT NOT NULL,     -- 429 | timeout | 5xx
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 4. Notes

- **Re-embedding:** compare `content_hash` of (name, description, category, ingredients). Changing `is_available` or `price` never triggers re-embedding.
- **Snapshots:** `order_items` stores name and price at order time, so later menu edits don't alter past orders.
- **Totals:** `line_total = unit_price * quantity` and `total_amount = sum(line_total)`, computed in Python from DB prices.
- **Cart concurrency:** every successful cart mutation increments `carts.version`. The API requires `expected_version` and performs a conditional update (`WHERE session_id = ... AND version = expected_version`) in a transaction. A zero-row update means the client is stale and receives `409` with the latest cart. This is optimistic concurrency control; no distributed lock is required for v1.
- **Order idempotency:** the unique `(session_id, idempotency_key)` constraint prevents duplicate successful orders. Store a hash of the normalized request and the original response; same key + same request returns the original result, while same key + different request returns `409`. Insert the order, order items, and idempotency record in one transaction.
- **Retention:** default to 30 days for chat messages and customer contact details. A scheduled cleanup job deletes expired `chat_messages` and clears/anonymizes `orders.contact` after 30 days; retain non-identifying order/item records for cafe operations. Make the duration configurable and document any exception before launch.
- **Embedding dimension:** changing embedding models requires altering the vector column and re-embedding everything.
- **HNSW:** the index is an implementation choice, not a requirement. Benchmark query latency and result quality against exact vector search using a representative menu before launch; for a few hundred items, exact search may be adequate.
