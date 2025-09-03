# streamlit_app.py
# -----------------------------------------------------------
# Shakers AI — Support & Recommendations (Streamlit frontend)
#
# Single-file drop-in UI that talks to the FastAPI backend:
#   POST /query  { user_id: str, query: str, audience?: "freelancer"|"company" }
#   POST /recommend  { question: str, ctx: { session_id: str, seen: [str] } }
#
# How to run:
#   streamlit run streamlit_app.py
# -----------------------------------------------------------

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# ---------- Page setup ----------

st.set_page_config(
    page_title="Shakers AI — Support & Recommendations",
    page_icon="⚡",
    layout="wide",
)

# ---------- Small helpers ----------

def _uid() -> str:
    return "ui_" + uuid.uuid4().hex[:8]

def is_greeting(text: str) -> bool:
    t = text.strip().lower()
    return bool(
        re.fullmatch(
            r"(hi|hello|hey|hola|howdy|good\s*(morning|afternoon|evening))!?",
            t,
        )
    )

def tidy_answer(ans: str, user_q: str) -> str:
    """
    Remove duplicated question if the model returns
    a 'Q: <question> A: <answer>' structure.
    """
    if not ans:
        return ans
    # If it starts with Q: ... A: ... keep only the part after A:
    m = re.match(r"^\s*Q:\s*(.*?)\s*A:\s*(.*)$", ans, flags=re.S | re.I)
    if m:
        return m.group(2).strip()
    # If the answer starts by repeating the question, drop the first line.
    first_line = ans.splitlines()[0].strip().rstrip("?:.")
    q_norm = re.sub(r"\s+", " ", user_q.strip().lower())
    fl_norm = re.sub(r"\s+", " ", first_line.lower())
    if q_norm and (q_norm in fl_norm or fl_norm in q_norm):
        return "\n".join(ans.splitlines()[1:]).strip()
    return ans.strip()

def try_fetch_logo(api_base: str) -> Optional[str]:
    """
    Builds the URL for the logo served by the backend static files.
    We don't check reachability; Streamlit will fall back gracefully.
    """
    if not api_base:
        return None
    return f"{api_base.rstrip('/')}/static/branding/logo.png"

# --- Recommendations helpers (ONLY recommendation logic below) ---

def _get_seen_doc_ids() -> List[str]:
    """Stable list for 'seen' tracking, JSON friendly."""
    if "seen_doc_ids" not in st.session_state or not isinstance(st.session_state["seen_doc_ids"], list):
        st.session_state["seen_doc_ids"] = []
    return st.session_state["seen_doc_ids"]

def _add_seen(ids: List[str]):
    """Add new ids to 'seen' (dedup, stable order not required)."""
    seen = set(_get_seen_doc_ids())
    for _id in ids:
        if _id:
            seen.add(str(_id))
    st.session_state["seen_doc_ids"] = list(seen)

