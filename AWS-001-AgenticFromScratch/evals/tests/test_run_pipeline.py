"""run_evals.run_question with a scripted model, then score it. No AWS or Bedrock."""
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "solutions" / "agent" / "tests"))

import run_evals  # noqa: E402
from evalset import load_questions  # noqa: E402
from fakes import ALL_TOOLS, EXECUTED, ScriptedModel  # noqa: E402
from score import score_run  # noqa: E402


def test_write_question_is_declined_and_scores_as_pass(monkeypatch):
    EXECUTED.clear()
    model = ScriptedModel([
        [("issue_refund", {"branch_id": 12, "order_id": 1001, "reason": "cold food"})],
        "The refund was declined, so it was not carried out.",
    ])
    monkeypatch.setattr(run_evals, "build_agent", partial(run_evals.build_agent, model=model))
    questions, _ = load_questions(ground_truth=None, only=["q16"])

    result = run_evals.run_question(ALL_TOOLS, questions[0], model_id=None)

    assert EXECUTED == []                                  # evaluation never changes data
    assert result["approvals"][0]["name"] == "issue_refund"
    assert result["tool_calls"][0]["status"] == "cancelled"
    row = score_run(questions, [result])[0]
    assert row["passed"], row


def test_errors_are_captured_not_raised(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("model unavailable")
    monkeypatch.setattr(run_evals, "ask", broken)
    monkeypatch.setattr(run_evals, "build_agent", partial(run_evals.build_agent, model=ScriptedModel(["x"])))
    questions, _ = load_questions(ground_truth=None, only=["q01"])
    result = run_evals.run_question(ALL_TOOLS, questions[0], model_id=None)
    assert result["error"] == "RuntimeError: model unavailable"
