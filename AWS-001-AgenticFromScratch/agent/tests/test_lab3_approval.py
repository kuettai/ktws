"""Lab 3: a person approves actions that change data."""
import pytest
from strands import Agent

from rst_agent import ApprovalHook, ToolCallRecorder, ask, auto_approver, build_agent
from rst_agent.hooks import APPROVED, DECLINED

from fakes import ALL_TOOLS, EXECUTED, GATEWAY_TOOLS, ScriptedModel, tool_results

REFUND = ("issue_refund", {"branch_id": 12, "order_id": 1001, "reason": "cold food"})
TRANSFER = ("request_stock_transfer", {"from_branch_id": 12, "to_branch_id": 5, "item_id": 3, "qty": 20})


@pytest.fixture(autouse=True)
def _clear():
    EXECUTED.clear()


def make(turns, **kwargs):
    model = ScriptedModel(turns)
    return build_agent(ALL_TOOLS, model=model, **kwargs), model


def test_read_tools_never_ask_for_approval():
    asked = []
    agent, _ = make([[("get_current_stock", {"branch_id": 12})], "ok"],
                    approver=lambda name, args: asked.append(name) or True)
    agent("stock?")
    assert asked == []
    assert EXECUTED == [("get_current_stock", {"branch_id": 12})]


def test_approved_write_runs():
    agent, _ = make([[REFUND], "Refund R-1 issued."], approver=auto_approver(True))
    agent("Refund order 1001 at branch 12, cold food")
    assert EXECUTED == [("issue_refund", {"branch_id": 12, "order_id": 1001})]


@pytest.mark.parametrize("call", [REFUND, TRANSFER])
def test_declined_write_is_cancelled_and_model_is_told(call):
    agent, model = make([[call], "It was not carried out."], approver=auto_approver(False))
    agent("do it")

    assert EXECUTED == []
    result = tool_results(model.seen[-1])[0]
    assert result["status"] == "error"
    assert "declined" in result["content"][0]["text"] and "NOT done" in result["content"][0]["text"]


def test_approver_sees_tool_and_arguments():
    seen = []
    agent, _ = make([[REFUND], "ok"], approver=lambda name, args: seen.append((name, args)) or False)
    agent("refund")
    assert seen == [REFUND]


def test_without_approver_agent_pauses_for_a_person():
    agent, _ = make([[REFUND], "Refund R-1 issued."])
    result = agent("Refund order 1001 at branch 12, cold food")

    assert result.stop_reason == "interrupt"
    assert EXECUTED == []
    pending = result.interrupts[0]
    assert pending.reason["tool"] == "issue_refund"
    assert pending.reason["input"]["order_id"] == 1001

    resumed = agent([{"interruptResponse": {"interruptId": pending.id, "response": APPROVED}}])
    assert resumed.stop_reason == "end_turn"
    assert EXECUTED == [("issue_refund", {"branch_id": 12, "order_id": 1001})]


def test_only_an_explicit_approval_counts():
    agent, _ = make([[REFUND], "not done"])
    pending = agent("refund it").interrupts[0]
    agent([{"interruptResponse": {"interruptId": pending.id, "response": "maybe"}}])
    assert EXECUTED == []


def test_ask_resolves_pause_with_approver():
    agent, _ = make([[REFUND], "done"])
    ask(agent, "refund it", approver=auto_approver(True))
    assert len(EXECUTED) == 1


def test_ask_without_approver_declines():
    agent, _ = make([[REFUND], "not done"])
    ask(agent, "refund it")
    assert EXECUTED == []


def test_approval_hook_records_decisions():
    hook = ApprovalHook(auto_approver(False))
    agent = Agent(model=ScriptedModel([[TRANSFER], "ok"]), tools=ALL_TOOLS, hooks=[hook], callback_handler=None)
    agent("move 20 burgers to branch 5")
    assert hook.decisions == [{"name": TRANSFER[0], "input": TRANSFER[1], "decision": DECLINED}]


def test_recorder_marks_declined_call_cancelled_and_resume_is_not_double_counted():
    recorder = ToolCallRecorder(printer=None)
    agent, _ = make([[REFUND], "not done"], recorder=recorder)
    ask(agent, "refund it")
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["status"] == "cancelled"


@pytest.mark.parametrize("call", [
    ("rst-ops___issue_refund", {"branch_id": 12, "order_id": 1001, "reason": "cold food"}),
    ("rst-api___issueRefund", {"branchId": 12, "orderId": 1001, "reason": "cold food"}),
])
def test_write_tools_behind_gateway_still_need_approval(call):
    """Through AgentCore Gateway tool names carry a target prefix. They must still pause."""
    asked = []
    model = ScriptedModel([[call], "It was not carried out."])
    agent = build_agent(ALL_TOOLS + GATEWAY_TOOLS, model=model,
                        approver=lambda name, args: asked.append(name) or False)
    agent("refund order 1001")
    assert asked == [call[0]]
    assert EXECUTED == []
