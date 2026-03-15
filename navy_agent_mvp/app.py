import os
import sys

# Ensure repo root is on sys.path so `navy_agent_mvp` is importable on Streamlit Cloud
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from navy_agent_mvp.config import load_book_catalog, load_env
from navy_agent_mvp.graph import run_agent


st.set_page_config(page_title="Navy Q&A MVP", page_icon="⚓", layout="wide")
load_env()

if "chat_memory" not in st.session_state:
    st.session_state.chat_memory = []

st.title("⚓ Navy Expert Q&A (MVP)")
st.caption("LangGraph router + Supabase retrieval + grounded answer with evidence")

with st.sidebar:
    catalog = load_book_catalog()
    sources = [b["source_file"] for b in catalog]

    st.subheader("🔍 Search in")
    _AUTO = "🌐 All books (auto-route)"
    book_choice = st.selectbox(
        "Select a book or let the AI decide",
        options=[_AUTO] + sources,
        index=0,
        help="Pick a specific PDF to search only that book, or leave on Auto to let the agent choose.",
    )
    locked_source = None if book_choice == _AUTO else book_choice

    if locked_source:
        _title = next((b["title"] for b in catalog if b["source_file"] == locked_source), locked_source)
        st.info(f"📖 Locked to:\n**{_title}**")

    st.markdown("---")
    top_k = st.slider("Top K retrieval", min_value=3, max_value=12, value=6)
    memory_turns = st.slider("Short memory turns", min_value=0, max_value=5, value=2)

    if st.button("Clear chat memory"):
        st.session_state.chat_memory = []
        st.success("Memory cleared")

    if st.session_state.chat_memory:
        st.markdown("---")
        st.caption("Recent memory")
        for i, turn in enumerate(reversed(st.session_state.chat_memory[-memory_turns:]), start=1):
            st.markdown(f"**Q{i}:** {turn['q'][:120]}")
            st.markdown(f"**A{i}:** {turn['a'][:160]}")


def _build_short_context() -> str:
    turns = st.session_state.chat_memory[-memory_turns:] if memory_turns > 0 else []
    if not turns:
        return ""
    lines = []
    for t in turns:
        lines.append(f"User: {t['q']}")
        lines.append(f"Assistant: {t['a'][:260]}")
    return "\n".join(lines)

query = st.text_input("Ask a naval question", placeholder="e.g., What are actions in restricted visibility?")

if st.button("Ask", type="primary") and query.strip():
    with st.spinner("Running agents..."):
        result = run_agent(
            query.strip(),
            top_k=top_k,
            conversation_context=_build_short_context(),
            source_file_lock=locked_source,
        )

    route = result["route"]
    answer_text = result.get("answer_markdown") or "No answer generated."
    citations = result.get("citations", [])
    cards = result.get("evidence_cards", [])

    # ── Answer ────────────────────────────────────────────────────────────────
    st.markdown("### Answer")
    st.write(answer_text)

    # ── Sources expander ──────────────────────────────────────────────────────
    # Collect the hits that were actually cited; fall back to all cards
    cited_indices = {c["idx"] for c in citations} if citations else set(range(1, len(cards) + 1))
    source_cards = [c for c in cards if c["citation_idx"] in cited_indices] or cards

    if source_cards:
        with st.expander(f"📚 View sources ({len(source_cards)} chunk{'s' if len(source_cards) != 1 else ''})", expanded=False):
            for card in source_cards:
                book = card["source_file"]
                page = card.get("page_start")
                line = card.get("line_start")
                sim  = card.get("similarity", 0.0)
                excerpt = card.get("excerpt", "")

                # Highlighted book name
                st.markdown(
                    f"<span style='background:#1e3a5f;color:#e8f4fd;padding:3px 10px;"
                    f"border-radius:4px;font-weight:bold;font-size:0.9em;'>📖 {book}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"Page {page}  |  Line {line}  |  similarity {sim:.4f}")
                st.markdown(
                    f"<div style='border-left:3px solid #1e3a5f;padding:8px 12px;"
                    f"background:#f7f9fc;border-radius:0 4px 4px 0;font-size:0.9em;"
                    f"white-space:pre-wrap;'>{excerpt}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("---")
    else:
        with st.expander("📚 View sources", expanded=False):
            st.info("No source chunks available.")

    # ── Debug expander (hidden by default) ────────────────────────────────────
    with st.expander("🔧 Debug / routing info", expanded=False):
        st.write(
            {
                "source_file_lock": locked_source,
                "target_source_file": route.get("target_source_file"),
                "routing_confidence": route.get("routing_confidence"),
                "refined_query": route.get("refined_query"),
                "retrieval_mode": result.get("retrieval_mode"),
                "route_reason_short": route.get("route_reason_short"),
            }
        )

    st.session_state.chat_memory.append(
        {
            "q": query.strip(),
            "a": answer_text,
            "source_file": route.get("target_source_file"),
        }
    )
    st.session_state.chat_memory = st.session_state.chat_memory[-5:]
