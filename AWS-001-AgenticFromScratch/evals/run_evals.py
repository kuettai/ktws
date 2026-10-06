"""Run every evaluation question through the restaurant agent and save what happened.

    uv run python run_evals.py                      # all questions, local MCP server
    uv run python run_evals.py --only q01,q12       # some questions
    uv run python score.py results/latest.json      # then score the run

Each question gets a fresh agent (no memory of earlier questions), signed in as the question's
persona. Every tool call is recorded. Write actions are always DECLINED, so an evaluation run
never changes data; the score checks that the agent asked for approval and reported it was not done.

Local (default): starts solutions/mcp-server per persona with LOCAL_ROLE / LOCAL_BRANCH_ID.
Remote: set MCP_URL and one token per persona, e.g. MCP_TOKEN_HQ, MCP_TOKEN_MANAGER_BRANCH_12.
Needs Bedrock model access (BEDROCK_MODEL_ID, AWS_REGION) and the MCP server's data sources.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from rst_agent import ToolCallRecorder, ask, build_agent, http_server, stdio_server
from rst_agent.agent import DEFAULT_MODEL_ID

from evalset import HERE, date_values, load_questions


def connect(persona_name: str, persona: dict):
    if url := os.environ.get("MCP_URL"):
        token = os.environ.get(f"MCP_TOKEN_{persona_name.upper()}") or os.environ.get("MCP_TOKEN")
        if not token:
            raise SystemExit(f"Set MCP_TOKEN_{persona_name.upper()} (a token for {persona_name}) to run against {url}")
        return http_server(url, token)
    return stdio_server(role=persona["role"], branch_id=persona.get("branch_id"))


def run_question(tools, question: dict, model_id: str | None) -> dict:
    recorder = ToolCallRecorder(printer=None)
    approvals = []

    def decline_and_record(name, tool_input):
        approvals.append({"name": name, "input": tool_input, "decision": "declined"})
        return False

    agent = build_agent(tools, approver=decline_and_record, recorder=recorder, model_id=model_id)
    started = time.monotonic()
    try:
        answer = str(ask(agent, question["question"], approver=decline_and_record))
        error = None
    except Exception as e:  # keep going: one broken question should not stop the run
        answer, error = "", f"{type(e).__name__}: {e}"
    return {
        "id": question["id"],
        "persona": question["persona"],
        "question": question["question"],
        "answer": answer.strip(),
        "tool_calls": recorder.calls,
        "approvals": approvals,
        "error": error,
        "seconds": round(time.monotonic() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", default=str(HERE / "questions.yaml"))
    parser.add_argument("--ground-truth", default=str(HERE / "ground_truth.json"))
    parser.add_argument("--only", help="comma-separated question IDs")
    parser.add_argument("--end-date", help="last day of data (default SEED_END_DATE or 2026-09-30)")
    parser.add_argument("--model-id", help="Bedrock model ID (default BEDROCK_MODEL_ID or built-in default)")
    parser.add_argument("--label", default="", help="short note saved with the run, e.g. 'after renaming get_top_items'")
    parser.add_argument("--out", help="results file (default results/<timestamp>.json, also copied to results/latest.json)")
    args = parser.parse_args()

    questions, personas = load_questions(
        args.questions, end_date=args.end_date, ground_truth=args.ground_truth,
        only=args.only.split(",") if args.only else None,
    )
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    questions.sort(key=lambda q: q["persona"])
    for persona_name, group in groupby(questions, key=lambda q: q["persona"]):
        with connect(persona_name, personas[persona_name]) as server:
            tools = server.list_tools_sync()
            for q in group:
                print(f"{q['id']} [{persona_name}] {q['question']}")
                result = run_question(tools, q, args.model_id)
                called = " > ".join(c["name"] for c in result["tool_calls"]) or "(no tools)"
                print(f"     {called}  ({result['seconds']}s){'  ERROR ' + result['error'] if result['error'] else ''}")
                results.append(result)
    results.sort(key=lambda r: r["id"])

    run = {
        "started_at": started_at,
        "label": args.label,
        "model_id": args.model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
        "endpoint": os.environ.get("MCP_URL", "local stdio"),
        "end_date": date_values(args.end_date)["end"],
        "ground_truth": {q["id"]: q["expected_answer"] for q in questions if q.get("expected_answer") is not None},
        "results": results,
    }
    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = Path(args.out) if args.out else out_dir / f"{started_at.replace(':', '')}.json"
    out.write_text(json.dumps(run, indent=2, default=str))
    (out_dir / "latest.json").write_text(out.read_text())
    print(f"\nSaved {out}. Score it with: uv run python score.py {out}")


if __name__ == "__main__":
    main()
