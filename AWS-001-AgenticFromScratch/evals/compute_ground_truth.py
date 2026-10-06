"""Work out the expected answers for this account's data and save them to ground_truth.json.

    uv run python compute_ground_truth.py              # Redshift + mock Operations API
    uv run python compute_ground_truth.py --print-sql  # just show the SQL, to run yourself

Run once per workshop account, after RstDataStack has loaded the data. The answers depend on
the seed (and seedEndDate), so they are not stored in questions.yaml.

Redshift answers: the ground_truth_sql of each question, first column of the first row.
    Uses the same settings as the MCP server: REDSHIFT_DATABASE and REDSHIFT_WORKGROUP
    (or REDSHIFT_CLUSTER_ID), AWS_REGION. Read-only queries on the mcp views.
Live answers: GET OPS_API_BASE_URL + ground_truth_http.path, then .field (header X-API-Key: OPS_API_KEY).
    Start mock-api with a fixed MOCK_NOW (e.g. 2026-10-01T14:30:00) for both this script and the
    evaluation run, or the live numbers will have moved on.
"""
import argparse
import json
import os
import time
import urllib.request
from decimal import Decimal
from pathlib import Path

from evalset import HERE, date_values, load_questions


def redshift_scalar(sql: str):
    import boto3

    client = boto3.client("redshift-data")
    target = {"Database": os.environ["REDSHIFT_DATABASE"]}
    if workgroup := os.environ.get("REDSHIFT_WORKGROUP"):
        target["WorkgroupName"] = workgroup
    else:
        target["ClusterIdentifier"] = os.environ["REDSHIFT_CLUSTER_ID"]
    statement_id = client.execute_statement(**target, Sql=sql)["Id"]
    while True:
        desc = client.describe_statement(Id=statement_id)
        if desc["Status"] == "FINISHED":
            break
        if desc["Status"] in ("FAILED", "ABORTED"):
            raise RuntimeError(desc.get("Error", desc["Status"]))
        time.sleep(0.3)
    records = client.get_statement_result(Id=statement_id)["Records"]
    if not records:
        return None
    field = records[0][0]
    if field.get("isNull"):
        return None
    for key in ("longValue", "doubleValue", "booleanValue"):
        if key in field:
            return field[key]
    value = field["stringValue"]
    try:
        return float(Decimal(value))
    except Exception:
        return value


def http_field(path: str, field: str):
    request = urllib.request.Request(
        os.environ.get("OPS_API_BASE_URL", "http://localhost:8080").rstrip("/") + path,
        headers={"X-API-Key": os.environ.get("OPS_API_KEY", "local-dev-key")},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        value = json.loads(response.read())
    for part in field.split("."):
        value = value[part]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", default=str(HERE / "questions.yaml"))
    parser.add_argument("--end-date", help="last day of data (default SEED_END_DATE or 2026-09-30)")
    parser.add_argument("--out", default=str(HERE / "ground_truth.json"))
    parser.add_argument("--print-sql", action="store_true")
    args = parser.parse_args()

    questions, _ = load_questions(args.questions, end_date=args.end_date, ground_truth=None)
    if args.print_sql:
        for q in questions:
            if q.get("ground_truth_sql"):
                print(f"-- {q['id']}: {q['question']}\n{q['ground_truth_sql'].strip()};\n")
        return

    answers, problems = {}, {}
    for q in questions:
        try:
            if q.get("ground_truth_sql"):
                answers[q["id"]] = redshift_scalar(q["ground_truth_sql"])
            elif q.get("ground_truth_http"):
                answers[q["id"]] = http_field(q["ground_truth_http"]["path"], q["ground_truth_http"]["field"])
            else:
                continue
            print(f"{q['id']}: {answers[q['id']]}")
        except Exception as e:
            problems[q["id"]] = str(e)
            print(f"{q['id']}: FAILED {e}")

    Path(args.out).write_text(json.dumps({
        "end_date": date_values(args.end_date)["end"],
        "mock_now": os.environ.get("MOCK_NOW"),
        "answers": answers,
        "problems": problems,
    }, indent=2, default=str))
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
