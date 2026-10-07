"""Redshift Data API helper (pre-built).

Tools call run_query(sql, params). Never build SQL with f-strings: pass values in params
and reference them in SQL as :name.

Environment:
    REDSHIFT_DATABASE        required, e.g. dev
    REDSHIFT_WORKGROUP       Redshift Serverless workgroup name, or
    REDSHIFT_CLUSTER_ID      provisioned cluster identifier (+ REDSHIFT_DB_USER)
    REDSHIFT_SECRET_ARN      optional, Secrets Manager credentials instead of IAM identity
    REDSHIFT_MAX_WAIT_SECONDS  optional, default 30
"""
import logging
import os
import time
from decimal import Decimal

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound
from mcp.server.mcpserver.exceptions import ToolError

log = logging.getLogger(__name__)

_client = None


class QueryError(ToolError):
    """Raised when a query fails. Message is shown to the model; details go to the log only."""


def _data_api():
    global _client
    if _client is None:
        # Pass the region on: boto3 reads AWS_DEFAULT_REGION or the profile's region, not AWS_REGION.
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        _client = boto3.client("redshift-data", region_name=region)
    return _client


def _target() -> dict:
    target = {"Database": os.environ["REDSHIFT_DATABASE"]}
    if workgroup := os.environ.get("REDSHIFT_WORKGROUP"):
        target["WorkgroupName"] = workgroup
    else:
        target["ClusterIdentifier"] = os.environ["REDSHIFT_CLUSTER_ID"]
        if db_user := os.environ.get("REDSHIFT_DB_USER"):
            target["DbUser"] = db_user
    if secret_arn := os.environ.get("REDSHIFT_SECRET_ARN"):
        target["SecretArn"] = secret_arn
    return target


def _to_python(field: dict, column: dict):
    if field.get("isNull"):
        return None
    if "longValue" in field:
        return field["longValue"]
    if "doubleValue" in field:
        return field["doubleValue"]
    if "booleanValue" in field:
        return field["booleanValue"]
    value = field.get("stringValue")
    if column.get("typeName") in ("numeric", "decimal") and value is not None:
        return float(Decimal(value))
    return value


def _wait(client, statement_id: str) -> tuple[str, dict]:
    """Poll a statement until it finishes or fails. Cancels it after REDSHIFT_MAX_WAIT_SECONDS."""
    max_wait = float(os.environ.get("REDSHIFT_MAX_WAIT_SECONDS", "30"))
    deadline = time.monotonic() + max_wait
    delay = 0.2
    while True:
        desc = client.describe_statement(Id=statement_id)
        if desc["Status"] in ("FINISHED", "FAILED", "ABORTED"):
            return statement_id, desc
        if time.monotonic() > deadline:
            client.cancel_statement(Id=statement_id)
            raise QueryError(f"The query took longer than {max_wait:.0f}s and was cancelled. Try a smaller date range.")
        time.sleep(delay)
        delay = min(delay * 1.5, 1.0)


def _aws_problem(exc: Exception) -> QueryError:
    """Turn an AWS-side failure (credentials, profile, region, workgroup) into a message that says
    what to check. Shown to the model and the user; contains no secrets."""
    profile = os.environ.get("AWS_PROFILE") or "not set (default credentials)"
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "not set"
    where = f"workgroup {os.environ.get('REDSHIFT_WORKGROUP')!r} in region {region}, AWS_PROFILE {profile}"
    log.error("Redshift unreachable (%s): %s", where, exc)
    if isinstance(exc, (ProfileNotFound, NoCredentialsError)):
        return QueryError(f"No usable AWS credentials ({where}). Set AWS_PROFILE to your workshop "
                          "profile in the terminal, in mcp-server/.env, or in Kiro's mcp.json.")
    code = exc.response.get("Error", {}).get("Code", "") if isinstance(exc, ClientError) else type(exc).__name__
    if code in ("ExpiredToken", "ExpiredTokenException", "UnrecognizedClientException", "InvalidClientTokenId"):
        return QueryError(f"The AWS credentials were refused ({code}; {where}). Sign in again or refresh them.")
    if code in ("ResourceNotFoundException", "ValidationException", "AccessDeniedException"):
        return QueryError(f"Can't use the Redshift workgroup ({code}; {where}). Check that AWS_PROFILE "
                          "and AWS_REGION point at the workshop account.")
    return QueryError(f"Can't reach Redshift ({code}; {where}). Check AWS_PROFILE and AWS_REGION.")


def run_query(sql: str, params: dict[str, object] | None = None) -> list[dict]:
    """Run a read-only query and return rows as a list of dicts keyed by column name."""
    try:
        client = _data_api()
    except (BotoCoreError, ClientError) as exc:
        raise _aws_problem(exc) from None
    request = {**_target(), "Sql": sql}
    if params:
        request["Parameters"] = [{"name": k, "value": str(v)} for k, v in params.items()]

    # Redshift Serverless sometimes fails the first query after it has been idle with
    # "Internal error encountered". That is not the query's fault, so try once more.
    for attempt in (1, 2):
        try:
            statement_id = client.execute_statement(**request)["Id"]
        except (BotoCoreError, ClientError) as exc:
            raise _aws_problem(exc) from None
        statement_id, desc = _wait(client, statement_id)
        if desc["Status"] == "FINISHED":
            break
        log.error("Query %s %s: %s", statement_id, desc["Status"], desc.get("Error"))
        if attempt == 1 and "Internal error" in (desc.get("Error") or ""):
            continue
        raise QueryError("The query failed. Check the parameters and try again.")

    if not desc.get("HasResultSet"):
        return []

    rows: list[dict] = []
    columns: list[dict] = []
    token = None
    while True:
        page = client.get_statement_result(Id=statement_id, **({"NextToken": token} if token else {}))
        columns = columns or page["ColumnMetadata"]
        for record in page["Records"]:
            rows.append({c["name"]: _to_python(f, c) for c, f in zip(columns, record)})
        token = page.get("NextToken")
        if not token:
            return rows
