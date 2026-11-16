# Cafe Ordering Chatbot

A chat-only ordering assistant for a single cafe/restaurant. Customers chat to browse the menu, add dishes, review an order summary, and place the order. The bot's job ends the moment the order is placed. Staff share the final bill and payment QR in person.

## How it works

1. Customer asks for something in chat ("something spicy and vegetarian").
2. The bot searches the menu (semantic search + exact database filters) and suggests available items.
3. Customer picks one or more dishes, with optional special cooking requests.
4. The bot shows an order summary (items, quantities, requests, prices, total). Totals are computed in backend code, never by the LLM.
5. Customer presses **Confirm order** (a real button that calls the backend) or asks for changes (back to step 2).

After confirmation the screen states that staff will share the final bill and payment QR.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js + Tailwind CSS |
| Backend | FastAPI |
| Orchestration | LangGraph (state machine) |
| LLM | Groq, behind an `llm_router` with model/provider fallback |
| Embeddings | OpenRouter (verify availability/cost) or local sentence-transformers fallback, behind a small interface |
| Database | PostgreSQL + pgvector (single database for relational data and vectors) |
| Menu source | Excel sheet (`.xlsx`) |

## Repository layout

```
cafe-chatbot/
├── README.md
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── data-model.md
│   ├── api-spec.md
│   ├── conversation-design.md
│   └── evaluation.md
├── backend/          # FastAPI app, LangGraph graph, llm_router, guardrails, ingestion
├── frontend/         # Next.js + Tailwind
├── data/             # sample menu only (never real customer data)
├── .env.example
└── docker-compose.yml  # local Postgres with pgvector
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for local Postgres + pgvector) or a hosted Postgres with pgvector (Supabase / Neon free tiers)
- A Groq API key; an OpenRouter API key (if using OpenRouter embeddings)

## Environment variables

Copy `.env.example` to `.env` and fill in values. **Never commit `.env`.**

```
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/cafe

# LLM (Groq) - model fallback order is defined in backend/config/llm_models.yaml
GROQ_API_KEY=

# Embeddings
EMBEDDING_PROVIDER=openrouter        # openrouter | local
OPENROUTER_API_KEY=
EMBEDDING_MODEL=                     # fill after checking OpenRouter's current list
EMBEDDING_DIM=384                    # must match the model and the pgvector column

# App
STAFF_API_KEY=                       # protects staff/admin endpoints
CORS_ORIGINS=http://localhost:3000
MAX_MESSAGE_LENGTH=500
```

## Setup and run

```bash
# 1. Database
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                 # create tables + enable pgvector
uvicorn app.main:app --reload        # http://localhost:8000  (API docs at /docs)

# 3. Frontend
cd ../frontend
npm install
npm run dev                          # http://localhost:3000
```

## Loading or updating the menu

Only three columns are required: **name**, **price**, **description**. Everything else is optional (category, veg/non-veg, spice level, prep time, ingredients, allergens, available).

```bash
cd backend
python -m scripts.ingest_menu ../data/menu.xlsx
```

The script is re-runnable: it validates the sheet, upserts items, uses the LLM to extract missing fields from free-text descriptions (stored as **inferred**), regenerates embeddings only for items whose text changed, and prints a report of items needing review.

Cafe staff should review items flagged `needs_review`, especially inferred **allergen** data, before going live. Toggling availability does not require re-embedding.

## Key design rules

- Availability, price and dietary data come from Postgres, never from the LLM or from embeddings.
- The LLM never calculates prices or totals.
- Only a button/endpoint places an order; LLM text never does.
- If a field is empty, the bot says "not specified, please check with staff" rather than guessing. No allergy guarantees.
- Every item and price in a bot reply is validated against the database before it is shown.

## Documentation

- [PRD](docs/prd.md)
- [Architecture](docs/architecture.md)
- [Data model](docs/data-model.md)
- [API spec](docs/api-spec.md)
- [Conversation design](docs/conversation-design.md)
- [Evaluation plan](docs/evaluation.md)
