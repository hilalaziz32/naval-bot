from typing import Any, Dict, List, Literal, Optional, TypedDict


class RoutingResult(TypedDict):
    refined_query: str
    target_source_file: Optional[str]
    routing_confidence: float
    route_reason_short: str


class RetrievalHit(TypedDict):
    id: str
    source_file: str
    page_start: Optional[int]
    line_start: Optional[int]
    chunk_text: str
    question: Optional[str]
    answer: Optional[str]
    similarity: float
    rerank_score: float


class Citation(TypedDict):
    idx: int
    source_file: str
    page_start: Optional[int]
    line_start: Optional[int]


class EvidenceCard(TypedDict):
    citation_idx: int
    source_file: str
    page_start: Optional[int]
    line_start: Optional[int]
    similarity: float
    excerpt: str
    why_selected: List[str]


class PlanSection(TypedDict, total=False):
    title: str
    instruction: str


class AnswerPlan(TypedDict, total=False):
    heading: str
    sections: List[PlanSection]
    style_tips: List[str]


class AgentState(TypedDict):
    user_query: str
    top_k: int
    conversation_context: str
    source_file_lock: Optional[str]
    route: RoutingResult
    retrieval_mode: Literal[
        "filtered",
        "global",
        "filtered_then_global",
        "hybrid_filtered",
        "hybrid_global",
        "hybrid_filtered_then_global",
        "none",
    ]
    hits: List[RetrievalHit]
    answer_markdown: str
    citations: List[Citation]
    evidence_cards: List[EvidenceCard]
    answer_plan: AnswerPlan
    route_debug: Dict[str, Any]
