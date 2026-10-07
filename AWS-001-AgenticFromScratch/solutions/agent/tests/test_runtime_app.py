"""Module 05: the AgentCore Runtime entrypoint. Scripted model and fake tools, no AWS."""
import pytest

import runtime_app
from rst_agent import ToolCallRecorder, build_agent

from fakes import ALL_TOOLS, EXECUTED, ScriptedModel

REFUND = ("issue_refund", {"branch_id": 12, "order_id": 1001, "reason": "cold food"})


@pytest.fixture(autouse=True)
def _clear():
    EXECUTED.clear()
    runtime_app.SESSIONS.clear()


def factory_for(turns, tokens=None):
    def factory(token):
        if tokens is not None:
            tokens.append(token)
        recorder = ToolCallRecorder(printer=None)
        agent = build_agent(ALL_TOOLS, model=ScriptedModel(turns), recorder=recorder)
        return runtime_app.Session(agent=agent, recorder=recorder)
    return factory


def test_read_question_returns_answer_and_tool_calls():
    factory = factory_for([[("get_top_items", {"branch_id": 12, "start_date": "2026-09-01",
                                               "end_date": "2026-09-30"})], "Spicy Chicken Burger."])
    out = runtime_app.handle({"prompt": "best seller?"}, "s1", "tok", factory)
    assert out["status"] == "done"
    assert "Spicy Chicken Burger" in out["answer"]
    assert [c["name"] for c in out["tool_calls"]] == ["get_top_items"]


def test_token_from_first_call_builds_the_session():
    tokens = []
    factory = factory_for(["hi", "again"], tokens)
    runtime_app.handle({"prompt": "a"}, "s1", "tok-1", factory)
    runtime_app.handle({"prompt": "b"}, "s1", "tok-1", factory)
    assert tokens == ["tok-1"]          # one agent per session, reused


@pytest.mark.parametrize("approve, executed", [(True, 1), (False, 0)])
def test_write_pauses_then_follows_the_person(approve, executed):
    factory = factory_for([[REFUND], "Done." if approve else "Not carried out."])
    out = runtime_app.handle({"prompt": "Refund order 1001, cold food"}, "s1", "tok", factory)
    assert out["status"] == "needs_approval"
    assert out["pending"][0]["tool"] == "issue_refund"
    assert EXECUTED == []                # nothing runs before a person answers

    out = runtime_app.handle({"approve": approve}, "s1", "tok", factory)
    assert out["status"] == "done"
    assert len(EXECUTED) == executed


def test_approval_sent_as_prompt_text_like_agentcore_invoke():
    """`agentcore invoke '{"approve": false}'` arrives as {"prompt": '{"approve": false}'}."""
    factory = factory_for([[REFUND], "Not carried out."])
    runtime_app.handle({"prompt": "Refund order 1001, cold food"}, "s1", "tok", factory)
    out = runtime_app.handle({"prompt": '{"approve": false}'}, "s1", "tok", factory)
    assert out["status"] == "done"
    assert EXECUTED == []


def test_new_prompt_blocked_while_approval_pending():
    factory = factory_for([[REFUND], "x"])
    runtime_app.handle({"prompt": "Refund order 1001"}, "s1", "tok", factory)
    out = runtime_app.handle({"prompt": "something else"}, "s1", "tok", factory)
    assert out["status"] == "error"


def test_approve_without_pending_is_an_error():
    out = runtime_app.handle({"approve": True}, "s1", "tok", factory_for(["x"]))
    assert out["status"] == "error"


def test_bearer_parsing():
    assert runtime_app._bearer({"Authorization": "Bearer abc"}) == "abc"
    assert runtime_app._bearer({}) is None
    assert runtime_app._bearer(None) is None
