# Shakers AI Case Study — Intelligent Support + Recommendations

A Retrieval-Augmented Generation (RAG) chatbot for Shakers’ knowledge base.  
It answers user questions with grounded content from your KB and proposes personalized follow-ups.


# Project Structure

app/
main.py # FastAPI app
routers/
query.py # /query endpoint (RAG + generation)
recommend.py # /recommend endpoint (follow-ups)
metrics.py # optional health/metrics
services/
retrieval.py # Chroma collection + similarity search
generation.py # OpenAI wrapper + robust retries
recommender.py # candidate pool + MMR + padding (>=2 items)
utils/
prompting.py # message builder (definition-first)
answer_post.py # clean/remove headings, strip echoes
sanitize.py # context & output sanitizer (labels, ****)
rcache.py # response cache
reranker.py # cross-encoder (optional)
compressor.py # sentence selector (optional)
scripts/
streamlit_app.py # simple front-end
index_kb.py # KB indexing script


# Architecture Overview

          ┌──────────────┐
          │   Client     │
          │ (API caller) │
          └──────┬───────┘
                 │  POST /query
                 ▼
          ┌──────────────┐
          │   FastAPI    │
          │   (routers)  │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │  Retrieval   │
          │  (ChromaDB)  │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │   LLM        │
          │ (OpenAI etc.)│
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │  Response    │
          │(answer + src)│
          └──────────────┘



## ⚙️ Requirements

- **Python 3.11+**
- **Poetry**
- OpenAI API key

---

## 🔐 Environment

Create `.env` in repo root:

```ini
OPENAI_API_KEY=sk-xxx


## SETUP


1 - Clone the repo

git clone https://github.com/VictorHernandoParral/shakers-ai-case-study.git
cd shakers-ai-case-study


2 - Install dependencies (with Poetry)

poetry install


3 - Environment variables
Copy .env.example to .env and set:

OPENAI_API_KEY=
CHROMA_PATH=store/chroma
COLLECTION_NAME=shakers-kb
MIN_SIMILARITY=0.75

4 - Index the Knowledge Base

To ingest KB docs (in app/data/kb/):

poetry run python -m scripts.index_kb


This will:

Chunk docs into ~400–800 char pieces.

Enrich chunks with metadata (doc_id, chunk_id, lang, doctype).

Store embeddings into Chroma at store/chroma.

⚠️ Note: store/chroma/ is ignored in Git, rebuild locally if needed.

5 - Run the API

Start FastAPI app:

poetry run uvicorn app.main:app --reload


6 - Run the UI

poetry run streamlit run scripts\streamlit_app.py


## How it works (RAG flow)

Retrieve: query → Chroma similarity search over KB chunks.

(Optional) Re-rank and compress: reorder + trim context.

Generate: OpenAI (gpt-4o-mini) produces a definition-first answer.

Clean: strip headings/labels/****, remove any echoed question.

Recommend: MMR + padding → ≥2 follow-ups, excluding the main topic.

Render: UI shows answer, references, recommendations, and history.


## Endpoints

POST /query

Body: { "query": "string", "top_k": (optional) }

Resp: { "answer": "string", "references": [...], "recommendations": [...], "meta": {...} }

POST /recommend

Body: { "question":"string", "ctx": {"session_id":"string"}, "k": 3 }

Resp: { "items": [{ "id", "title", "url", "reason" }] }


# Metrics

A /metrics endpoint is available for observability:

query_latency_ms

retrieved_docs_count

oos_rate

query_count


## Out-of-Scope (OOS) Detection

The system detects queries that fall outside the knowledge base (KB) and returns a safe fallback response without calling an LLM.

**How it works**
- Retrieval returns ranked chunks with either `distance ∈ [0,1]` (lower is closer) or `similarity ∈ [0,1]`.
- The OOS gate evaluates:
  - `SIM_MIN`: required absolute top similarity (via `1 - distance`).
  - `MARGIN_MIN`: required margin between top-1 and top-2 similarities.
  - `REQUIRE_TOPK`: margin is only applied when at least this many chunks exist.
- If the gate triggers, the API responds with:
  ```json
  {
    "answer": "I don't have information on this. Please ask me something related to the Shakers platform (e.g., payments, project workflow, freelancers, etc.).",
    "sources": [],
    "oos": true
  }


### Recommendation Service

**Endpoint**
`POST /recommend`
Request: `{ "user_id": string, "query": string }`  
Response: `{ "recommendations": [{ "id": string|null, "title": string, "url": string, "reason": string }] }`

**How it works**
1) Builds a lightweight user profile (recent queries and seen resources).
2) Retrieves candidate resources from the KB.
3) Filters out already seen items per user.
4) Applies a simple MMR diversification to ensure topic variety.
5) Returns 2–3 items, each with a brief explanation of relevance.

**Profile updates**
- Profiles are updated on each `/recommend` call.
- Profiles are also updated after `/query` answers (query appended; sources marked as seen).
- Storage: JSON file at `app/data/profiles/profiles.json`.


# Notes

All answers must be in English only (enforced by prompt).

OOS detection via similarity threshold (MIN_SIMILARITY in .env).

KB expansion is manual: add English docs under app/data/kb/ and re-run index.

Latency depends on model & context size. Repeated queries are faster thanks to the cache.


## 🧾 License / Ownership
Internal use for the Shakers AI case study. 

