import os
import sys
from html import escape

# Ensure repo root is on sys.path so `navy_agent_mvp` is importable on Streamlit Cloud
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from navy_agent_mvp.config import load_book_catalog, load_env
from navy_agent_mvp.graph import run_agent
from navy_agent_mvp.nodes.answer import generate_topic_chat_response


st.set_page_config(page_title="Navy Q&A MVP", page_icon="⚓", layout="wide")
load_env()

if "chat_memory" not in st.session_state:
    st.session_state.chat_memory = []
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "topic_context" not in st.session_state:
    st.session_state.topic_context = ""
if "topic_active" not in st.session_state:
    st.session_state.topic_active = False

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
        st.session_state.chat_messages = []
        st.session_state.topic_context = ""
        st.session_state.topic_active = False
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


def _append_chat_message(role: str, content: str, mode: str, **extra) -> None:
    st.session_state.chat_messages.append(
        {
            "role": role,
            "content": content,
            "mode": mode,
            **extra,
        }
    )
    st.session_state.chat_messages = st.session_state.chat_messages[-40:]


def _render_chunk_cards(hits, citations, retrieval_mode, evidence_cards=None) -> None:
    evidence_cards = evidence_cards or []
    card_map = {card.get("citation_idx"): card for card in evidence_cards}
    used = {c.get("idx") for c in (citations or [])}
    if not hits:
        st.info("No chunks retrieved from the knowledge base.")
        return

    mode_label = retrieval_mode or "unknown"
    st.markdown(f"**Retrieved chunks ({len(hits)}) · mode: {mode_label}**")
    for idx, chunk in enumerate(hits, start=1):
        similarity = float(chunk.get("similarity") or 0.0)
        rerank = float(chunk.get("rerank_score") or 0.0)
        used_label = "✅ used in answer" if idx in used else "↗️ extra context"
        chunk_text = chunk.get("chunk_text") or ""
        max_len = 1400
        preview = chunk_text if len(chunk_text) <= max_len else chunk_text[:max_len].rstrip() + "..."
        source = escape(chunk.get("source_file") or "unknown.pdf")
        page = chunk.get("page_start")
        line = chunk.get("line_start")
        card = card_map.get(idx)
        reason_lines = card.get("why_selected") if card and card.get("why_selected") else []

        badge = (
            f"Chunk {idx} · sim {similarity:.4f} · rerank {rerank:.4f} · {used_label}"
        )
        meta = f"📖 {source} | page {page} | line {line}"
        reason_text = "<br/>".join(escape(line) for line in reason_lines)
        preview_html = escape(preview)
        card_html = (
            "<div style='border:1px solid #1e3a5f25;border-radius:10px;padding:12px;margin-bottom:12px;"
            "background-color:#f8fafc;'>"
            f"<div style='font-weight:600;font-size:0.92em;color:#0f172a;'>{badge}</div>"
            f"<div style='font-size:0.82em;color:#475569;margin-bottom:6px;'>{meta}</div>"
            f"<div style='font-size:0.92em;white-space:pre-wrap;color:#0b172a;'>{preview_html}</div>"
        )
        if reason_text:
            card_html += (
                f"<div style='margin-top:6px;font-size:0.8em;color:#0f172a;'><strong>Why selected:</strong> {reason_text}</div>"
            )
        card_html += "</div>"
        st.markdown(card_html, unsafe_allow_html=True)


