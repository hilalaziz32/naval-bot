from navy_agent_mvp.state import AgentState
from navy_agent_mvp.utils import truncate


def explain_node(state: AgentState) -> AgentState:
    hits = state.get("hits", [])
    route = state.get("route", {})

    cards = []
    for idx, h in enumerate(hits, start=1):
        cards.append(
            {
                "citation_idx": idx,
                "source_file": h["source_file"],
                "page_start": h.get("page_start"),
                "line_start": h.get("line_start"),
                "similarity": float(h.get("similarity") or 0.0),
                "excerpt": truncate(h.get("chunk_text") or "", 380),
                "why_selected": [
                    f"semantic similarity={float(h.get('similarity') or 0.0):.4f}",
                    f"rerank score={float(h.get('rerank_score') or 0.0):.4f}",
                    f"router target={route.get('target_source_file') or 'none'}",
                    f"retrieval mode={state.get('retrieval_mode')}",
                ],
            }
        )

    state["evidence_cards"] = cards
    return state
