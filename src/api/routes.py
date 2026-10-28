"""
FastAPI Routes — the Agent Gateway.
"""
from collections import OrderedDict

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.graph import agent_graph
from src.api.schemas import ChatRequest, ChatResponse, HealthResponse
from src.observability.langfuse_setup import get_langfuse_client, get_langfuse_handler

router = APIRouter()

# In-memory conversation history per session (bounded LRU).
MAX_SESSIONS = 500
MAX_TURNS = 10
_sessions: "OrderedDict[str, list]" = OrderedDict()


def _get_history(session_id: str) -> list:
    history = _sessions.pop(session_id, [])
    _sessions[session_id] = history
    while len(_sessions) > MAX_SESSIONS:
        _sessions.popitem(last=False)
    return history


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Main chat endpoint: runs the full ReAct agent graph."""
    history = _get_history(req.session_id)
    user_msg = HumanMessage(content=req.message)

    initial_state = {
        "messages": [*history, user_msg],
        "intent": "",
        "order_id": "",
        "tracking_number": "",
        "customer_email": "",
        "tool_results": {},
        "final_response": "",
        "retry_count": 0,
        "error_message": "",
    }

    config: dict = {"metadata": {"session_id": req.session_id}}
    handler = get_langfuse_handler()
    if handler:
        config["callbacks"] = [handler]

    # The graph is synchronous; keep the event loop free.
    result = await run_in_threadpool(agent_graph.invoke, initial_state, config)

    client = get_langfuse_client()
    if client:
        client.flush()

    reply = result.get("final_response") or "Sorry, something went wrong."
    history.extend([user_msg, AIMessage(content=reply)])
    del history[: -MAX_TURNS * 2]

    return ChatResponse(
        response=reply,
        intent=result.get("intent", "general"),
        order_id=result.get("order_id", ""),
        tracking_number=result.get("tracking_number", ""),
        customer_email=result.get("customer_email", ""),
        tool_results=result.get("tool_results", {}),
    )
