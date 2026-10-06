import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

import server
import tools.write_tools as wt
from lib.auth import Caller
from tests.conftest import call_tool

ORDER = 20261001000120045


@pytest.fixture
def posts(monkeypatch):
    """Capture POSTs to the Operations API instead of sending them."""
    monkeypatch.setenv("OPS_API_BASE_URL", "http://ops.test/")
    monkeypatch.setenv("OPS_API_KEY", "k")
    captured = []
    replies = {"status": 200, "json": {"ok": True}}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured.append({"url": url, "json": json, "headers": headers})
        return httpx.Response(replies["status"], json=replies["json"])

    monkeypatch.setattr(wt.httpx, "post", fake_post)
    return captured, replies


def as_role(monkeypatch, role, branch=None):
    monkeypatch.setenv("LOCAL_ROLE", role)
    if branch is not None:
        monkeypatch.setenv("LOCAL_BRANCH_ID", str(branch))


def test_refund_posts_expected_body(posts):
    captured, _ = posts
    call_tool(server.mcp, "issue_refund", {"branch_id": 12, "order_id": ORDER, "reason": " Cold food ", "amount": 12.5})
    assert captured[0]["url"] == f"http://ops.test/pos/12/orders/{ORDER}/refund"
    assert captured[0]["json"] == {"reason": "Cold food", "amount": 12.5}
    assert captured[0]["headers"] == {"X-API-Key": "k"}


def test_full_refund_omits_amount(posts):
    captured, _ = posts
    call_tool(server.mcp, "issue_refund", {"branch_id": 12, "order_id": ORDER, "reason": "Wrong order"})
    assert captured[0]["json"] == {"reason": "Wrong order"}


def test_transfer_posts_expected_body(posts):
    captured, _ = posts
    call_tool(server.mcp, "request_stock_transfer", {"from_branch_id": 12, "to_branch_id": 5, "item_id": 1, "qty": 40})
    assert captured[0]["url"] == "http://ops.test/inventory/transfers"
    assert captured[0]["json"] == {"fromBranchId": 12, "toBranchId": 5, "itemId": 1, "qty": 40}


def test_manager_can_refund_own_branch(posts, monkeypatch):
    as_role(monkeypatch, "manager", 12)
    call_tool(server.mcp, "issue_refund", {"branch_id": 12, "order_id": ORDER, "reason": "x"})
    assert len(posts[0]) == 1


def test_manager_refused_other_branch_not_redirected(posts, monkeypatch):
    as_role(monkeypatch, "manager", 12)
    with pytest.raises(ToolError, match="only issue refunds for branch 12, not branch 5"):
        call_tool(server.mcp, "issue_refund", {"branch_id": 5, "order_id": ORDER, "reason": "x"})
    assert posts[0] == []


def test_manager_transfer_must_send_from_own_branch(posts, monkeypatch):
    as_role(monkeypatch, "manager", 12)
    call_tool(server.mcp, "request_stock_transfer", {"from_branch_id": 12, "to_branch_id": 5, "item_id": 1, "qty": 10})
    with pytest.raises(ToolError, match="only transfer stock for branch 12"):
        call_tool(server.mcp, "request_stock_transfer", {"from_branch_id": 5, "to_branch_id": 12, "item_id": 1, "qty": 10})
    assert len(posts[0]) == 1


@pytest.mark.parametrize("tool,args", [
    ("issue_refund", {"branch_id": 12, "order_id": ORDER, "reason": "x"}),
    ("request_stock_transfer", {"from_branch_id": 12, "to_branch_id": 5, "item_id": 1, "qty": 10}),
])
def test_staff_cannot_write(tool, args, posts, monkeypatch):
    as_role(monkeypatch, "staff", 12)
    with pytest.raises(ToolError, match="Only managers and HQ users"):
        call_tool(server.mcp, tool, args)
    assert posts[0] == []


def test_service_account_cannot_write(posts, monkeypatch):
    monkeypatch.setattr(wt, "current_caller", lambda: Caller("hq", None, "client", True))
    with pytest.raises(ToolError, match="Service accounts cannot issue refunds"):
        call_tool(server.mcp, "issue_refund", {"branch_id": 12, "order_id": ORDER, "reason": "x"})
    assert posts[0] == []


@pytest.mark.parametrize("args,message", [
    ({"from_branch_id": 12, "to_branch_id": 12, "item_id": 1, "qty": 5}, "must be different"),
    ({"from_branch_id": 12, "to_branch_id": 5, "item_id": 1, "qty": 501}, "qty"),
])
def test_transfer_input_validation(args, message, posts):
    with pytest.raises(ToolError, match=message):
        call_tool(server.mcp, "request_stock_transfer", args)
    assert posts[0] == []


@pytest.mark.parametrize("args,message", [
    ({"branch_id": 12, "order_id": ORDER, "reason": ""}, "reason is required"),
    ({"branch_id": 12, "order_id": ORDER, "reason": "x", "amount": -1}, "amount must be a positive"),
])
def test_refund_input_validation(args, message, posts):
    with pytest.raises(ToolError, match=message):
        call_tool(server.mcp, "issue_refund", args)
    assert posts[0] == []


def test_api_conflict_message_reaches_model(posts):
    _, replies = posts
    replies.update(status=409, json={"code": "NOT_REFUNDABLE", "message": "Order already refunded"})
    with pytest.raises(ToolError, match="Order already refunded"):
        call_tool(server.mcp, "issue_refund", {"branch_id": 12, "order_id": ORDER, "reason": "x"})


def test_write_tools_flag_data_change():
    import asyncio
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for name in ("issue_refund", "request_stock_transfer"):
        assert tools[name].description.startswith("CHANGES DATA")
