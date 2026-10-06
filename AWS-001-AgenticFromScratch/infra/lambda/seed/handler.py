"""CloudFormation custom resource: generate mock data, upload to S3, load into Redshift.

Bundled with data/*.sql and data/generate_seed.py at synth time (see data-stack.ts).

Create: load data for SeedEndDate (YYYY-MM-DD; empty = yesterday, UTC), then views and grants.
Update: always re-apply views, grants and IAM role mapping (cheap, idempotent), so adding a
participant role works. Reload the data only when a new, different SeedEndDate is passed on
purpose. An empty or unchanged SeedEndDate (e.g. `cdk deploy RstMcpStack` without -c
seedEndDate, which also updates this stack) keeps the data as it is.
"""
import json
import logging
import os
import subprocess
import sys
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

HERE = Path(__file__).parent
SEED_DIR = Path("/tmp/seed")
TABLES = ["fact_inventory_daily", "fact_order_items", "fact_orders",
          "dim_customer", "dim_date", "dim_menu_item", "dim_branch"]

s3 = boto3.client("s3")
data_api = boto3.client("redshift-data")


def statements(sql_text: str) -> list[str]:
    """Split a .sql file on ';' at end of line, dropping comment-only chunks."""
    out, current = [], []
    for line in sql_text.splitlines():
        line = line.split("--", 1)[0]  # our SQL files have no '--' inside string literals
        if not line.strip():
            continue
        current.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";")
            if stmt:
                out.append(stmt)
            current = []
    return out


def run(sql: str, props: dict, tolerate: tuple[str, ...] = ()) -> None:
    sid = data_api.execute_statement(
        WorkgroupName=props["WorkgroupName"], Database=props["Database"],
        SecretArn=props["AdminSecretArn"], Sql=sql,
    )["Id"]
    while True:
        desc = data_api.describe_statement(Id=sid)
        if desc["Status"] == "FINISHED":
            return
        if desc["Status"] in ("FAILED", "ABORTED"):
            error = desc.get("Error", "")
            if any(t in error for t in tolerate):
                log.info("Ignored: %s", error)
                return
            raise RuntimeError(f"{sql[:120]}... failed: {error}")
        time.sleep(2)


def end_date(value: str) -> str:
    """SeedEndDate as YYYY-MM-DD. Empty means yesterday (UTC)."""
    if not value:
        return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"SeedEndDate must be YYYY-MM-DD, got {value!r}")
    return date.fromisoformat(value).isoformat()


def load_data(props: dict, seed_end_date: str) -> None:
    """Generate the mock data for the 180 days up to seed_end_date and (re)load every table."""
    bucket = props["SeedBucket"]
    log.info("Loading data up to %s", seed_end_date)
    subprocess.run([sys.executable, str(HERE / "generate_seed.py"), "--out", str(SEED_DIR),
                    "--end-date", seed_end_date], check=True)
    for f in SEED_DIR.iterdir():
        s3.upload_file(str(f), bucket, f"seed/{f.name}")

    for stmt in statements((HERE / "ddl.sql").read_text()):
        run(stmt, props)
    for table in TABLES:
        run(f"TRUNCATE rst.{table}", props)
    copy_sql = (HERE / "copy.sql").read_text().replace("<SEED_BUCKET>", bucket)
    for stmt in statements(copy_sql):
        if stmt.lstrip().upper().startswith("COPY"):
            run(stmt, props)


def apply_access(props: dict) -> None:
    """Views, the read-only mcp_reader role, and the IAM roles mapped to it."""
    for stmt in statements((HERE / "views.sql").read_text()):
        run(stmt, props)
    for stmt in statements((HERE / "grants.sql").read_text()):
        run(stmt, props, tolerate=("already exists",))

    # Map IAM roles (ECS task role, participant role) to mcp_reader explicitly.
    for role_name in filter(None, props.get("ReaderRoleNames", "").split(",")):
        user = f'"IAMR:{role_name.strip()}"'
        run(f"CREATE USER {user} PASSWORD DISABLE", props, tolerate=("already exists",))
        run(f"GRANT ROLE mcp_reader TO {user}", props, tolerate=("already",))


def on_event(event, context):
    log.info(json.dumps({k: v for k, v in event.items() if k != "ResponseURL"}))
    props = event["ResourceProperties"]
    if event["RequestType"] == "Create":
        load_data(props, end_date(props.get("SeedEndDate", "")))
        apply_access(props)
    elif event["RequestType"] == "Update":
        new = props.get("SeedEndDate", "")
        old = event.get("OldResourceProperties", {}).get("SeedEndDate", "")
        if new and new != old:
            load_data(props, end_date(new))
        else:
            log.info("SeedEndDate %r unchanged or not given: keeping the loaded data", new)
        apply_access(props)
    return {"PhysicalResourceId": event.get("PhysicalResourceId", "rst-seed")}
