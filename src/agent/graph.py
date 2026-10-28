"""
LangGraph Graph — ReAct agent with retry loop.

Flow:
  START → triage ─┬─(needs tools)→ tools ─┬─(success)→ response → END
                  │                       │
                  │                       └─(tool error, retries < 3)→ tools
                  │
                  └─(general)→ response → END
"""
from langgraph.graph import END, StateGraph

from src.agent.nodes import TOOL_ERROR_PREFIX, response_node, tool_node, triage_node
from src.agent.state import AgentState

MAX_RETRIES = 3


def should_use_tools(state: AgentState) -> str:
    """Router after triage: decide whether to call tools or respond directly."""
    return "response" if state.get("intent", "general") == "general" else "tools"


def after_tools(state: AgentState) -> str:
    """Router after tools: retry on tool/LLM errors (not on ordinary 'not found' answers)."""
    has_error = any(
        str(v).startswith(TOOL_ERROR_PREFIX) for v in state.get("tool_results", {}).values()
    )
    if has_error and state.get("retry_count", 0) < MAX_RETRIES:
        return "retry"
    return "response"


def build_graph():
    """Build and compile the LangGraph state graph with retry loop."""
    workflow = StateGraph(AgentState)

    workflow.add_node("triage", triage_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("response", response_node)

    workflow.set_entry_point("triage")
    workflow.add_conditional_edges("triage", should_use_tools, {"tools": "tools", "response": "response"})
    workflow.add_conditional_edges("tools", after_tools, {"retry": "tools", "response": "response"})
    workflow.add_edge("response", END)

    return workflow.compile()


agent_graph = build_graph()
