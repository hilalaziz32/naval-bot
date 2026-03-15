from typing import Optional

from langgraph.graph import END, StateGraph

from navy_agent_mvp.nodes.answer import synthesize_answer_node
from navy_agent_mvp.nodes.explain import explain_node
from navy_agent_mvp.nodes.plan import plan_answer_node
from navy_agent_mvp.nodes.retriever import retrieve_node
from navy_agent_mvp.nodes.router import route_query_node
from navy_agent_mvp.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("route_query", route_query_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("plan", plan_answer_node)
    graph.add_node("synthesize", synthesize_answer_node)
    graph.add_node("explain", explain_node)

    graph.set_entry_point("route_query")
    graph.add_edge("route_query", "retrieve")
    graph.add_edge("retrieve", "plan")
    graph.add_edge("plan", "synthesize")
    graph.add_edge("synthesize", "explain")
    graph.add_edge("explain", END)

    return graph.compile()


def run_agent(
    user_query: str,
    top_k: int = 6,
    conversation_context: str = "",
    source_file_lock: Optional[str] = None,
):
    app = build_graph()
    initial_state: AgentState = {
        "user_query": user_query,
        "top_k": top_k,
        "conversation_context": conversation_context,
        "source_file_lock": source_file_lock,
        "route": {
            "refined_query": user_query,
            "target_source_file": None,
            "routing_confidence": 0.0,
            "route_reason_short": "Not routed yet.",
        },
        "retrieval_mode": "none",
        "hits": [],
        "answer_markdown": "",
        "citations": [],
        "evidence_cards": [],
        "answer_plan": {"heading": "", "sections": [], "style_tips": []},
        "route_debug": {},
    }
    return app.invoke(initial_state)
