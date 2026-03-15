from typing import List

from google import genai
from google.genai import types

from navy_agent_mvp.config import get_gemini_api_key, get_models
from navy_agent_mvp.state import AgentState
from navy_agent_mvp.utils import parse_json_loose


def _ensure_heading(text: str, heading_hint: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith("### "):
        return text
    title = (heading_hint or "").strip().rstrip("?") or "Response"
    heading = f"### {title[:90]}"
    return f"{heading}\n\n{text}" if text.strip() else heading


def generate_topic_chat_response(user_query: str, short_memory: str, topic_context: str) -> str:
    api_key = get_gemini_api_key()
    text_model, _ = get_models()
    client = genai.Client(api_key=api_key)

    prompt = (
        "You are a helpful naval training assistant in free-chat mode.\n"
        "The user already searched the knowledge base. Use the provided topic context as anchor, "
        "but you may answer naturally like a normal AI assistant.\n\n"
        "RULES:\n"
        "- Begin every answer with a level-3 markdown heading that summarizes the takeaway.\n"
        "- Use short subheadings or bold labels for multi-part guidance.\n"
        "- Be direct, practical, and concise.\n"
        "- Prefer answers aligned with the provided topic context.\n"
        "- If the user asks outside the topic, still help and clearly say when uncertain.\n"
        "- Do not invent exact rule numbers or quoted passages unless present in context.\n"
        "- No JSON. Return plain markdown text only.\n\n"
        f"RECENT_MEMORY:\n{short_memory or 'none'}\n\n"
        f"TOPIC_CONTEXT:\n{topic_context or 'none'}\n\n"
        f"USER_QUESTION:\n{user_query}"
    )

    try:
        resp = client.models.generate_content(
            model=text_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.35),
        )
        text = (resp.text or "").strip()
        if text:
            return _ensure_heading(text, user_query)
    except Exception:
        pass

    return _ensure_heading(
        "I can help with this topic, but I could not generate a response right now. Please try again.",
        user_query,
    )


def synthesize_answer_node(state: AgentState) -> AgentState:
    hits = state.get("hits", [])
    user_query = state["user_query"]
    refined_query = state["route"]["refined_query"]
    plan = state.get("answer_plan") or {}
    plan_heading = plan.get("heading") or user_query
    plan_sections = plan.get("sections") or []
    plan_style = plan.get("style_tips") or [
        "Be direct and confident.",
        "Use compact bullets for multiple steps.",
    ]

    section_lines: List[str] = []
    for idx, section in enumerate(plan_sections, start=1):
        title = (section.get("title") if isinstance(section, dict) else None) or f"Section {idx}"
        instruction = (section.get("instruction") if isinstance(section, dict) else None) or "Explain this part."
        section_lines.append(f"{idx}. {title}: {instruction}")
    if not section_lines:
        section_lines = ["1. Key Points: Summarize the most relevant facts."]

    style_line = "; ".join(plan_style)

    if not hits:
        state["answer_markdown"] = _ensure_heading(
            "I could not find relevant evidence in the indexed books.",
            plan_heading,
        )
        state["citations"] = []
        return state

    min_chunk_usage = min(len(hits), 3)

    evidence_lines: List[str] = []
    for idx, h in enumerate(hits, start=1):
        evidence_lines.append(
            f"[{idx}] source_file={h['source_file']} page={h.get('page_start')} line={h.get('line_start')} similarity={h.get('similarity', 0.0):.4f}\n"
            f"chunk_text: {h.get('chunk_text', '')}\n"
        )

    prompt = (
        "You are a naval expert assistant. Follow the provided plan exactly when writing the answer.\n\n"
        "PLAN_HEADING:\n"
        f"{plan_heading}\n\n"
        "PLAN_SECTIONS (execute in order):\n"
        + "\n".join(section_lines)
        + "\n\nSTYLE_TIPS:\n"
        f"{style_line}\n\n"
        "STEP-BY-STEP:\n"
        "1) Start with the plan heading as an H3 markdown line.\n"
        "2) Address each section in order using short paragraphs or bullet lists.\n"
        "3) End with a practical takeaway if appropriate.\n"
        "4) Do NOT mention book names, page numbers, or citation markers.\n"
        "5) Integrate at least "
        f"{min_chunk_usage} distinct evidence chunk{'s' if min_chunk_usage != 1 else ''} unless fewer chunks were retrieved.\n"
        "6) If evidence is insufficient, say so plainly.\n\n"
        "OUTPUT FORMAT:\n"
        "Return STRICT JSON with keys answer_markdown (string) and used_citations (array of integers).\n"
        "No markdown fences. No extra keys.\n\n"
        f"USER_QUESTION:\n{user_query}\n\n"
        f"REFINED_QUERY:\n{refined_query}\n\n"
        "EVIDENCE CHUNKS:\n"
        + "\n".join(evidence_lines)
    )

    api_key = get_gemini_api_key()
    text_model, _ = get_models()
    client = genai.Client(api_key=api_key)

    answer_markdown = ""
    used = []
    try:
        resp = client.models.generate_content(
            model=text_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        data = parse_json_loose(resp.text or "")
        if isinstance(data, dict):
            ans = data.get("answer_markdown")
            if isinstance(ans, str) and ans.strip():
                answer_markdown = ans.strip()
            citations_raw = data.get("used_citations", [])
            if isinstance(citations_raw, list):
                used = [int(x) for x in citations_raw if isinstance(x, int) and 1 <= x <= len(hits)]
    except Exception:
        pass

    if not answer_markdown:
        top = hits[0]
        fallback_body = (top.get("answer") or top.get("chunk_text") or "")[:500].strip()
        answer_markdown = _ensure_heading(
            fallback_body or "Insufficient information found in the indexed documents.",
            plan_heading,
        )
        used = [1]

    if not used:
        used = [1]

    citations = []
    for idx in used:
        h = hits[idx - 1]
        citations.append(
            {
                "idx": idx,
                "source_file": h["source_file"],
                "page_start": h.get("page_start"),
                "line_start": h.get("line_start"),
            }
        )

    state["answer_markdown"] = _ensure_heading(answer_markdown, plan_heading)
    state["citations"] = citations
    return state
