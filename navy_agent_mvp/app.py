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

CHAT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap');
:root {
    --ink: #050b16;
    --deep-navy: #08142e;
    --aqua: #4bd6ff;
    --sand: #ffe4c7;
    --cloud: #f4f7fb;
    --card-border: rgba(13, 37, 78, 0.15);
}
.stApp {
    font-family: 'Space Grotesk', sans-serif;
    color: var(--ink);
    background: radial-gradient(circle at 10% 20%, rgba(31,64,139,0.15), transparent 45%),
                radial-gradient(circle at 80% 0%, rgba(20,174,221,0.18), transparent 40%),
                linear-gradient(180deg, #f4f7fc 0%, #eef2fb 40%, #e6ebf7 100%);
}
[data-testid="stSidebar"] .block-container {
    font-family: 'Space Grotesk', sans-serif;
}
.chat-feed-shell {
    background: rgba(255, 255, 255, 0.82);
    border: 1px solid rgba(9, 21, 53, 0.07);
    border-radius: 24px;
    padding: 20px 28px;
    backdrop-filter: blur(14px);
    box-shadow: 0 25px 60px rgba(9, 16, 40, 0.08);
}
.chat-row {
    display: flex;
    gap: 16px;
    margin-bottom: 28px;
}
.chat-row:last-of-type {
    margin-bottom: 0;
}
.chat-row.user {
    justify-content: flex-end;
}
.chat-avatar {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    background: var(--deep-navy);
    color: #f4fbff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);
}
.chat-row.user .chat-avatar {
    background: #e8f1ff;
    color: #0b285d;
}
.chat-bubble {
    max-width: min(780px, 90%);
    border-radius: 22px;
    padding: 18px 22px 20px;
    background: #ffffff;
    box-shadow: 0 20px 60px rgba(8, 17, 46, 0.08);
    border: 1px solid rgba(9, 23, 64, 0.1);
}
.chat-row.user .chat-bubble {
    background: #041c3f;
    border-color: rgba(75, 214, 255, 0.2);
    color: #e9f4ff;
}
.chat-badge {
    font-size: 0.73rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
}
.chat-badge.kb {
    background: rgba(75, 214, 255, 0.18);
    color: #083c5a;
}
.chat-badge.topic {
    background: rgba(255, 189, 111, 0.32);
    color: #864400;
}
.chat-badge.user {
    background: rgba(255, 255, 255, 0.18);
    color: #f1f5ff;
}
.chat-body {
    margin-top: 10px;
    line-height: 1.55;
    font-size: 1rem;
}
.chat-row.user .chat-body p, .chat-row.user .chat-body li {
    color: #f1f5ff;
}
.chat-meta {
    margin-top: 14px;
    font-size: 0.83rem;
    color: #4c5b7a;
}
.chat-row.user .chat-meta {
    color: #c7dbff;
}
.chat-empty {
    background: #ebf2ff;
    border-radius: 18px;
    padding: 18px;
    text-align: center;
    color: #15315c;
}
.plan-card {
    margin-top: 14px;
    border: 1px solid rgba(13, 37, 78, 0.12);
    border-radius: 14px;
    padding: 14px 16px;
    background: #f9fbff;
    font-size: 0.93rem;
}
.plan-card h5 {
    margin: 0 0 6px;
    font-size: 0.9rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #0d2c5c;
}
.plan-card ul {
    padding-left: 1.1rem;
    margin: 4px 0;
}
.plan-card .plan-tips {
    margin-top: 6px;
    font-size: 0.82rem;
    color: #334466;
}
.chunk-stack {
    margin-top: 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.chunk-meta {
    font-size: 0.82rem;
    color: #4b5c7e;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.chunk-card {
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 12px 14px;
    background: #ffffff;
}
.chunk-card.used {
    border-color: rgba(65, 163, 255, 0.5);
    box-shadow: 0 8px 24px rgba(8, 37, 84, 0.08);
}
.chunk-card__header {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: space-between;
    font-size: 0.84rem;
    font-weight: 600;
    color: #0f2857;
}
.chunk-card__body {
    margin-top: 6px;
    font-size: 0.92rem;
    color: #101b33;
    white-space: pre-wrap;
}
.chunk-card__reason {
    margin-top: 8px;
    font-size: 0.8rem;
    color: #5c6a85;
}
.chunk-card__reason strong {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
    color: #2a4472;
}
.stTextInput > div > input {
    border-radius: 18px !important;
    border: 1px solid rgba(5, 15, 40, 0.2) !important;
    padding: 0.9rem 1.2rem !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 1rem !important;
}
.stButton button {
    border-radius: 16px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 0.9rem 1rem !important;
}
.stButton button:first-child {
    background: #0b2f63 !important;
    color: #f5fbff !important;
}
.stButton button:hover {
    box-shadow: 0 12px 30px rgba(7, 14, 40, 0.18);
}
</style>
"""

st.markdown(CHAT_CSS, unsafe_allow_html=True)

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
    cards_html = [
        f"<div class='chunk-stack'><div class='chunk-meta'>Retrieved {len(hits)} chunks · mode: {mode_label}</div>"
    ]
    for idx, chunk in enumerate(hits, start=1):
        similarity = float(chunk.get("similarity") or 0.0)
        rerank = float(chunk.get("rerank_score") or 0.0)
        used_label = "Used" if idx in used else "Not used"
        chunk_text = chunk.get("chunk_text") or ""
        max_len = 520
        preview = chunk_text if len(chunk_text) <= max_len else chunk_text[:max_len].rstrip() + "..."
        source = escape(chunk.get("source_file") or "unknown.pdf")
        page = chunk.get("page_start")
        line = chunk.get("line_start")
        card = card_map.get(idx)
        reason_lines = card.get("why_selected") if card and card.get("why_selected") else []

        reason_text = "<br/>".join(escape(line) for line in reason_lines)
        preview_html = escape(preview)
        used_class = "used" if idx in used else ""
        default_reason = escape("Semantic match + route decision")
        cards_html.append(
            f"""
            <div class='chunk-card {used_class}'>
                <div class='chunk-card__header'>
                    <span>Chunk {idx} · {used_label}</span>
                    <span>sim {similarity:.4f} · rerank {rerank:.4f}</span>
                </div>
                <div class='chunk-card__body'>{preview_html}</div>
                <div class='chunk-card__reason'>
                    <strong>Source</strong> {source} · p.{page} · line {line}<br/>
                    <strong>Why</strong> {reason_text or default_reason}
                </div>
            </div>
            """
        )
    cards_html.append("</div>")
    st.markdown("\n".join(cards_html), unsafe_allow_html=True)


def _render_plan_card(plan) -> None:
    if not plan:
        return
    heading = escape(plan.get("heading") or "Plan")
    sections = plan.get("sections") or []
    style_tips = plan.get("style_tips") or []

    section_items = []
    for section in sections:
        title = escape(section.get("title") or "Section")
        instruction = escape(section.get("instruction") or "Explain this part.")
        section_items.append(f"<li><strong>{title}:</strong> {instruction}</li>")
    section_html = "".join(section_items) or "<li>Summarize the critical points.</li>"

    tips_html = " · ".join(escape(tip) for tip in style_tips) if style_tips else "Use confident, concise phrasing."

    st.markdown(
        f"""
        <div class='plan-card'>
            <h5>Answer plan · {heading}</h5>
            <ul>{section_html}</ul>
            <div class='plan-tips'><strong>Style:</strong> {tips_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_chat_feed():
    st.subheader("📟 Conversation Feed")
    with st.container():
        messages = st.session_state.chat_messages
        if not messages:
            st.markdown(
                """
                <div class='chat-feed-shell'>
                    <div class='chat-empty'>Ask a question to start the chat.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        st.markdown("<div class='chat-feed-shell'>", unsafe_allow_html=True)
        for msg in messages:
            role = msg.get("role", "assistant")
            mode = msg.get("mode", "kb")
            row_class = "user" if role == "user" else "assistant"
            avatar = "🧭" if role == "assistant" else "🗨️"
            badge_class = "user"
            badge = "Question"
            if role == "assistant" and mode == "kb":
                badge_class = "kb"
                badge = "KB Answer"
            elif role == "assistant" and mode == "topic":
                badge_class = "topic"
                badge = "Topic Chat"
            elif role == "user" and mode == "topic":
                badge = "Topic Follow-up"
            content = msg.get("content", "")

            meta_html = ""
            if role == "assistant" and mode == "kb":
                chunks = msg.get("chunks") or []
                citations = msg.get("citations") or []
                used = {c.get("idx") for c in citations}
                retrieval_mode = msg.get("retrieval_mode") or "unknown"
                meta_html = (
                    f"<div class='chat-meta'>Grounded on {len(used)} of {len(chunks)} retrieved chunks · mode: {retrieval_mode}</div>"
                )
            elif role == "assistant" and mode == "topic":
                ctx_preview = (msg.get("topic_context") or "").strip()
                if ctx_preview:
                    snippet = escape(ctx_preview[:400])
                    meta_html = f"<div class='chat-meta'>Anchored to: {snippet}</div>"

            st.markdown(
                f"""
                <div class='chat-row {row_class}'>
                    <div class='chat-avatar'>{avatar}</div>
                    <div class='chat-bubble'>
                        <div class='chat-badge {badge_class}'>{badge}</div>
                        <div class='chat-body'>
{content}
                        </div>
                        {meta_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if role == "assistant" and mode == "kb":
                _render_plan_card(msg.get("plan"))
                _render_chunk_cards(
                    msg.get("chunks") or [],
                    msg.get("citations") or [],
                    msg.get("retrieval_mode"),
                    msg.get("evidence_cards") or [],
                )
            elif role == "assistant" and mode == "topic":
                ctx_preview = (msg.get("topic_context") or "").strip()
                if ctx_preview:
                    st.markdown(
                        f"""
                        <div class='plan-card'>
                            <h5>Context anchor</h5>
                            <p style='white-space:pre-wrap;'>{escape(ctx_preview[:400])}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        st.markdown("</div>", unsafe_allow_html=True)


_render_chat_feed()

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
