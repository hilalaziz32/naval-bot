"""Streaming version of answer synthesis for real-time token generation."""
from typing import List, Iterator, Tuple, Dict, Any
from google import genai
from google.genai import types

from navy_agent_mvp.config import get_gemini_api_key, get_models
from navy_agent_mvp.state import AgentState
from navy_agent_mvp.utils import parse_json_loose

_TABLE_HINTS = {"table", "compare", "comparison", "vs", "versus", "difference", "differences", "matrix"}
_STEP_HINTS = {"steps", "step", "procedure", "process", "checklist", "how to", "how do", "what do"}
_CONCISE_HINTS = {"summary", "summarize", "brief", "short", "key", "most important", "top", "quick"}
_DETAILED_HINTS = {"explain", "detailed", "detail", "why", "rationale", "background"}


def _response_mode(question: str) -> dict:
    q = (question or "").lower()
    return {
        "table": any(h in q for h in _TABLE_HINTS),
        "steps": any(h in q for h in _STEP_HINTS),
        "concise": any(h in q for h in _CONCISE_HINTS) and not any(h in q for h in _DETAILED_HINTS),
        "detail": any(h in q for h in _DETAILED_HINTS),
    }


def _ensure_heading(text: str, heading_hint: str) -> str:
    """Ensure the text starts with an H3 heading."""
    stripped = text.lstrip()
    if stripped.startswith("### "):
        return text
    title = (heading_hint or "").strip().rstrip("?") or "Response"
    heading = f"### {title[:90]}"
    return f"{heading}\n\n{text}" if text.strip() else heading


def synthesize_answer_streaming(state: AgentState) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """
    Stream answer tokens in real-time from Gemini.
    
    Yields:
        Tuple[str, Dict]: (token_text, metadata_dict)
        - During streaming: ("token", {})
        - At end: ("", {"citations": [...], "done": True})
    """
    hits = state.get("hits", [])
    user_query = state["user_query"]
    refined_query = state["route"]["refined_query"]
    plan = state.get("answer_plan") or {}
    book_hint = state.get("book_context_hint") or ""
    conversation_context = state.get("conversation_context") or ""
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

    mode = _response_mode(user_query)

    if not hits:
        if conversation_context:
            prompt = (
                "You are a naval training assistant. Answer using ONLY the provided conversation context.\n"
                "If the context is insufficient, say so and suggest running a KB search.\n"
                "Return markdown text only (no JSON).\n\n"
                f"RESPONSE_MODE:\n- concise={mode['concise']}\n- detail={mode['detail']}\n- table={mode['table']}\n- steps={mode['steps']}\n\n"
                f"CONTEXT:\n{conversation_context}\n\n"
                f"QUESTION:\n{user_query}"
            )
            api_key = get_gemini_api_key()
            text_model, _ = get_models()
            client = genai.Client(api_key=api_key)
            try:
                response = client.models.generate_content_stream(
                    model=text_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                for chunk in response:
                    if chunk.text:
                        yield (chunk.text, {})
                yield ("", {"citations": [], "done": True})
                return
            except Exception:
                pass

        fallback = _ensure_heading(
            "I could not find relevant evidence in the indexed books.",
            plan_heading,
        )
        # Stream the fallback word by word
        words = fallback.split()
        for word in words:
            yield (word + " ", {})
        yield ("", {"citations": [], "done": True})
        return

    min_chunk_usage = min(len(hits), 3)

    evidence_lines: List[str] = []
    for idx, h in enumerate(hits, start=1):
        evidence_lines.append(
            f"[{idx}] source_file={h['source_file']} page={h.get('page_start')} line={h.get('line_start')} similarity={h.get('similarity', 0.0):.4f}\n"
            f"chunk_text: {h.get('chunk_text', '')}\n"
        )

    prompt = (
        "You are a naval expert assistant. Write a comprehensive answer following the plan.\n\n"
        "BOOK_CONTEXT:\n"
        f"{book_hint or 'General Royal Navy seamanship reference.'}\n\n"
        "PLAN_HEADING:\n"
        f"{plan_heading}\n\n"
        "PLAN_SECTIONS (execute in order):\n"
        + "\n".join(section_lines)
        + "\n\nSTYLE_TIPS:\n"
        f"{style_line}\n\n"
        "RESPONSE_MODE:\n"
        f"- concise={mode['concise']}\n"
        f"- detail={mode['detail']}\n"
        f"- table={mode['table']}\n"
        f"- steps={mode['steps']}\n\n"
        "INSTRUCTIONS:\n"
        "1) Start with the plan heading as an H3 markdown line (### Heading).\n"
        "2) Address each section in order using short paragraphs or bullet lists.\n"
        "3) End with a practical takeaway if appropriate.\n"
        "4) Do NOT mention book names, page numbers, or citation markers in the text.\n"
        "5) Integrate at least "
        f"{min_chunk_usage} distinct evidence chunk{'s' if min_chunk_usage != 1 else ''} unless fewer chunks were retrieved.\n"
        "6) If evidence is insufficient, say so plainly.\n"
        "7) Use blank lines between heading, paragraphs, lists, and tables.\n"
        "8) If you include a table, use GFM syntax with a header row and separator row.\n"
        "9) Be direct, authoritative, and practical.\n\n"
        f"USER_QUESTION:\n{user_query}\n\n"
        f"REFINED_QUERY:\n{refined_query}\n\n"
        f"CONVERSATION_CONTEXT:\n{conversation_context or 'none'}\n\n"
        "EVIDENCE CHUNKS:\n"
        + "\n".join(evidence_lines)
    )

    api_key = get_gemini_api_key()
    text_model, _ = get_models()
    client = genai.Client(api_key=api_key)

    accumulated_text = ""
    heading_added = False
    
    try:
        # Use streaming API
        response = client.models.generate_content_stream(
            model=text_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1),
        )
        
        for chunk in response:
            if chunk.text:
                text = chunk.text
                
                # Ensure heading is present at the start
                if not heading_added and accumulated_text == "":
                    if not text.lstrip().startswith("### "):
                        heading = f"### {plan_heading[:90]}\n\n"
                        yield (heading, {})
                        accumulated_text += heading
                    heading_added = True
                
                accumulated_text += text
                yield (text, {})
        
        # After streaming completes, extract citations
        # For now, we'll use a simple heuristic: assume first 3 chunks were used
        used_citations = list(range(1, min(4, len(hits) + 1)))
        
        citations = []
        for idx in used_citations:
            if idx <= len(hits):
                h = hits[idx - 1]
                citations.append({
                    "idx": idx,
                    "source_file": h["source_file"],
                    "page_start": h.get("page_start"),
                    "line_start": h.get("line_start"),
                })
        
        # Send final metadata
        yield ("", {"citations": citations, "done": True})
        
    except Exception as e:
        # Fallback on error
        if not accumulated_text:
            top = hits[0]
            fallback_body = (top.get("answer") or top.get("chunk_text") or "")[:500].strip()
            fallback = _ensure_heading(
                fallback_body or "Insufficient information found in the indexed documents.",
                plan_heading,
            )
            words = fallback.split()
            for word in words:
                yield (word + " ", {})
            
            citations = [{
                "idx": 1,
                "source_file": hits[0]["source_file"],
                "page_start": hits[0].get("page_start"),
                "line_start": hits[0].get("line_start"),
            }]
            yield ("", {"citations": citations, "done": True})
        else:
            # Already streamed some content, just send done signal
            yield ("", {"citations": [], "done": True, "error": str(e)})
