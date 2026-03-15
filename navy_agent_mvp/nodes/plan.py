from typing import List

from google import genai
from google.genai import types

from navy_agent_mvp.config import get_gemini_api_key, get_models
from navy_agent_mvp.state import AgentState, AnswerPlan
from navy_agent_mvp.utils import parse_json_loose, truncate


def _default_plan(user_query: str) -> AnswerPlan:
    title = (user_query or "").strip().rstrip("?") or "Response"
    heading = title[:90]
    return {
        "heading": heading,
        "sections": [
            {
                "title": "Key Points",
                "instruction": "Summarize the most relevant facts you can support with evidence.",
            },
            {
                "title": "Practical Guidance",
                "instruction": "Explain what the watchstander should do next or remember.",
            },
        ],
        "style_tips": [
            "Keep sentences tight and declarative.",
            "Use short bullets for multi-step procedures.",
        ],
    }


def plan_answer_node(state: AgentState) -> AgentState:
    user_query = state["user_query"]
    refined_query = state["route"].get("refined_query") or user_query
    hits = state.get("hits", [])

    if not hits:
        state["answer_plan"] = _default_plan(user_query)
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
        f"SNIPPETS:\n" + "\n\n".join(snippet_lines)
    )

    api_key = get_gemini_api_key()
    text_model, _ = get_models()
    client = genai.Client(api_key=api_key)

    plan = _default_plan(user_query)
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
