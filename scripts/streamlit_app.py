import os
import time
import uuid
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
QUERY_ENDPOINT = f"{API_BASE}/query"

st.set_page_config(page_title="Shakers QA", page_icon="💬", layout="centered")

st.title("Shakers QA Demo")
st.caption("Ask questions about the Shakers knowledge base. (English only)")

# Per-session user_id (stable while the Streamlit app runs)
if "user_id" not in st.session_state:
    st.session_state.user_id = f"ui_{uuid.uuid4().hex[:8]}"

with st.sidebar:
    st.subheader("Settings")
    api_url = st.text_input("API base URL", value=API_BASE, help="Backend FastAPI base URL")
    st.caption(f"Session user_id: `{st.session_state.user_id}`")

query = st.text_input("Your question", value="How do payments work on Shakers?")
ask = st.button("Ask", type="primary")

def post_query(api_base: str, user_id: str, q: str) -> dict:
    payload = {
        "user_id": user_id,
        "query": q,
        # keep defaults for audience/source/min_similarity/top_k to match backend
    }
    r = requests.post(f"{api_base.rstrip('/')}/query", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

if ask and query.strip():
    with st.spinner("Thinking..."):
        t0 = time.perf_counter()
        try:
            data = post_query(api_url, st.session_state.user_id, query.strip())
            dt_ms = int((time.perf_counter() - t0) * 1000)

            oos = bool(data.get("oos"))
            answer = data.get("answer", "")
            sources = data.get("sources") or data.get("refs") or []

            st.subheader("Answer")
            if oos:
                st.warning("Out of scope")
            st.markdown(answer or "_No answer returned._")

            if sources:
                st.subheader("Sources")
                for i, s in enumerate(sources, start=1):
                    title = s.get("title") or "Source"
                    url = s.get("url") or ""
                    if url:
                        st.markdown(f"{i}. [{title}]({url})")
                    else:
                        st.markdown(f"{i}. {title}")

            st.caption(f"Latency: {dt_ms} ms")

        except requests.HTTPError as e:
            st.error(f"HTTP error: {e.response.status_code} {e.response.text}")
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
else:
    st.info("Type a question and press **Ask**.")
