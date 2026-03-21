"""FastAPI backend for Navy RAG chat application with streaming support."""
import asyncio
import json
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client, Client

from backend.auth import get_auth_context
from backend.streaming_answer import synthesize_answer_streaming
from navy_agent_mvp.config import get_supabase_client, load_book_catalog
from navy_agent_mvp.graph import build_graph
from navy_agent_mvp.state import AgentState
from navy_agent_mvp.utils import truncate
from navy_agent_mvp.nodes.router import route_query_node
from navy_agent_mvp.nodes.retriever import retrieve_node
from navy_agent_mvp.nodes.plan import plan_answer_node
from navy_agent_mvp.nodes.explain import explain_node

# Initialize FastAPI app
app = FastAPI(title="Navy RAG API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load book catalog at startup
BOOK_CATALOG = []


def _book_short_title(book: Dict[str, Any]) -> str:
    source_file = (book.get("source_file") or "").strip()
    title = (book.get("title") or "").strip()
    if source_file.lower().endswith(".pdf") and source_file:
        source_base = source_file[:-4]
    else:
        source_base = source_file
    return source_base or title or "Unknown source"


def _normalized_books() -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for book in BOOK_CATALOG:
        normalized.append(
            {
                "source_file": book.get("source_file"),
                "title": book.get("title") or book.get("source_file") or "Untitled",
                "short_title": book.get("short_title") or _book_short_title(book),
                "summary": book.get("summary") or "",
                "aliases": book.get("aliases") or [],
            }
        )
    return normalized


def _normalize_book_lock(book_lock: Optional[str]) -> Optional[str]:
    if not book_lock:
        return None

    requested = book_lock.strip().lower()
    if not requested:
        return None

    for book in BOOK_CATALOG:
        source = (book.get("source_file") or "").strip()
        title = (book.get("title") or "").strip()
        aliases = [a.strip() for a in (book.get("aliases") or []) if isinstance(a, str)]

        candidates = [source.lower(), title.lower(), *[a.lower() for a in aliases]]
        if requested in candidates:
            return source

    return None

@app.on_event("startup")
async def startup_event():
    """Load book catalog on startup."""
    global BOOK_CATALOG
    BOOK_CATALOG = load_book_catalog()


# Pydantic models
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    book_lock: Optional[str] = None
    top_k: int = 6


class ConversationResponse(BaseModel):
    id: str
    title: str
    book_lock: Optional[str]
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: List[Dict[str, Any]]
    evidence_cards: List[Dict[str, Any]]
    created_at: str


# Helper functions
def get_supabase(access_token: Optional[str] = None) -> Client:
    """Get Supabase client."""
    client = get_supabase_client()
    if access_token:
        try:
            client.postgrest.auth(access_token)
        except Exception:
            # Fallback to base client behavior if auth binding is unavailable.
            pass
    return client


async def create_conversation(
    user_id: str,
    title: str,
    book_lock: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new conversation in Supabase."""
    supabase = get_supabase(access_token)
    
    data = {
        "user_id": user_id,
        "title": title,
        "book_lock": book_lock,
    }
    
    result = supabase.table("conversations").insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create conversation")
    
    return result.data[0]


async def save_message(
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    citations: List[Dict] = None,
    evidence_cards: List[Dict] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Save a message to Supabase."""
    supabase = get_supabase(access_token)
    
    data = {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "citations": citations or [],
        "evidence_cards": evidence_cards or [],
    }
    
    result = supabase.table("messages").insert(data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save message")
    
    return result.data[0]


def _build_conversation_context(
    conversation_id: str,
    access_token: Optional[str],
    limit: int = 6,
) -> str:
    if not conversation_id:
        return ""

    supabase = get_supabase(access_token)
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = list(reversed(result.data or []))
    if not rows:
        return ""

    lines = []
    for row in rows:
        role = (row.get("role") or "assistant").strip().lower()
        content = (row.get("content") or "").strip()
        if not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {truncate(content, 320)}")

    return "\n".join(lines)


def run_agent_pipeline(state: AgentState) -> AgentState:
    """Run the agent pipeline up to the answer synthesis step."""
    # Run routing
    state = route_query_node(state)
    
    # Run retrieval
    state = retrieve_node(state)
    
    # Run planning
    state = plan_answer_node(state)
    
    # Note: We don't run synthesize_answer_node here because we'll stream it
    # We also skip explain_node for now as it just builds evidence cards
    
    return state


async def stream_chat_response(
    user_message: str,
    conversation_id: str,
    user_id: str,
    book_lock: Optional[str] = None,
    top_k: int = 6,
    access_token: Optional[str] = None,
):
    """
    Stream chat response using SSE format.
    
    Yields JSON events:
    - {"type": "token", "content": "..."}
    - {"type": "metadata", "citations": [...], "evidence_cards": [...]}
    - {"type": "done"}
    """
    try:
        # Save user message
        await save_message(user_id, conversation_id, "user", user_message, access_token=access_token)

        conversation_context = _build_conversation_context(conversation_id, access_token)
        
        # Initialize agent state
        initial_state: AgentState = {
            "user_query": user_message,
            "top_k": top_k,
            "conversation_context": conversation_context,
            "source_file_lock": book_lock,
            "route": {
                "refined_query": "",
                "target_source_file": None,
                "routing_confidence": 0.0,
                "route_reason_short": "",
            },
            "retrieval_mode": "hybrid_global",
            "hits": [],
            "answer_markdown": "",
            "citations": [],
            "evidence_cards": [],
            "book_context_hint": "",
            "answer_plan": {
                "heading": "",
                "sections": [],
                "style_tips": [],
            },
            "route_debug": {},
        }
        
        # Run pipeline in thread to avoid blocking
        state = await asyncio.to_thread(run_agent_pipeline, initial_state)
        
        # Build evidence cards
        state = explain_node(state)
        
        # Stream the answer
        accumulated_answer = ""
        citations = []
        
        for token, metadata in synthesize_answer_streaming(state):
            if token:
                # Stream token
                accumulated_answer += token
                event_data = json.dumps({"type": "token", "content": token})
                yield f"data: {event_data}\n\n"
            
            if metadata.get("done"):
                # Stream metadata
                citations = metadata.get("citations", [])
                evidence_cards = state.get("evidence_cards", [])
                
                metadata_event = json.dumps({
                    "type": "metadata",
                    "citations": citations,
                    "evidence_cards": evidence_cards,
                })
                yield f"data: {metadata_event}\n\n"
                
                # Save assistant message
                await save_message(
                    user_id,
                    conversation_id,
                    "assistant",
                    accumulated_answer,
                    citations,
                    evidence_cards,
                    access_token=access_token,
                )
                
                # Send done event
                done_event = json.dumps({"type": "done"})
                yield f"data: {done_event}\n\n"
                break
        
    except Exception as e:
        error_event = json.dumps({"type": "error", "message": str(e)})
        yield f"data: {error_event}\n\n"


# API Routes
@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Navy RAG API"}


@app.get("/api/books")
async def get_books():
    """Get list of available books."""
    return {"books": _normalized_books()}


@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    auth: Dict[str, str] = Depends(get_auth_context),
):
    """
    Stream chat response.
    
    Returns Server-Sent Events (SSE) stream.
    """
    conversation_id = request.conversation_id
    user_id = auth["user_id"]
    access_token = auth["access_token"]
    normalized_book_lock = _normalize_book_lock(request.book_lock)
    
    # Create new conversation if needed
    if not conversation_id:
        # Generate title from first message
        title = request.message[:50] + ("..." if len(request.message) > 50 else "")
        conversation = await create_conversation(
            user_id,
            title,
            normalized_book_lock,
            access_token=access_token,
        )
        conversation_id = conversation["id"]
    
    return StreamingResponse(
        stream_chat_response(
            request.message,
            conversation_id,
            user_id,
            normalized_book_lock,
            request.top_k,
            access_token,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/conversations")
async def get_conversations(
    auth: Dict[str, str] = Depends(get_auth_context),
) -> List[ConversationResponse]:
    """Get all conversations for the current user."""
    user_id = auth["user_id"]
    supabase = get_supabase(auth["access_token"])
    
    result = supabase.table("conversations")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .execute()
    
    return result.data


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    auth: Dict[str, str] = Depends(get_auth_context),
) -> List[MessageResponse]:
    """Get all messages for a conversation."""
    user_id = auth["user_id"]
    supabase = get_supabase(auth["access_token"])
    
    # Verify conversation belongs to user
    conv_result = supabase.table("conversations")\
        .select("id")\
        .eq("id", conversation_id)\
        .eq("user_id", user_id)\
        .execute()
    
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get messages
    result = supabase.table("messages")\
        .select("*")\
        .eq("conversation_id", conversation_id)\
        .order("created_at")\
        .execute()
    
    return result.data


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    auth: Dict[str, str] = Depends(get_auth_context),
):
    """Delete a conversation and all its messages."""
    user_id = auth["user_id"]
    supabase = get_supabase(auth["access_token"])
    
    # Verify conversation belongs to user
    conv_result = supabase.table("conversations")\
        .select("id")\
        .eq("id", conversation_id)\
        .eq("user_id", user_id)\
        .execute()
    
    if not conv_result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Delete conversation (messages will cascade delete)
    supabase.table("conversations")\
        .delete()\
        .eq("id", conversation_id)\
        .execute()
    
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
