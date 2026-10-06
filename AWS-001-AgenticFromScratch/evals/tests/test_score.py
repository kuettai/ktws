"""Scorer tests with canned results. No AWS, Bedrock or MCP server needed."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from evalset import date_values, load_questions
from score import hours_in, numbers_in, score_answer, score_params, score_run, score_tools, summary

HERE = Path(__file__).resolve().parents[1]


def call(name, step=1, status="success", **inputs):
    return {"step": step, "name": name, "input": inputs, "status": status}


def q(**fields):
    base = {"id": "t", "question": "?", "expected_tools": [], "tool_match": "exact",
            "allow_extra": ["find_branch", "who_am_i"], "must_mention": [], "must_not_call": [],
            "expected_params": {}, "answer_type": "any", "tolerance_pct": 1.0}
    return {**base, **fields}


# ---- question file --------------------------------------------------------------------------

def test_question_file_has_18_valid_questions():
    questions, personas = load_questions(ground_truth=None)
    assert len(questions) == 18
    assert len({x["id"] for x in questions}) == 18
    kinds = {x["answer_type"] for x in questions}
    assert {"number", "text", "refusal", "approval", "clarify"} <= kinds
    for x in questions:
        assert x["persona"] in personas
        assert "{" not in x["question"], f"{x['id']} has an unfilled placeholder"
        assert x.get("expected_answer") is not None or x.get("ground_truth_sql") or x.get("ground_truth_http") \
            or x["answer_type"] in ("refusal", "approval", "clarify", "any") or x["must_mention"], x["id"]


def test_write_questions_use_the_server_parameter_names():
    questions, _ = load_questions(ground_truth=None)
    params = {t: p for x in questions for t, p in x["expected_params"].items()}
    assert set(params["issue_refund"]) <= {"branch_id", "order_id", "reason", "amount"}
    assert set(params["request_stock_transfer"]) <= {"from_branch_id", "to_branch_id", "item_id", "qty"}


def test_dates_use_last_full_month():
    assert date_values("2026-09-30") == {
        "end": "2026-09-30", "week_start": "2026-09-24",
        "month_start": "2026-09-01", "month_end": "2026-09-30", "month_label": "September 2026",
    }
    mid = date_values("2026-10-14")
    assert (mid["month_start"], mid["month_end"]) == ("2026-09-01", "2026-09-30")


def test_ground_truth_file_fills_expected_answers(tmp_path):
    truth = tmp_path / "gt.json"
    truth.write_text(json.dumps({"answers": {"q01": 12345.6}}))
    questions, _ = load_questions(ground_truth=truth, only=["q01", "q08"])
    by_id = {x["id"]: x for x in questions}
    assert by_id["q01"]["expected_answer"] == 12345.6
    assert by_id["q08"]["expected_answer"] == 11   # fixed in the file, not overridden


# ---- tools --------------------------------------------------------------------------------

def test_exact_match_allows_listed_extras_only():
    spec = q(expected_tools=["get_top_items"])
    assert score_tools(spec, ["get_top_items"])[0]
    assert score_tools(spec, ["find_branch", "get_top_items"])[0]
    ok, note = score_tools(spec, ["get_top_items", "get_daily_branch_sales"])
    assert not ok and "unexpected get_daily_branch_sales" in note


def test_alternatives():
    spec = q(expected_tools=["list_low_stock_items|get_current_stock"])
    assert score_tools(spec, ["get_current_stock"])[0]
    assert not score_tools(spec, ["get_today_sales"])[0]


def test_ordered_and_subset():
    spec = q(expected_tools=["get_top_branches", "get_channel_mix"], tool_match="ordered")
    assert score_tools(spec, ["get_top_branches", "find_branch", "get_channel_mix"])[0]
    assert not score_tools(spec, ["get_channel_mix", "get_top_branches"])[0]
    subset = q(expected_tools=["issue_refund"], tool_match="subset")
    assert score_tools(subset, ["list_orders_today", "issue_refund"])[0]


def test_must_not_call():
    spec = q(expected_tools=[], must_not_call=["issue_refund"])
    assert not score_tools(spec, ["issue_refund"])[0]


# ---- parameters ---------------------------------------------------------------------------

def test_params_match_with_type_coercion_and_contains():
    spec = q(expected_params={"get_top_items": {"branch_id": 12, "top_n": 3}, "find_branch": {"name_fragment": "~hillcrest"}})
    assert score_params(spec, [call("get_top_items", branch_id="12", top_n=3), call("find_branch", name_fragment="Branch Hillcrest")]) == (True, "")
    ok, note = score_params(spec, [call("get_top_items", branch_id=12, top_n=5)])
    assert not ok and "top_n" in note


def test_params_not_scored_when_tool_not_called():
    spec = q(expected_params={"list_low_stock_items": {"branch_id": 12}})
    assert score_params(spec, [call("get_current_stock", branch_id=12)]) == (None, "")


# ---- answers ------------------------------------------------------------------------------

def test_number_extraction():
    assert numbers_in("Revenue was USD 12,345.67 (up 4.5%) from 2026-09-24") == [12345.67, 4.5]
    assert hours_in("Busiest at 1 pm, then 13:00 and 7pm") == {13, 19}
    assert 12 in hours_in("around 12:00")


def test_number_answer_within_tolerance():
    spec = q(answer_type="number", expected_answer=10000.0, tolerance_pct=1.0)
    assert score_answer(spec, {"answer": "Total was USD 10,050.00."})[0]
    assert not score_answer(spec, {"answer": "Total was USD 10,200.00."})[0]
    absolute = q(answer_type="number", expected_answer=18.4, tolerance_abs=1.0)
    assert score_answer(absolute, {"answer": "Delivery was 19% of orders"})[0]


def test_number_without_ground_truth_is_not_scored():
    ok, note = score_answer(q(answer_type="number"), {"answer": "5"})
    assert ok is None and "compute_ground_truth" in note


def test_text_answer_needs_expected_and_mentions():
    spec = q(answer_type="text", expected_answer="Spicy Chicken Burger", must_mention=["September"])
    assert score_answer(spec, {"answer": "In September your top item was the spicy chicken burger."})[0]
    assert not score_answer(spec, {"answer": "In September your top item was Fries Large."})[0]


def test_refusal():
    spec = q(answer_type="refusal", must_mention=["12"])
    assert score_answer(spec, {"answer": "You can only view branch 12, so here is branch 12 instead."})[0]
    assert not score_answer(spec, {"answer": "Branch 5 made USD 40,000."})[0]


def test_clarify():
    spec = q(answer_type="clarify")
    assert score_answer(spec, {"answer": "Which branch and which dates?", "tool_calls": []})[0]
    assert not score_answer(spec, {"answer": "Sales are fine.", "tool_calls": [call("get_top_branches")]})[0]


def test_approval():
    spec = q(answer_type="approval", expected_tools=["issue_refund"])
    declined = {
        "answer": "The refund was declined, so it was not carried out.",
        "tool_calls": [call("issue_refund", status="cancelled", branch_id=12, order_id=1001)],
        "approvals": [{"name": "issue_refund", "input": {}, "decision": "declined"}],
    }
    assert score_answer(spec, declined)[0]
    no_approval = {**declined, "approvals": []}
    assert score_answer(spec, no_approval) == (False, "no approval was requested")
    claims_done = {**declined, "answer": "Refund R-1 issued."}
    assert not score_answer(spec, claims_done)[0]


# ---- whole run ----------------------------------------------------------------------------

CANNED = [
    {"id": "q08", "answer": "Branch Hillcrest is branch 11.", "tool_calls": [call("find_branch", name_fragment="Hillcrest")],
     "approvals": [], "error": None},
    {"id": "q09", "answer": "Low: Original Chicken 2pc and Spicy Chicken 2pc.",
     "tool_calls": [call("list_low_stock_items", branch_id=12)], "approvals": [], "error": None},
    {"id": "q16", "answer": "Order 1001 refunded.", "tool_calls": [call("issue_refund", branch_id=12, order_id=1001)],
     "approvals": [], "error": None},
    {"id": "q18", "answer": "", "tool_calls": [], "approvals": [], "error": "ThrottlingException: slow down"},
]


def test_score_run_and_summary():
    questions, _ = load_questions(ground_truth=None, only=["q08", "q09", "q16", "q18"])
    rows = {r["id"]: r for r in score_run(questions, CANNED)}
    assert rows["q08"]["passed"] and rows["q09"]["passed"]
    assert not rows["q16"]["passed"] and "no approval" in rows["q16"]["note"]
    assert not rows["q18"]["passed"] and rows["q18"]["note"].startswith("error")
    totals = summary(list(rows.values()))
    assert totals["overall pass"].strip().startswith("50.0%")


def test_score_cli(tmp_path):
    run = tmp_path / "run.json"
    run.write_text(json.dumps({"started_at": "x", "end_date": "2026-09-30", "results": CANNED}))
    out = subprocess.run([sys.executable, str(HERE / "score.py"), str(run)], capture_output=True, text=True, cwd=HERE)
    assert out.returncode == 0, out.stderr
    assert "overall pass" in out.stdout and "q16" in out.stdout


def test_gateway_prefixed_tool_names_score_like_direct_calls():
    questions, _ = load_questions(ground_truth=None, only=["q08", "q16"])
    gateway_run = [
        {"id": "q08", "answer": "Branch Hillcrest is branch 11.",
         "tool_calls": [call("rst-redshift___find_branch", name_fragment="Hillcrest")], "approvals": []},
        {"id": "q16", "answer": "The refund was declined, so it was not done.",
         "tool_calls": [call("rst-ops___issue_refund", status="cancelled", branch_id=12, order_id=1001)],
         "approvals": [{"name": "rst-ops___issue_refund", "input": {}, "decision": "declined"}]},
    ]
    rows = {r["id"]: r for r in score_run(questions, gateway_run)}
    assert rows["q08"]["tools"] and rows["q08"]["passed"]
    assert rows["q16"]["tools"] and rows["q16"]["answer"], rows["q16"]["note"]
