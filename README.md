# Shakers AI Case Study — Intelligent Support + Recommendations

**Tech:** FastAPI, FAISS/Chroma, Sentence-Transformers, SQLModel, Streamlit

## Install
1) Install Poetry and run `make setup`
2) Build KB index with `make index`
3) Run API with `make run` → open http://localhost:8000/docs

## Endpoints
- `POST /query` → RAG answer with citations, OOS handling, <5s target
- `POST /recommend` → 2–3 diverse items with "why"
- `GET /metrics` → basic metrics for dashboard

## Project structure
See `app/` modules and `scripts/index_kb.py`.

## Notes
- LLM calls are stubbed; plug in Groq/Gemini/OpenAI in `services/rag.py`.
- Replace retrieval placeholders with FAISS/Chroma in `utils/retrieval.py`.
- Add tests in `tests/` and expand metrics for the Streamlit dashboard.
