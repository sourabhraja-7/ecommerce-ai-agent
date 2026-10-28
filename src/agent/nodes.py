"""
LangGraph Nodes — the three processing stages of the ReAct agent.

  1. triage_node   → classify intent, extract entities
  2. tool_node     → let the LLM pick tools via function calling, then execute them
  3. response_node → compose the final customer-facing reply
"""
import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agent.state import AgentState
from src.agent.tools import ALL_TOOLS, TOOLS_BY_NAME
from src.config import settings

# Prefix for results that came from a tool *crashing* (as opposed to a normal
# "not found" answer). Only these trigger the retry loop.
TOOL_ERROR_PREFIX = "⚠️ TOOL_ERROR"

# ---------------------------------------------------------------------------
# Shared LLM instances (lazy, so tests can import without an API key)
# ---------------------------------------------------------------------------

_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.temperature,
            api_key=settings.openai_api_key,
            max_retries=2,
        )
    return _llm


def _last_user_message(messages: list) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return ""


# ---------------------------------------------------------------------------
# 1. TRIAGE NODE
# ---------------------------------------------------------------------------

class Triage(BaseModel):
    intent: Literal["order_status", "shipping_tracking", "return_request", "return_policy", "general"]
    order_id: str = Field(default="", description="Order ID like ORD-1001, empty if none")
    tracking_number: str = Field(default="", description="Tracking number like FDX-78901234, empty if none")
    customer_email: str = Field(default="", description="Email address, empty if none")


TRIAGE_PROMPT = """You are an e-commerce customer support triage assistant.
Classify the customer's LATEST message and extract any entities. Use earlier
conversation turns only to resolve references like "it" or "that order".

Intents:
- order_status: asking about an order, listing their orders, or searching for an order
- shipping_tracking: asking where a package is / tracking
- return_request: wants to return an item or asks if an order can be returned
- return_policy: asking about the return / refund policy in general
- general: greetings, thanks, chitchat, anything else"""


def triage_node(state: AgentState) -> dict:
    """Classify the user's intent and extract entities."""
    messages = state.get("messages", [])
    if not _last_user_message(messages):
        return {"intent": "general", "error_message": ""}

    history = [m for m in messages if not isinstance(m, SystemMessage)][-6:]
    try:
        triage: Triage = _get_llm().with_structured_output(Triage).invoke(
            [SystemMessage(content=TRIAGE_PROMPT), *history]
        )
        return {**triage.model_dump(), "error_message": ""}
    except Exception as e:
        return {
            "intent": "general",
            "order_id": "",
            "tracking_number": "",
            "customer_email": "",
            "error_message": f"triage failed: {e}",
        }


# ---------------------------------------------------------------------------
# 2. TOOL NODE (ReAct "Act" step)
# ---------------------------------------------------------------------------

TOOL_PROMPT = """You are an e-commerce support agent. Call the tool(s) needed to answer
the customer's latest message.

Customer intent: {intent}
Known context:
- Order ID: {order_id}
- Tracking Number: {tracking_number}
- Email: {email}

Rules:
- For a return request, call check_return_eligibility first. Only call
  initiate_return if the customer clearly asked to return AND gave a reason.
- If the customer gave a vague description (e.g. "my keyboard order"), use search_orders."""


def tool_node(state: AgentState) -> dict:
    """Use LLM function-calling to decide and execute the right tool(s)."""
    retries = state.get("retry_count", 0)
    prompt = TOOL_PROMPT.format(
        intent=state.get("intent", "general"),
        order_id=state.get("order_id") or "unknown",
        tracking_number=state.get("tracking_number") or "unknown",
        email=state.get("customer_email") or "unknown",
    )
    history = [m for m in state.get("messages", []) if not isinstance(m, SystemMessage)]

    try:
        ai_msg = _get_llm().bind_tools(ALL_TOOLS).invoke([SystemMessage(content=prompt), *history])
    except Exception as e:
        return {
            "tool_results": {"llm": f"{TOOL_ERROR_PREFIX}: {e}"},
            "retry_count": retries + 1,
            "error_message": str(e),
        }

    tool_results: dict[str, str] = {}
    for tc in ai_msg.tool_calls or []:
        name = tc["name"]
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            tool_results[name] = f"{TOOL_ERROR_PREFIX}: unknown tool '{name}'"
            continue
        try:
            tool_results[name] = str(tool.invoke(tc["args"]))
        except Exception as e:
            tool_results[name] = f"{TOOL_ERROR_PREFIX}: {type(e).__name__}: {e}"

    return {"tool_results": tool_results, "retry_count": retries + 1, "error_message": ""}


# ---------------------------------------------------------------------------
# 3. RESPONSE NODE
# ---------------------------------------------------------------------------

RESPONSE_PROMPT = """You are a friendly e-commerce customer support agent. Reply in English.

Compose a concise, well-structured response to the customer's latest message
using ONLY the information below. Never invent order details.

Customer intent: {intent}
Tool results:
{tool_results}

Guidelines:
- Use bullet points where helpful; include order IDs and tracking numbers.
- If a lookup failed (❌), say so plainly and suggest what the customer can provide.
- If a return is eligible but not yet started, ask for the reason
  (defective, wrong item, not as described, changed mind, damaged, too late).
- End with: "Is there anything else I can help you with?\""""

GREETING = (
    "Hello! 👋 I'm your virtual support assistant. I can help you with:\n\n"
    "📦 **Order Status** — Check your order with your order ID or email.\n"
    "🚚 **Package Tracking** — Track your shipment with your tracking number.\n"
    "🔄 **Returns** — Learn about our return policy or start a return.\n\n"
    "How can I help you today?"
)

FALLBACK = (
    "I apologize, but I'm having trouble processing your request right now. "
    "Please try again in a moment, or contact our support team at support@example.com. "
    "Is there anything else I can help you with?"
)


def response_node(state: AgentState) -> dict:
    """Compose the final customer-facing response."""
    intent = state.get("intent", "general")
    tool_results = state.get("tool_results", {})
    good_results = {k: v for k, v in tool_results.items() if not str(v).startswith(TOOL_ERROR_PREFIX)}

    # Tools were needed but every attempt failed
    if intent != "general" and tool_results and not good_results:
        return {"final_response": FALLBACK}

    if intent == "general" and not tool_results:
        if state.get("error_message"):
            return {"final_response": FALLBACK}
        return {"final_response": GREETING}

    history = [m for m in state.get("messages", []) if not isinstance(m, SystemMessage)]
    prompt = RESPONSE_PROMPT.format(
        intent=intent,
        tool_results=json.dumps(good_results, ensure_ascii=False, indent=2) or "(none)",
    )
    try:
        response = _get_llm().invoke([SystemMessage(content=prompt), *history])
        return {"final_response": response.content.strip()}
    except Exception:
        return {"final_response": format_tool_results(intent, good_results)}


def format_tool_results(intent: str, tool_results: dict) -> str:
    """Format raw tool results into a plain response without the LLM."""
    headers = {
        "order_status": "Here are your order details:",
        "shipping_tracking": "Here is your shipment status:",
        "return_request": "Here is your return request status:",
        "return_policy": "Here is our return policy:",
    }
    parts = [headers.get(intent, "Here is what I found:"), ""]
    parts.extend(str(r) for r in tool_results.values())
    parts.append("\nIs there anything else I can help you with?")
    return "\n".join(parts)