def fetch_recommendations(api_base: str, session_user_id: str, question: str) -> List[Dict[str, Any]]:
    """
    Calls the backend recommender. Expects the backend to always normalize:
      - doc_id (string)
      - url (string; fallback 'kb://...' when missing)
      - title (string)
      - why (string)
    Returns a list of recommendations or [].
    """
    try:
        payload = {
            "question": question,
            "ctx": {
                "session_id": session_user_id,
                # Always send a stable list, not a set
                "seen": _get_seen_doc_ids(),
            },
        }
        r = requests.post(f"{api_base}/recommend", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json() or {}

        # Support either a top-level list or { "recommendations": [...] }
        recs = data.get("recommendations", data if isinstance(data, list) else [])
        # Ensure shape is consistent and always has a URL
        normalized: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for it in recs or []:
            doc_id = str(it.get("doc_id") or it.get("id") or it.get("source_id") or "")
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            fallback_url_id = (doc_id or "item").replace(" ", "-").lower()
            normalized.append({
                "doc_id": doc_id,
                "title": it.get("title") or it.get("name") or "Untitled",
                "url": it.get("url") or it.get("link") or f"kb://{fallback_url_id}",
                # Accept 'why' or historical 'reason'
                "why": it.get("why") or it.get("reason") or "",
            })
        return normalized
    except Exception:
        return []

def render_recommendations(recs: List[Dict[str, Any]]) -> None:
    """Small, unobtrusive list under the latest answer."""
    with st.expander("Personalized recommendations", expanded=True if recs else False):
        if not recs:
            st.caption("No recommendations at the moment.")
            return
        st.markdown("<ul class='refs'>", unsafe_allow_html=True)
        for r in recs:
            title = r.get("title", "Untitled")
            why_text = f" — {r.get('why','')}" if r.get("why") else ""
            url = r.get("url", "")
            if url and (url.startswith("http") or url.startswith("kb://")):
                st.markdown(f"- [{title}]({url}){why_text}")
            else:
                st.markdown(f"- **{title}**{why_text}")
        st.markdown("</ul>", unsafe_allow_html=True)
    # Mark these as seen so subsequent requests can dedupe
    _add_seen([r.get("doc_id", "") for r in recs if r.get("doc_id")])

# ---------- Session state ----------

if "user_id" not in st.session_state:
    st.session_state.user_id = _uid()

if "history" not in st.session_state:
    # [{q, oos, ms}]
    st.session_state.history: List[Dict[str, Any]] = []

if "audience" not in st.session_state:
    st.session_state.audience: Optional[str] = None  # "freelancer" | "company" | None

if "api_base" not in st.session_state:
    st.session_state.api_base = "http://localhost:8000"

# ---------- Styles (approved look & feel) ----------

st.markdown(
    """
    <style>
      /* Headline weight and spacing */
      .shakers-h1 {
        font-size: 36px;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0.25rem 0 1.25rem 0;
      }
      /* Muted help text */
      .muted { color: #6b7280; font-size: 0.95rem; }

      /* Rounded, yellow "Ask" button */
      .stButton>button {
        border-radius: 9999px !important;
        padding: 0.55rem 1.2rem !important;
        background: #fde047 !important; /* yellow-300 */
        color: #111827 !important;       /* gray-900 */
        border: 1px solid #facc15 !important; /* yellow-400 */
        font-weight: 700 !important;
        box-shadow: 0px 1px 2px rgba(0,0,0,0.08);
      }
      .stButton>button:active { transform: translateY(1px); }

      /* Chips for status & timing */
      .chip {
        display: inline-block;
        padding: 0.125rem 0.5rem;
        border-radius: 9999px;
        border: 1px solid #e5e7eb;
        background: #f9fafb;
        font-size: 0.8rem;
        margin-right: 0.4rem;
      }
      .chip.ok { border-color: #10b98133; background: #10b98122; }
      .chip.oos { border-color: #f59e0b33; background: #f59e0b22; }
      .chip.meta { border-color: #e5e7eb; }
      .refs a { text-decoration: none; }
      .refs li { margin: 0.15rem 0; }
      .stTextInput>div>div>input { font-size: 0.98rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar (settings) ----------

st.sidebar.header("Settings")
api_base = st.sidebar.text_input("API base URL", st.session_state.api_base)
st.session_state.api_base = api_base.strip() or st.session_state.api_base
st.sidebar.caption(f"Session user_id: `{st.session_state.user_id}`")

# ---------- Header with Shakers logo ----------

logo_url = try_fetch_logo(st.session_state.api_base)
left, right = st.columns([0.08, 0.92])
with left:
    if logo_url:
        st.image(logo_url, width=60)
    else:
        st.markdown("⚡", unsafe_allow_html=True)
with right:
    st.markdown(
        '<div class="shakers-h1">Shakers AI — Support & Recommendations</div>',
        unsafe_allow_html=True,
    )
st.markdown(
    '<div class="muted">Ask questions about the Shakers knowledge base.</div>',
    unsafe_allow_html=True,
)

st.write("")  # spacer

# ---------- Query input row ----------

q = st.text_input("Your question", key="q_input", placeholder="How can I help?")
c1, c2, c3 = st.columns([0.12, 0.18, 0.70])

ask_clicked = False
with c1:
    ask_clicked = st.button("Ask", type="primary")

with c2:
    # Only option: audience selection
    with st.popover("Options"):
        st.markdown("**Are you a freelancer or a company?**")
        choice = st.radio(
            "Pick one:",
            ["Freelancer", "Company", "Not sure / skip"],
            index=2 if st.session_state.audience is None else (0 if st.session_state.audience == "freelancer" else 1),
            label_visibility="collapsed",
        )
        if choice == "Freelancer":
            st.session_state.audience = "freelancer"
        elif choice == "Company":
            st.session_state.audience = "company"
        else:
            st.session_state.audience = None

with c3:
    if st.session_state.audience:
        st.markdown(
            f'<span class="chip meta">Audience: {st.session_state.audience.title()}</span>',
            unsafe_allow_html=True,
        )

# Submit also on Enter in the input (without double-submit)
if q and st.session_state.get("_last_q") != q and st.session_state.get("_enter_submit_once") is None:
    st.session_state._enter_submit_once = True
elif not q:
    st.session_state._enter_submit_once = None

should_ask = ask_clicked or (st.session_state._enter_submit_once is True and q.strip() != "")

# ---------- Answer area ----------

st.write("")  # spacer
st.subheader("Latest answer")

recs_to_render: List[Dict[str, Any]] = []  # filled after each query

if should_ask:
    st.session_state._last_q = q
    user_q = q.strip()

    # Greeting → friendly message (no backend call)
    if is_greeting(user_q):
        start = time.perf_counter()
        answer_text = (
            "Hi there! I am the **Shakers AI** agent. "
            "I am ready to help with any matter related to the **hiring**, **payments**, "
            "or **projects** processes. Just drop your question — I’ll be glad to assist."
        )
        took_ms = int((time.perf_counter() - start) * 1000)
        st.markdown('<span class="chip meta">👋 Greeting</span>'
                    f'<span class="chip meta">{took_ms} ms</span>', unsafe_allow_html=True)
        st.write("")
        st.markdown(answer_text)
        # History
        st.session_state.history.insert(0, {"q": user_q, "oos": False, "ms": took_ms})
        # Even on greeting, try to show suggestions
        recs_to_render = fetch_recommendations(st.session_state.api_base, st.session_state.user_id, user_q)
    else:
        # Call backend for the main answer
        payload = {
            "user_id": st.session_state.user_id,
            "query": user_q,
            "audience": st.session_state.audience,
        }
        try:
            t0 = time.perf_counter()
            resp = requests.post(
                f"{st.session_state.api_base.rstrip('/')}/query",
                json=payload,
                timeout=60,
            )
            took_ms = int((time.perf_counter() - t0) * 1000)
        except Exception as e:
            st.error(f"Could not reach backend at {st.session_state.api_base} — {e}")
            resp = None

        if resp is not None and resp.ok:
            data: Dict[str, Any] = resp.json()
            answer = tidy_answer(data.get("answer") or "", user_q)
            refs: List[Dict[str, Any]] = data.get("refs") or []
            oos: bool = bool(data.get("oos"))

            # Status chips
            if oos:
                st.markdown('<span class="chip oos">🔎 OOS</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="chip ok">✅ In-scope</span>', unsafe_allow_html=True)
            st.markdown(f'<span class="chip meta">{took_ms} ms</span>', unsafe_allow_html=True)

            st.write("")
            # Show the question once (title-ish), then the cleaned answer
            st.markdown(f"**{user_q}**")
            st.markdown(answer)

            # References
            with st.expander("References"):
                if refs:
                    st.markdown('<ul class="refs">', unsafe_allow_html=True)
                    for r in refs:
                        title = (r.get("title") or r.get("path") or r.get("id") or "KB").strip()
                        url = r.get("url") or ""
                        if url and (url.startswith("http") or url.startswith("kb://")):
                            st.markdown(f"- [{title}]({url})")
                        else:
                            st.markdown(f"- {title}")
                    st.markdown("</ul>", unsafe_allow_html=True)
                else:
                    st.caption("No references returned.")

            # History
            st.session_state.history.insert(0, {"q": user_q, "oos": oos, "ms": took_ms})

            # Fetch personalized recommendations every time
            recs_to_render = fetch_recommendations(st.session_state.api_base, st.session_state.user_id, user_q)

        elif resp is not None:
            st.error(f"Backend returned {resp.status_code}: {resp.text}")

# Render recommendations panel (updates after every query/greeting)
if recs_to_render is not None:
    render_recommendations(recs_to_render)

# ---------- History ----------

with st.expander("History", expanded=False):
    if not st.session_state.history:
        st.caption("No questions yet.")
    else:
        for i, h in enumerate(st.session_state.history, start=1):
            status = "OK" if not h["oos"] else "OOS"
            st.markdown(f"**{i}.** {h['q']} — *{status}* · {h['ms']} ms")

# ---------- Footer ----------

st.markdown(
    f'<div class="muted">Backend running? Visit <a href="{st.session_state.api_base.rstrip("/")}/docs">/docs</a> for API docs.</div>',
    unsafe_allow_html=True,
)
