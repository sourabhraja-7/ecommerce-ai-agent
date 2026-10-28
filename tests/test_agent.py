"""
Unit & integration tests for the E-Commerce Support Agent.
None of these need LLM credentials.
"""
from src.agent.graph import after_tools, build_graph, should_use_tools
from src.agent.nodes import TOOL_ERROR_PREFIX, response_node
from src.agent.tools import (
    check_return_eligibility,
    get_return_policy,
    initiate_return,
    lookup_order,
    search_orders,
    track_shipment,
)
from src.services.order_service import OrderService
from src.services.returns_service import ReturnsService
from src.services.shipping_service import ShippingService


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestOrderService:
    svc = OrderService()

    def test_get_existing_order(self):
        order = self.svc.get_order("ORD-1001")
        assert order is not None
        assert order.customer_name == "James Wilson"
        assert order.status == "delivered"
        assert len(order.items) == 2

    def test_get_order_case_insensitive(self):
        assert self.svc.get_order(" ord-1001 ") is not None

    def test_get_missing_order(self):
        assert self.svc.get_order("ORD-9999") is None

    def test_get_orders_by_email(self):
        orders = self.svc.get_orders_by_email("JAMES@example.com")
        assert {o.order_id for o in orders} == {"ORD-1001", "ORD-1011"}

    def test_search_orders_by_name(self):
        assert len(self.svc.search_orders("James")) == 2

    def test_search_orders_by_product(self):
        assert [o.order_id for o in self.svc.search_orders("Keyboard")] == ["ORD-1002"]

    def test_get_all_orders(self):
        assert len(self.svc.get_all_orders()) == 12

    def test_can_return_delivered_order(self):
        can, _ = self.svc.can_return("ORD-1005")
        assert can is True

    def test_cannot_return_cancelled_order(self):
        can, msg = self.svc.can_return("ORD-1004")
        assert can is False
        assert "cancel" in msg.lower()

    def test_cannot_return_unshipped_order(self):
        can, _ = self.svc.can_return("ORD-1003")
        assert can is False

    def test_cannot_return_expired_order(self):
        can, msg = self.svc.can_return("ORD-1008")
        assert can is False
        assert "14" in msg


class TestShippingService:
    svc = ShippingService()

    def test_track_existing(self):
        shipment = self.svc.track("FDX-78901234")
        assert shipment.carrier == "FedEx"
        assert shipment.status == "delivered"
        assert len(shipment.events) == 4

    def test_track_missing(self):
        assert self.svc.track("XXX-00000000") is None

    def test_readable_status(self):
        assert "delivered" in self.svc.get_readable_status("FDX-78901234").lower()


class TestReturnsService:
    svc = ReturnsService()

    def test_create_return_and_rma_sequence(self):
        first = self.svc.create_return("ORD-1012", "defective", 204.96)
        assert first.rma_number.startswith("RMA-")
        assert first.status == "approved"
        assert first.refund_amount == 204.96
        assert self.svc.get_return("ORD-1012").rma_number == first.rma_number

    def test_get_policy(self):
        assert "14 days" in self.svc.get_policy()


# ---------------------------------------------------------------------------
# Tool tests
# ---------------------------------------------------------------------------

class TestAgentTools:
    def test_lookup_order(self):
        result = lookup_order.invoke({"order_id": "ORD-1001"})
        assert "James Wilson" in result
        assert "delivered" in result
        assert "105.97" in result

    def test_lookup_missing_order(self):
        assert "not found" in lookup_order.invoke({"order_id": "ORD-XXXX"}).lower()

    def test_search_orders_tool(self):
        assert "ORD-1002" in search_orders.invoke({"query": "keyboard"})

    def test_track_shipment(self):
        result = track_shipment.invoke({"tracking_number": "UPS-45678901"})
        assert "UPS" in result
        assert "IN_TRANSIT" in result

    def test_get_return_policy(self):
        assert "14 days" in get_return_policy.invoke({})

    def test_check_return_eligibility(self):
        assert check_return_eligibility.invoke({"order_id": "ORD-1001"}).startswith("✅")

    def test_initiate_return_rejects_bad_reason(self):
        assert "Invalid reason" in initiate_return.invoke({"order_id": "ORD-1009", "reason": "meh"})

    def test_initiate_return_blocks_duplicates(self):
        first = initiate_return.invoke({"order_id": "ORD-1009", "reason": "changed mind"})
        assert "RMA-" in first
        second = initiate_return.invoke({"order_id": "ORD-1009", "reason": "defective"})
        assert "already exists" in second


# ---------------------------------------------------------------------------
# Graph tests
# ---------------------------------------------------------------------------

class TestGraph:
    def test_graph_has_nodes(self):
        nodes = build_graph().get_graph().nodes
        assert {"triage", "tools", "response"} <= set(nodes)

    def test_should_use_tools_logic(self):
        for intent in ("order_status", "shipping_tracking", "return_request", "return_policy"):
            assert should_use_tools({"intent": intent}) == "tools"
        assert should_use_tools({"intent": "general"}) == "response"

    def test_after_tools_retries_only_on_tool_errors(self):
        crashed = {"tool_results": {"lookup_order": f"{TOOL_ERROR_PREFIX}: db locked"}}
        assert after_tools({**crashed, "retry_count": 1}) == "retry"
        assert after_tools({**crashed, "retry_count": 3}) == "response"
        # A normal "not found" answer is a valid result, not a reason to retry
        not_found = {"tool_results": {"lookup_order": "❌ Order #X not found."}, "retry_count": 1}
        assert after_tools(not_found) == "response"

    def test_response_fallback_when_all_tools_failed(self):
        out = response_node({"intent": "order_status", "tool_results": {"x": f"{TOOL_ERROR_PREFIX}: boom"}})
        assert "trouble" in out["final_response"]

    def test_response_greeting_for_general(self):
        out = response_node({"intent": "general", "tool_results": {}})
        assert "How can I help" in out["final_response"]


# ---------------------------------------------------------------------------
# API tests (graph stubbed — no LLM)
# ---------------------------------------------------------------------------

class TestAPI:
    def test_health_and_chat_keep_session_history(self, monkeypatch):
        from fastapi.testclient import TestClient

        from src.api import routes
        from src.main import app

        seen = []

        class FakeGraph:
            def invoke(self, state, config):
                seen.append(len(state["messages"]))
                return {"final_response": "hi", "intent": "general", "tool_results": {}}

        monkeypatch.setattr(routes, "agent_graph", FakeGraph())
        with TestClient(app) as client:
            assert client.get("/api/v1/health").json()["status"] == "ok"
            for _ in range(2):
                r = client.post("/api/v1/chat", json={"message": "hello", "session_id": "t1"})
                assert r.status_code == 200
                assert r.json()["response"] == "hi"

        # Second call sees the first turn (user + assistant) plus the new message
        assert seen == [1, 3]
