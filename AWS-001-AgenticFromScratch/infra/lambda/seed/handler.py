"""CloudFormation custom resource: generate mock data, upload to S3, load into Redshift.

Bundled with data/*.sql and data/generate_seed.py at synth time (see data-stack.ts).
Idempotent: safe on stack update (tables truncated before COPY, "already exists" ignored).
"""
import json
import logging
import os
import subprocess
import sys
import time
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


def seed(props: dict) -> None:
    bucket = props["SeedBucket"]
    subprocess.run([sys.executable, str(HERE / "generate_seed.py"), "--out", str(SEED_DIR),
                    "--end-date", props["SeedEndDate"]], check=True)
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
    if event["RequestType"] in ("Create", "Update"):
        seed(event["ResourceProperties"])
    return {"PhysicalResourceId": event.get("PhysicalResourceId", "rst-seed")}
