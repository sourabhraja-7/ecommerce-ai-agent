"""
E-Commerce AI Support Agent
Customer support chat interface.
"""
import os
import uuid

import requests
import streamlit as st

API_URL = os.getenv("SUPPORT_API_URL", "http://localhost:8000/api/v1/chat")

# ── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title="E-Commerce Support Agent",
    page_icon="●",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Styling ──────────────────────────────────────────────────
st.markdown(
    """<style>
    .main .block-container { max-width: 800px; padding-top: 1.5rem; }
    #MainMenu, footer, [data-testid="stDecoration"], .stDeployButton { display: none !important; }

    .brand { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
    .brand-dot { width: 10px; height: 10px; border-radius: 50%; background: #4f46e5; }
    .brand-name { font-size: 1.25rem; font-weight: 700; letter-spacing: -0.3px; }
    .brand-sub { font-size: 0.8rem; opacity: .65; margin-top: -2px; margin-bottom: 20px; }

    [data-testid="stChatMessage"] { border-radius: 12px; padding: 12px 16px; margin: 8px 0; }
    .stButton > button { border-radius: 8px; font-size: 0.82rem; padding: 8px 12px; }
    .stButton > button:hover { border-color: #4f46e5; color: #4f46e5; }
    </style>""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="brand"><div class="brand-dot"></div><span class="brand-name">E-Commerce Support</span></div>'
    '<div class="brand-sub">AI-powered order &amp; shipping assistance</div>',
    unsafe_allow_html=True,
)

# ── Session ──────────────────────────────────────────────────
WELCOME = (
    "Hello! I'm your AI support agent. I can help you track orders, check shipments, "
    "and process returns.\n\nHow can I help you today?"
)
if "msgs" not in st.session_state:
    st.session_state.msgs = [{"role": "assistant", "text": WELCOME, "steps": None}]
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

INTENT_LABEL = {
    "order_status": "Order status inquiry detected.",
    "shipping_tracking": "Package tracking request detected.",
    "return_request": "Return request detected.",
    "return_policy": "Return policy question detected.",
    "general": "General inquiry.",
}
TOOL_LABEL = {
    "lookup_order": "Queried order management system.",
    "lookup_orders_by_email": "Searched orders by customer email.",
    "search_orders": "Ran cross-order search.",
    "track_shipment": "Pulled tracking from carrier.",
    "get_return_policy": "Retrieved return policy details.",
    "check_return_eligibility": "Checked return window & status.",
    "initiate_return": "Created RMA & initiated return.",
}


def thinking_text(steps: dict) -> str:
    lines = [f"●  {INTENT_LABEL.get(steps.get('intent', 'general'), 'Analyzed the request.')}"]
    ids = [v for v in (steps.get("order_id"), steps.get("tracking_number"), steps.get("customer_email")) if v]
    if ids:
        lines.append(f"   Identified: {', '.join(ids)}")
    for tn in steps.get("tool_results", {}):
        lines.append(f"●  {TOOL_LABEL.get(tn, 'Gathered data.')}  [{tn}]")
    return "\n".join(lines)


def call_api(query: str):
    try:
        r = requests.post(
            API_URL, json={"message": query, "session_id": st.session_state.session_id}, timeout=90
        )
        if r.status_code == 200:
            d = r.json()
            steps = {k: d.get(k, "") for k in ("intent", "order_id", "tracking_number", "customer_email")}
            steps["tool_results"] = d.get("tool_results", {})
            return d.get("response", "Sorry, something went wrong."), steps
        return f"API error ({r.status_code}). Please try again.", None
    except requests.exceptions.ConnectionError:
        return "**Cannot reach the server.** Start it with `uvicorn src.main:app --reload`.", None
    except Exception as e:
        return f"Error: {e}", None


def render(msg: dict):
    with st.chat_message(msg["role"]):
        if msg.get("steps"):
            with st.expander("Details", expanded=False):
                st.code(thinking_text(msg["steps"]), language=None)
        st.markdown(msg["text"])


# ── Quick Actions ────────────────────────────────────────────
actions = [
    ("Track ORD-1002", "What's the status of order ORD-1002?"),
    ("Shipment FDX-78901234", "Where is package FDX-78901234?"),
    ("Return Policy", "What is your return policy?"),
    ("My Orders", "Show orders for james@example.com"),
]
pending = None
for col, (label, query) in zip(st.columns(len(actions)), actions):
    if col.button(label, use_container_width=True):
        pending = query
st.divider()

# ── Chat ─────────────────────────────────────────────────────
for m in st.session_state.msgs:
    render(m)

prompt = st.chat_input("Type your message…") or pending
if prompt:
    user = {"role": "user", "text": prompt, "steps": None}
    st.session_state.msgs.append(user)
    render(user)
    with st.spinner("Thinking..."):
        reply, steps = call_api(prompt)
    bot = {"role": "assistant", "text": reply, "steps": steps}
    st.session_state.msgs.append(bot)
    render(bot)
