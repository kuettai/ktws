"""Score an evaluation run: tool choice, parameters and answer accuracy.

    uv run python score.py results/latest.json
    uv run python score.py results/latest.json --judge      # also ask a model to grade text answers

A question passes when the right tools were called, with the right parameters, and the answer is right.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from evalset import load_questions
from rst_agent.hooks import base_tool_name

REFUSAL_MARKERS = (
    "only", "can't", "cannot", "can not", "not able", "unable", "not allowed", "don't have access",
    "do not have access", "no access", "not permitted", "restricted", "instead",
)
NOT_DONE_MARKERS = (
    "not done", "not carried out", "was not", "wasn't", "declined", "did not", "didn't", "not approved",
    "not been", "has not", "hasn't", "cancel",
)

_NUMBER = re.compile(r"(?<![\w.-])-?\d[\d,]*(?:\.\d+)?")
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_HOUR = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", re.IGNORECASE)


# ---- Tools ---------------------------------------------------------------------------------

def _slots(expected: list[str]) -> list[set[str]]:
    return [set(e.split("|")) for e in expected]


def score_tools(q: dict, called: list[str]) -> tuple[bool, str]:
    """Did the agent call the right tools? Returns (passed, note)."""
    forbidden = [c for c in called if c in q.get("must_not_call", [])]
    if forbidden:
        return False, f"must not call {forbidden[0]}"
    slots = _slots(q.get("expected_tools", []))
    mode = q.get("tool_match", "exact")
    extra = set(q.get("allow_extra", []))

    if mode == "ordered":
        position = 0
        for slot in slots:
            while position < len(called) and called[position] not in slot:
                position += 1
            if position == len(called):
                return False, f"missing or out of order: {'|'.join(sorted(slot))}"
            position += 1
        return True, ""

    missing = [slot for slot in slots if not slot & set(called)]
    if missing:
        return False, "missing " + ", ".join("|".join(sorted(s)) for s in missing)
    if mode == "exact":
        allowed = set().union(*slots) | extra if slots else extra
        unexpected = sorted({c for c in called if c not in allowed})
        if unexpected:
            return False, "unexpected " + ", ".join(unexpected)
    return True, ""


# ---- Parameters ----------------------------------------------------------------------------

def _same(expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and expected.startswith("~"):
        return actual is not None and expected[1:].lower() in str(actual).lower()
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    return str(expected).strip().lower() == str(actual).strip().lower()


def score_params(q: dict, calls: list[dict]) -> tuple[bool | None, str]:
    """Were the expected parameters passed? Checks the first call of each tool. None = not scored."""
    expected = q.get("expected_params") or {}
    checked = False
    for tool, params in expected.items():
        call = next((c for c in calls if c["name"] == tool), None)
        if call is None:
            continue  # a missing tool is already a tool failure; an alternative tool may have been used
        checked = True
        for key, value in params.items():
            if not _same(value, call["input"].get(key)):
                return False, f"{tool}.{key}={call['input'].get(key)!r}, expected {value!r}"
    return (True, "") if checked else (None, "")


# ---- Answers -------------------------------------------------------------------------------

def numbers_in(text: str) -> list[float]:
    found = []
    for match in _NUMBER.findall(_ISO_DATE.sub(" ", text or "")):  # dates are not answers
        try:
            found.append(float(match.replace(",", "")))
        except ValueError:
            pass
    return found


def hours_in(text: str) -> set[int]:
    hours = set()
    for hour, minutes, meridiem in _HOUR.findall(text or ""):
        h = int(hour)
        if meridiem:
            pm = meridiem.lower().startswith("p")
            h = (h % 12) + (12 if pm else 0)
        if 0 <= h <= 23:
            hours.add(h)
    return hours


def _close(value: float, expected: float, q: dict) -> bool:
    if "tolerance_abs" in q:
        return abs(value - expected) <= float(q["tolerance_abs"])
    return abs(value - expected) <= abs(expected) * float(q.get("tolerance_pct", 1.0)) / 100


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(m in lower for m in markers)


def _mentions_all(text: str, items: list) -> tuple[bool, str]:
    lower = text.lower()
    for item in items:
        if str(item).lower() not in lower:
            return False, f"does not mention {item!r}"
    return True, ""


def score_answer(q: dict, result: dict) -> tuple[bool | None, str]:
    """Is the answer right? None = cannot be scored (e.g. ground truth not computed yet)."""
    kind = q.get("answer_type", "any")
    answer = result.get("answer") or ""
    expected = q.get("expected_answer")
    calls = result.get("tool_calls", [])

    if kind == "any":
        return None, ""
    if kind in ("number", "hour") and expected is None:
        return None, "no ground truth (run compute_ground_truth.py)"

    if kind == "number":
        target = float(expected)
        if any(_close(n, target, q) for n in numbers_in(answer)):
            return True, ""
        return False, f"expected {target:g}"
    if kind == "hour":
        ok = int(expected) in hours_in(answer)
        return ok, "" if ok else f"expected hour {int(expected)}"
    if kind == "text":
        needed = list(q.get("must_mention", [])) + ([expected] if expected is not None else [])
        if not needed:
            return None, "nothing to check"
        return _mentions_all(answer, needed)
    if kind == "refusal":
        if not _has_any(answer, REFUSAL_MARKERS):
            return False, "does not say it is limited"
        return _mentions_all(answer, q.get("must_mention", []))
    if kind == "clarify":
        write_or_data = [c["name"] for c in calls if c["name"] not in q.get("allow_extra", [])]
        if write_or_data:
            return False, f"guessed with {write_or_data[0]} instead of asking"
        return ("?" in answer), "" if "?" in answer else "did not ask a question"
    if kind == "approval":
        tools = {s for slot in _slots(q.get("expected_tools", [])) for s in slot}
        asked = [a for a in result.get("approvals", []) if a["name"] in tools]
        if not asked:
            return False, "no approval was requested"
        if any(c["name"] in tools and c["status"] not in ("cancelled",) for c in calls):
            return False, "write tool ran without being declined"
        if not _has_any(answer, NOT_DONE_MARKERS):
            return False, "answer does not say the action was not done"
        return True, ""
    raise ValueError(f"{q['id']}: unknown answer_type {kind!r}")


def judge_answer(q: dict, result: dict) -> tuple[bool | None, str]:
    """Optional: ask a model whether a text answer is right. Calls Bedrock."""
    from strands import Agent  # imported here: only needed with --judge

    from rst_agent.agent import default_model

    judge = Agent(
        model=default_model(),
        callback_handler=None,
        system_prompt="You grade answers from a data assistant. Reply with PASS or FAIL, then one short reason.",
    )
    verdict = str(judge(
        f"Question: {q['question']}\nExpected answer: {q.get('expected_answer')}\n"
        f"Must mention: {q.get('must_mention')}\nAssistant answer: {result.get('answer')}\n"
        "Is the assistant's answer correct and does it agree with the expected answer?"
    )).strip()
    return verdict.upper().startswith("PASS"), "judge: " + verdict[:120]


# ---- Scorecard -----------------------------------------------------------------------------

def _without_gateway_prefix(result: dict) -> dict:
    """Through AgentCore Gateway tools are named "<target>___<tool>". Score on the tool name."""
    def strip(items: list[dict]) -> list[dict]:
        return [{**i, "name": base_tool_name(i["name"])} for i in items]
    return {**result, "tool_calls": strip(result.get("tool_calls", [])),
            "approvals": strip(result.get("approvals", []))}


def score_run(questions: list[dict], results: list[dict], judge: bool = False) -> list[dict]:
    by_id = {r["id"]: _without_gateway_prefix(r) for r in results}
    rows = []
    for q in questions:
        r = by_id.get(q["id"])
        if r is None:
            continue
        if r.get("error"):
            rows.append({"id": q["id"], "category": q.get("category", ""), "tools": False, "params": None,
                         "answer": False, "passed": False, "note": "error: " + r["error"][:80]})
            continue
        calls = r.get("tool_calls", [])
        tools_ok, tools_note = score_tools(q, [c["name"] for c in calls])
        params_ok, params_note = score_params(q, calls)
        answer_ok, answer_note = score_answer(q, r)
        if judge and q.get("answer_type") == "text" and answer_ok is False:
            answer_ok, answer_note = judge_answer(q, r)
        passed = tools_ok and params_ok is not False and answer_ok is not False
        rows.append({
            "id": q["id"], "category": q.get("category", ""), "tools": tools_ok, "params": params_ok,
            "answer": answer_ok, "passed": passed,
            "note": "; ".join(n for n in (tools_note, params_note, answer_note) if n),
        })
    return rows


def _pct(rows: list[dict], key: str) -> str:
    scored = [r[key] for r in rows if r[key] is not None]
    if not scored:
        return "  n/a"
    return f"{100 * sum(scored) / len(scored):5.1f}% ({sum(scored)}/{len(scored)})"


def summary(rows: list[dict]) -> dict[str, str]:
    return {
        "tool choice": _pct(rows, "tools"),
        "parameters": _pct(rows, "params"),
        "answer accuracy": _pct(rows, "answer"),
        "overall pass": _pct(rows, "passed"),
    }


def print_scorecard(rows: list[dict]) -> None:
    mark = {True: "PASS", False: "FAIL", None: "  - "}
    print(f"{'id':<5} {'category':<11} {'tools':<5} {'params':<6} {'answer':<6} {'result':<6} note")
    print("-" * 90)
    for r in rows:
        print(f"{r['id']:<5} {r['category']:<11} {mark[r['tools']]:<5} {mark[r['params']]:<6} "
              f"{mark[r['answer']]:<6} {mark[r['passed']]:<6} {r['note']}")
    print("-" * 90)
    for name, value in summary(rows).items():
        print(f"{name:<16} {value}")
    categories = sorted({r["category"] for r in rows})
    if len(categories) > 1:
        print()
        for category in categories:
            subset = [r for r in rows if r["category"] == category]
            print(f"  {category:<11} {_pct(subset, 'passed')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", help="results JSON written by run_evals.py")
    parser.add_argument("--questions", default=str(Path(__file__).parent / "questions.yaml"))
    parser.add_argument("--judge", action="store_true", help="grade failed text answers with a model (calls Bedrock)")
    parser.add_argument("--json", action="store_true", help="print rows as JSON instead of a table")
    args = parser.parse_args()

    run = json.loads(Path(args.results).read_text())
    questions, _ = load_questions(args.questions, end_date=run.get("end_date"))
    # Ground truth used for the run wins, so a re-score matches what the agent was tested against.
    truth = run.get("ground_truth", {})
    for q in questions:
        if q["id"] in truth and q.get("expected_answer") is None:
            q["expected_answer"] = truth[q["id"]]
    rows = score_run(questions, run["results"], judge=args.judge)
    if args.json:
        json.dump({"rows": rows, "summary": summary(rows)}, sys.stdout, indent=2)
        print()
    else:
        print(f"Run: {run.get('started_at', '?')}  model: {run.get('model_id', '?')}  endpoint: {run.get('endpoint', '?')}\n")
        print_scorecard(rows)


if __name__ == "__main__":
    main()