st.subheader("📟 Conversation Feed")
with st.container():
    if not st.session_state.chat_messages:
        st.info("Ask a question to start the chat.")
    for msg in st.session_state.chat_messages:
        role = msg.get("role", "assistant")
        avatar = "🧭" if role == "assistant" else "🗨️"
        mode = msg.get("mode", "kb")
        with st.chat_message(role, avatar=avatar):
            if role == "assistant":
                badge = "KB Answer" if mode == "kb" else "Topic Chat"
                st.markdown(
                    f"<span style='background:#ecf2ff;color:#1d3b8b;padding:2px 10px;border-radius:8px;font-size:0.85em;'>{badge}</span>",
                    unsafe_allow_html=True,
                )
            else:
                badge = "KB question" if mode == "kb" else "Topic follow-up"
                st.caption(badge)

            st.markdown(msg.get("content", ""))

            if role == "assistant" and mode == "kb":
                chunks = msg.get("chunks") or []
                citations = msg.get("citations") or []
                retrieval_mode = msg.get("retrieval_mode")
                used = {c.get("idx") for c in citations}
                chunk_count = len(chunks)
                st.caption(
                    f"Grounded on {len(used)} of {chunk_count} retrieved chunks · mode: {retrieval_mode or 'unknown'}"
                )
                _render_chunk_cards(chunks, citations, retrieval_mode, msg.get("evidence_cards"))
                if chunk_count > 1 and len(used) <= 1:
                    st.warning(
                        "Only one chunk was cited even though multiple were retrieved. Consider refining the question for broader coverage.",
                        icon="⚠️",
                    )
                plan = msg.get("plan")
                if plan:
                    with st.expander("Answer plan", expanded=False):
                        st.markdown(f"**Heading:** {plan.get('heading', 'n/a')}")
                        sections = plan.get("sections") or []
                        if sections:
                            st.markdown("**Sections:**")
                            for section in sections:
                                title = section.get("title", "Section")
                                instruction = section.get("instruction", "")
                                st.markdown(f"- **{title}:** {instruction}")
                        style_tips = plan.get("style_tips") or []
                        if style_tips:
                            st.caption("Style tips: " + "; ".join(style_tips))
            elif role == "assistant" and mode == "topic":
                context_preview = (msg.get("topic_context") or "").strip()
                if context_preview:
                    st.caption("Context anchor:\n" + context_preview[:400])

st.markdown("---")

query = st.text_input(
    "Ask a naval question",
    placeholder="e.g., What are actions in restricted visibility?",
    key="kb_question_input",
)

query = st.text_input("Ask a naval question", placeholder="e.g., What are actions in restricted visibility?")

col1, col2 = st.columns(2)
kb_clicked = col1.button("Search KB + Answer", type="primary", use_container_width=True)
topic_clicked = col2.button("Topic Chat (AI)", use_container_width=True)

question = query.strip()

if kb_clicked:
    if not question:
        st.warning("Please enter a question before running the KB search.")
    else:
        _append_chat_message("user", question, mode="kb")
        with st.spinner("Searching knowledge base and generating answer..."):
            result = run_agent(
                question,
                top_k=top_k,
                conversation_context=_build_short_context(),
                source_file_lock=locked_source,
            )

        route = result["route"]
        answer_text = result.get("answer_markdown") or "No answer generated."
        citations = result.get("citations", [])
        cards = result.get("evidence_cards", [])
        hits = result.get("hits", [])
        retrieval_mode = result.get("retrieval_mode")

        context_lines = []
        for i, h in enumerate(hits[:4], start=1):
            context_lines.append(
                f"[{i}] {h.get('source_file')} p.{h.get('page_start')} sim={float(h.get('similarity') or 0.0):.4f} "
                f"rerank={float(h.get('rerank_score') or 0.0):.4f}\n{(h.get('chunk_text') or '')[:420]}"
            )
        st.session_state.topic_context = "\n\n".join(context_lines)
        st.session_state.topic_active = bool(hits)

        _append_chat_message(
            "assistant",
            answer_text,
            mode="kb",
            citations=citations,
            chunks=hits,
            retrieval_mode=retrieval_mode,
            evidence_cards=cards,
            plan=result.get("answer_plan"),
        )

        st.session_state.chat_memory.append(
            {
                "q": question,
                "a": answer_text,
                "source_file": route.get("target_source_file"),
            }
        )
        st.session_state.chat_memory = st.session_state.chat_memory[-5:]
        st.toast("KB search complete.")

if topic_clicked:
    if not question:
        st.warning("Please enter a question before using topic chat.")
    else:
        _append_chat_message("user", question, mode="topic")
        if not st.session_state.topic_active:
            warning_text = "Please run 'Search KB + Answer' first so topic chat has a knowledge anchor."
            _append_chat_message("assistant", warning_text, mode="topic")
            st.warning(warning_text)
        else:
            with st.spinner("Generating topic-based AI response..."):
                topic_answer = generate_topic_chat_response(
                    user_query=question,
                    short_memory=_build_short_context(),
                    topic_context=st.session_state.topic_context,
                )

            _append_chat_message(
                "assistant",
                topic_answer,
                mode="topic",
                topic_context=st.session_state.topic_context,
            )
            st.session_state.chat_memory.append(
                {
                    "q": question,
                    "a": topic_answer,
                    "source_file": locked_source,
                }
            )
            st.session_state.chat_memory = st.session_state.chat_memory[-5:]
