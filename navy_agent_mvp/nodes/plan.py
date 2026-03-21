from typing import List

_TABLE_HINTS = {"table", "compare", "comparison", "vs", "versus", "difference", "differences", "matrix"}
_STEP_HINTS = {"steps", "step", "procedure", "process", "checklist", "how to", "how do", "what do"}
_CONCISE_HINTS = {"summary", "summarize", "brief", "short", "key", "most important", "top", "quick"}
_DETAILED_HINTS = {"explain", "detailed", "detail", "why", "rationale", "background"}


def _detect_style_hints(question: str) -> dict:
    q = (question or "").lower()
    wants_table = any(h in q for h in _TABLE_HINTS)
    wants_steps = any(h in q for h in _STEP_HINTS)
    wants_concise = any(h in q for h in _CONCISE_HINTS)
    wants_detail = any(h in q for h in _DETAILED_HINTS)
    return {
        "table": wants_table,
        "steps": wants_steps,
        "concise": wants_concise and not wants_detail,
        "detail": wants_detail,
    }

from google import genai
from google.genai import types

from navy_agent_mvp.config import get_gemini_api_key, get_models
from navy_agent_mvp.state import AgentState, AnswerPlan
from navy_agent_mvp.utils import parse_json_loose, truncate


def _default_plan(user_query: str, book_hint: str = "") -> AnswerPlan:
    hints = _detect_style_hints(user_query)
    title = (user_query or "").strip().rstrip("?") or "Response"
    heading = title[:90]
    sections = [
        {
            "title": "Key Points",
            "instruction": "Summarize the most relevant facts you can support with evidence.",
        }
    ]

    if hints["steps"]:
        sections.append(
            {
                "title": "Procedure",
                "instruction": "Provide a short numbered checklist or step-by-step guidance.",
            }
        )
    elif hints["table"]:
        sections.append(
            {
                "title": "Comparison",
                "instruction": "Provide a compact markdown table contrasting key items.",
            }
        )
    else:
        sections.append(
            {
                "title": "Practical Guidance",
                "instruction": "Explain what the watchstander should do next or remember.",
            }
        )

    style_tips = [
        "Keep sentences tight and declarative.",
        "Use short bullets for multi-step procedures.",
    ]
    if hints["concise"]:
        style_tips.append("Be concise: aim for 4-8 bullets max.")
    if hints["detail"]:
        style_tips.append("Allow 2-4 short paragraphs for context and rationale.")
    if hints["table"]:
        style_tips.append("Use a markdown table where it helps comparison.")
    if hints["steps"]:
        style_tips.append("Use numbered steps for procedures.")

    return {
        "heading": heading,
        "sections": sections,
        "style_tips": style_tips,
    }


def plan_answer_node(state: AgentState) -> AgentState:
    user_query = state["user_query"]
    refined_query = state["route"].get("refined_query") or user_query
    hits = state.get("hits", [])
    book_hint = state.get("book_context_hint") or ""

    if not hits:
        state["answer_plan"] = _default_plan(user_query, book_hint)
        return state

    snippet_lines: List[str] = []
    for idx, hit in enumerate(hits[:5], start=1):
        snippet = truncate(hit.get("chunk_text") or "", 320)
        snippet_lines.append(
            f"[{idx}] source={hit.get('source_file')} page={hit.get('page_start')}\n{snippet}"
        )

    prompt = (
        "You are a planning assistant for a naval question-answering agent.\n"
        "Given the user question, refined query, and supporting snippets, create a compact plan.\n"
        "Return STRICT JSON with keys: heading (string), sections (array of 1-4 objects), style_tips (array of 1-3 strings).\n"
        "Each section object must have title and instruction.\n"
        "No prose. JSON only.\n\n"
        f"QUESTION:\n{user_query}\n\n"
        f"REFINED_QUERY:\n{refined_query}\n\n"
        f"BOOK_CONTEXT:\n{book_hint or 'General naval seamanship reference.'}\n\n"
        f"SNIPPETS:\n" + "\n\n".join(snippet_lines)
    )

    api_key = get_gemini_api_key()
    text_model, _ = get_models()
    client = genai.Client(api_key=api_key)

    plan = _default_plan(user_query, book_hint)
    try:
        resp = client.models.generate_content(
            model=text_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        data = parse_json_loose(resp.text or "")
        if isinstance(data, dict):
            heading = data.get("heading")
            if isinstance(heading, str) and heading.strip():
                plan["heading"] = heading.strip()[:90]

            sections = data.get("sections")
            parsed_sections: List[dict] = []
            if isinstance(sections, list):
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    title = section.get("title")
                    instruction = section.get("instruction")
                    if isinstance(title, str) and isinstance(instruction, str):
                        parsed_sections.append(
                            {
                                "title": title.strip()[:60] or "Section",
                                "instruction": instruction.strip()[:200] or "Explain the point.",
                            }
                        )
            if parsed_sections:
                plan["sections"] = parsed_sections[:4]

            style_tips = data.get("style_tips")
            parsed_tips: List[str] = []
            if isinstance(style_tips, list):
                for tip in style_tips:
                    if isinstance(tip, str) and tip.strip():
                        parsed_tips.append(tip.strip()[:120])
            if parsed_tips:
                plan["style_tips"] = parsed_tips[:3]
    except Exception:
        pass

    state["answer_plan"] = plan
    return state
