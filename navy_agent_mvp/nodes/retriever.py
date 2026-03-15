import re
from typing import Dict, List, Optional, Sequence

from google import genai
from google.genai import types

from navy_agent_mvp.config import EMBED_DIM, get_gemini_api_key, get_models, get_supabase_client
from navy_agent_mvp.state import AgentState
from navy_agent_mvp.utils import dedupe_hits, normalize_embedding, vector_literal


_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "then",
    "than",
    "to",
    "for",
    "of",
    "in",
    "on",
    "at",
    "by",
    "from",
    "with",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "what",
    "when",
    "where",
    "why",
    "how",
    "who",
    "which",
    "about",
    "into",
    "over",
    "under",
    "through",
    "between",
    "after",
    "before",
    "during",
    "your",
    "our",
    "their",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "we",
    "you",
    "they",
}


def _embed_query(query: str) -> List[float]:
    api_key = get_gemini_api_key()
    _, embed_model = get_models()
    client = genai.Client(api_key=api_key)

    result = client.models.embed_content(
        model=embed_model,
        contents=[query],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBED_DIM,
        ),
    )
    [emb] = result.embeddings
    values = list(emb.values)
    if len(values) != EMBED_DIM:
        raise ValueError(f"Expected embedding dim {EMBED_DIM}, got {len(values)}")
    return normalize_embedding(values)


def _rpc_search(query_embedding: List[float], top_k: int, source_file: Optional[str]):
    supabase = get_supabase_client()
    response = supabase.rpc(
        "match_naval_chunks",
        {
            "query_embedding": vector_literal(query_embedding),
            "match_count": top_k,
            "filter_source": source_file,
        },
    ).execute()
    return response.data or []


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9\-_/]{1,}", (text or "").lower())
    return [t for t in tokens if t not in _STOPWORDS]


def _query_variants(user_query: str, refined_query: str, conversation_context: str) -> List[str]:
    variants = [refined_query.strip(), user_query.strip()]

    history_tail = (conversation_context or "").strip()
    if history_tail:
        tail_lines = [ln.strip() for ln in history_tail.splitlines() if ln.strip()]
        compact_tail = " ".join(tail_lines[-2:])
        if compact_tail:
            variants.append(f"{refined_query.strip()} {compact_tail}"[:500])

    seen = set()
    out: List[str] = []
    for q in variants:
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            out.append(q)
    return out


def _merge_keep_best_similarity(rows: Sequence[dict]) -> List[dict]:
    best: Dict[tuple, dict] = {}
    for row in rows:
        key = (
            row.get("source_file"),
            row.get("page_start"),
            row.get("line_start"),
            (row.get("chunk_text") or "")[:140],
        )
        prev = best.get(key)
        if prev is None or float(row.get("similarity") or 0.0) > float(prev.get("similarity") or 0.0):
            best[key] = row
    return list(best.values())


def _rerank_rows(rows: Sequence[dict], query_text: str, target_source_file: Optional[str]) -> List[dict]:
    query_tokens = set(_tokenize(query_text))
    reranked: List[dict] = []

    for row in rows:
        chunk_text = row.get("chunk_text") or ""
        qa_text = f"{row.get('question') or ''} {row.get('answer') or ''}"
        searchable = f"{chunk_text}\n{qa_text}".lower()

        doc_tokens = set(_tokenize(searchable))
        overlap = len(query_tokens.intersection(doc_tokens))
        overlap_norm = overlap / max(1.0, min(12.0, float(len(query_tokens))))

        sim = float(row.get("similarity") or 0.0)
        sim = max(0.0, min(1.0, sim))

        source_boost = 0.0
        if target_source_file and row.get("source_file") == target_source_file:
            source_boost = 0.06

        score = (0.78 * sim) + (0.22 * overlap_norm) + source_boost
        cloned = dict(row)
        cloned["rerank_score"] = float(score)
        reranked.append(cloned)

    reranked.sort(key=lambda x: (float(x.get("rerank_score") or 0.0), float(x.get("similarity") or 0.0)), reverse=True)
    return reranked


def retrieve_node(state: AgentState) -> AgentState:
    route = state["route"]
    user_query = state["user_query"]
    refined_query = route["refined_query"]
    conversation_context = state.get("conversation_context") or ""
    top_k = int(state.get("top_k", 6))
    confidence = float(route.get("routing_confidence", 0.0))
    target = route.get("target_source_file")
    source_file_lock = state.get("source_file_lock")

    variants = _query_variants(user_query, refined_query, conversation_context)
    query_embeddings = {q: _embed_query(q) for q in variants}
    pool_k = max(top_k * 4, 12)

    candidate_rows: List[dict] = []

    if source_file_lock:
        for q in variants:
            candidate_rows.extend(_rpc_search(query_embeddings[q], pool_k, source_file_lock))
        mode = "hybrid_filtered"
        rerank_target = source_file_lock
    elif target and confidence >= 0.7:
        filtered_rows: List[dict] = []
        for q in variants:
            filtered_rows.extend(_rpc_search(query_embeddings[q], pool_k, target))

        if len(filtered_rows) >= max(4, top_k):
            candidate_rows = filtered_rows
            mode = "hybrid_filtered"
        else:
            global_rows: List[dict] = []
            for q in variants:
                global_rows.extend(_rpc_search(query_embeddings[q], pool_k, None))
            candidate_rows = [*filtered_rows, *global_rows]
            mode = "hybrid_filtered_then_global"
        rerank_target = target
    else:
        for q in variants:
            candidate_rows.extend(_rpc_search(query_embeddings[q], pool_k, None))
        mode = "hybrid_global"
        rerank_target = None

    merged = _merge_keep_best_similarity(dedupe_hits(candidate_rows))
    reranked = _rerank_rows(merged, query_text=f"{user_query}\n{refined_query}", target_source_file=rerank_target)
    rows = reranked[:top_k]

    hits = []
    for row in rows:
        hits.append(
            {
                "id": str(row.get("id")),
                "source_file": row.get("source_file") or "",
                "page_start": row.get("page_start"),
                "line_start": row.get("line_start"),
                "chunk_text": row.get("chunk_text") or "",
                "question": row.get("question"),
                "answer": row.get("answer"),
                "similarity": float(row.get("similarity") or 0.0),
                "rerank_score": float(row.get("rerank_score") or 0.0),
            }
        )

    state["hits"] = hits
    state["retrieval_mode"] = mode if hits else "none"
    return state
