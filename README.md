# Shakers AI Case Study — Intelligent Support + Recommendations

AI-powered assistant for answering knowledge-base (KB) questions in English, using FastAPI, ChromaDB, and retrieval-augmented generation (RAG).

# Project Structure

app/
 ├── routers/        # API endpoints (query, health, etc.)
 ├── services/       # Core services (retrieval, indexing, etc.)
 ├── utils/          # Helpers (chunking, metadata, OOS detection)
 └── data/           # Knowledge base docs (English only)
scripts/
 └── index_kb.py     # Script to index KB into Chroma
store/
 └── chroma/         # Local Chroma vector DB (ignored in Git)
tests/               # Unit/integration tests

# Architecture Overview

          ┌──────────────┐
          │   Client      │
          │ (API caller)  │
          └──────┬───────┘
                 │  POST /query
                 ▼
          ┌──────────────┐
          │   FastAPI     │
          │   (routers)   │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │  Retrieval    │
          │  (ChromaDB)   │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │   LLM         │
          │ (OpenAI etc.) │
          └──────┬───────┘
                 │
                 ▼
          ┌──────────────┐
          │  Response     │
          │ (answer + src)│
          └──────────────┘



# SETUP


1 - Clone the repo

git clone https://github.com/VictorHernandoParral/shakers-ai-case-study.git
cd shakers-ai-case-study


2 - Install dependencies (with Poetry)

poetry install


3 - Environment variables
Copy .env.example to .env and set:

OPENAI_API_KEY=sk-...
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


By default:

Local dev: http://127.0.0.1:8000

Explicit host: http://0.0.0.0:8000 (useful in Docker/VMs)

Test health:

curl http://127.0.0.1:8000/health

# Query Endpoint

Example request:

curl -X POST "http://127.0.0.1:8000/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u123",
    "query": "How do payments work?"
  }'


Example response:

{
  "answer": "Payments are processed via...",
  "sources": [
    {"id": "doc1", "title": "Payments FAQ", "url": "https://..."}
  ],
  "latency_ms": 120,
  "oos": false
}

# Metrics

A /metrics endpoint is available for observability:

query_latency_ms

retrieved_docs_count

oos_rate

query_count

# Testing

Run unit + integration tests:

poetry run pytest -v

# Notes

All answers must be in English only (enforced by prompt).

OOS detection via similarity threshold (MIN_SIMILARITY in .env).

KB expansion is manual: add English docs under app/data/kb/ and re-run index.


