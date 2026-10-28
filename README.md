# E-Commerce AI Support Agent

A **ReAct agent** for e-commerce customer support, built with **LangGraph**, **FastAPI**, **Streamlit**, **SQLite**, and optional **Langfuse** tracing.

## Architecture

```
Streamlit UI ──► FastAPI  POST /api/v1/chat ──► LangGraph agent ──► SQLite
                                                     │
                                                     └── Langfuse (optional tracing)
```

Each request flows through a 3-node graph:

```
START → triage ─┬─(needs tools)→ tools ─┬─(ok)──────────────────► response → END
                │                       └─(tool crash, < 3 tries)→ tools
                └─(general)────────────────────────────────────► response → END
```

| Node | Job |
|---|---|
| **triage** | LLM structured output → intent + order ID / tracking number / email |
| **tools** | LLM function-calling picks from 7 tools and runs them |
| **response** | LLM writes the customer reply from the tool results only |

**Tools:** `lookup_order` · `lookup_orders_by_email` · `search_orders` · `track_shipment` · `get_return_policy` · `check_return_eligibility` · `initiate_return`

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set OPENAI_API_KEY
python run.py                 # API on :8000/docs, chat UI on :8501
```

Or run them separately:

```bash
uvicorn src.main:app --reload
streamlit run src/ui/streamlit_app.py
```

The SQLite database (`data/ecommerce.db`) is created and seeded on first start: 12 orders and 9 shipments, with dates relative to today.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | `{"status":"ok","version":"1.0.0"}` |
| `POST` | `/api/v1/chat` | `{"message": "...", "session_id": "optional"}` → agent reply |

Reuse a `session_id` and the agent remembers the last 10 turns, so follow-ups like *"can I return it?"* work.

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the status of ORD-1002?", "session_id":"demo"}'
```

## Sample queries

| Query | Expected path |
|---|---|
| `What's the status of order ORD-1002?` | `lookup_order` |
| `Where is package FDX-78901234?` | `track_shipment` |
| `Track UPS-99887766` | `track_shipment` (out for delivery) |
| `What is your return policy?` | `get_return_policy` |
| `Show orders for james@example.com` | `lookup_orders_by_email` |
| `Find my keyboard order` | `search_orders("keyboard")` |
| `Can I return ORD-1005?` | `check_return_eligibility` ✅ |
| `Return ORD-1005, it's defective` | `initiate_return` → RMA number |
| `I need to return ORD-1008` | denied (outside 14-day window) |

## Tests

```bash
pytest -q
```

30 tests covering services, tools, graph routing, and the API. They use a throwaway database and need no LLM credentials.

## Observability

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env` to trace every LLM call, tool run, latency and token cost. Without the keys, tracing is off.

## Project layout

```
src/
├── config.py                  # settings from .env
├── main.py                    # FastAPI app (DB seed + Langfuse on startup)
├── agent/   state.py · tools.py · nodes.py · graph.py
├── services/ database.py · order_service.py · shipping_service.py · returns_service.py
├── api/     schemas.py · routes.py
├── observability/langfuse_setup.py
└── ui/streamlit_app.py
tests/  conftest.py · test_agent.py
run.py                         # launches API + UI
```

## License

MIT
