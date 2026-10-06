"""Lab 1: ToolCallRecorder shows how the agent works step by step."""
import pytest

from rst_agent import SYSTEM_PROMPT, ToolCallRecorder, build_agent

from fakes import ALL_TOOLS, EXECUTED, ScriptedModel


@pytest.fixture(autouse=True)
def _clear():
    EXECUTED.clear()


def test_recorder_traces_multi_step_plan():
    recorder = ToolCallRecorder(printer=None)
    agent = build_agent(ALL_TOOLS, recorder=recorder, model=ScriptedModel([
        [("get_top_items", {"branch_id": 12, "start_date": "2026-09-01", "end_date": "2026-09-30"})],
        [("get_current_stock", {"branch_id": 12})],
        "Spicy Chicken Burger is your top seller and is low on stock.",
    ]))
    result = agent("What is my best seller and am I low on it?")

    assert "low on stock" in str(result)
    assert recorder.tool_names == ["get_top_items", "get_current_stock"]
    assert [c["step"] for c in recorder.calls] == [1, 2]
    assert all(c["status"] == "success" for c in recorder.calls)
    assert recorder.calls[0]["input"]["branch_id"] == 12


def test_recorder_prints_each_step():
    lines = []
    agent = build_agent(
        ALL_TOOLS,
        recorder=ToolCallRecorder(printer=lines.append),
        model=ScriptedModel([[("get_current_stock", {"branch_id": 12})], "ok"]),
    )
    agent("stock?")
    assert lines[0].startswith("[step 1] calling get_current_stock")
    assert lines[1].startswith("[step 1] get_current_stock success")


def test_parallel_tool_calls_get_their_own_steps():
    recorder = ToolCallRecorder(printer=None)
    agent = build_agent(ALL_TOOLS, recorder=recorder, model=ScriptedModel([
        [("get_current_stock", {"branch_id": 12}), ("get_current_stock", {"branch_id": 5})],
        "ok",
    ]))
    agent("compare stock at 12 and 5")
    assert [c["input"]["branch_id"] for c in recorder.calls] == [12, 5]
    assert [c["step"] for c in recorder.calls] == [1, 2]


def test_reset_clears_calls():
    recorder = ToolCallRecorder(printer=None)
    agent = build_agent(ALL_TOOLS, recorder=recorder, model=ScriptedModel([[("get_current_stock", {"branch_id": 12})], "ok"]))
    agent("stock?")
    recorder.reset()
    assert recorder.calls == []


def test_system_prompt_rules():
    assert "Never guess" in SYSTEM_PROMPT
    assert "issue_refund" in SYSTEM_PROMPT and "approve" in SYSTEM_PROMPT
