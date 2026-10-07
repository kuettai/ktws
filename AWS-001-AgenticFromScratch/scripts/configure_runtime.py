#!/usr/bin/env python3
"""Fill in the settings the MCP server needs on AgentCore Runtime (Day 2 Module 02).

    python scripts/configure_runtime.py rstday2 [--agent RstMcp] [--participant <name>]
    (on Windows: py scripts\\configure_runtime.py rstday2)

Run from the workshop folder, after `agentcore add agent`. It reads your Day 1 stacks and
Cognito app clients, then writes into rstday2/agentcore/agentcore.json:

    executionRoleArn   the Day 1 task role rst-mcp-task-<region> (it may read Redshift as mcp_reader)
    envVars            Redshift, Ops API and sign-in settings, the same ones ECS gave the server

It prints every value it sets (the Ops API key is hidden). Works on Windows, macOS and
Linux; needs the AWS CLI v2 on the PATH and your AWS_PROFILE / AWS_REGION set.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def aws(*args: str) -> str:
    out = subprocess.run(["aws", *args, "--output", "text"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"AWS CLI failed: aws {' '.join(args[:2])}\n{out.stderr.strip()}")
    return out.stdout.strip()


def output(stack: str, key: str) -> str:
    value = aws("cloudformation", "describe-stacks", "--stack-name", stack,
                "--query", f"Stacks[0].Outputs[?OutputKey=='{key}'].OutputValue")
    if not value or value == "None":
        sys.exit(f"Stack {stack} has no output {key}. Is it deployed in this account and region?")
    return value


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("project", help="AgentCore project folder, e.g. rstday2")
    p.add_argument("--agent", default="RstMcp", help="runtime name in agentcore.json (default RstMcp)")
    p.add_argument("--participant", default="", help="shared account: your participant name")
    args = p.parse_args()
    if not shutil.which("aws"):
        sys.exit("The AWS CLI v2 is not on the PATH.")

    config_file = Path(args.project) / "agentcore" / "agentcore.json"
    if not config_file.exists():
        sys.exit(f"{config_file} not found. Run this from the workshop folder, after `agentcore create`.")
    config = json.loads(config_file.read_text())
    runtime = next((r for r in config.get("runtimes", []) if r["name"] == args.agent), None)
    if runtime is None:
        sys.exit(f"No runtime named {args.agent} in {config_file}. Run `agentcore add agent --name {args.agent} ...` first.")

    suffix = f"-{args.participant}" if args.participant else ""
    mcp_stack = f"RstMcpStack{suffix}"
    account = aws("sts", "get-caller-identity", "--query", "Account")
    region = aws("ec2", "describe-availability-zones", "--query", "AvailabilityZones[0].RegionName")
    pool_id = output("RstAuthStack", "UserPoolId")
    mcp_url = output(mcp_stack, "McpUrl")
    ops_url = output(mcp_stack, "OpsApiUrl")
    ops_key = aws("secretsmanager", "get-secret-value", "--secret-id", output(mcp_stack, "OpsApiKeySecretArn"),
                  "--query", "SecretString")

    # The app clients from Day 1 Module 06 (by hand, or by the catch-up deploy).
    clients = json.loads(subprocess.run(
        ["aws", "cognito-idp", "list-user-pool-clients", "--user-pool-id", pool_id, "--max-results", "60",
         "--query", "UserPoolClients[].[ClientName,ClientId]", "--output", "json"],
        capture_output=True, text=True, check=True).stdout)
    wanted = {f"quick-user{suffix}", f"quick-s2s{suffix}", f"kiro-user{suffix}"}
    client_ids = [cid for name, cid in clients if name in wanted]
    if not client_ids:
        sys.exit(f"No app clients named {', '.join(sorted(wanted))} in user pool {pool_id} (Day 1 Module 06 Part B).")

    env = {
        "MCP_TRANSPORT": "http",
        "AWS_REGION": region,
        "REDSHIFT_WORKGROUP": "rst-workshop",
        "REDSHIFT_DATABASE": "dev",
        "OPS_API_BASE_URL": ops_url,
        "OPS_API_KEY": ops_key,
        # The server re-checks the token Runtime already checked, and reads role and branch_id from it.
        "OIDC_ISSUER": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}",
        "OIDC_ALLOWED_AUDIENCES": ",".join(client_ids),
        "OIDC_REQUIRED_SCOPES": f"{mcp_url}/read",
        # The resource the read scope belongs to (Day 1): the same tokens work on ECS and on Runtime.
        "MCP_PUBLIC_URL": mcp_url,
    }
    runtime["executionRoleArn"] = f"arn:aws:iam::{account}:role/rst-mcp-task-{region}"
    runtime["runtimeVersion"] = "PYTHON_3_12"  # the same Python as the Day 1 container
    runtime["envVars"] = [{"name": k, "value": v} for k, v in env.items()]
    config_file.write_text(json.dumps(config, indent=2) + "\n")

    print(f"Updated {config_file}, runtime {args.agent}:")
    print(f"  executionRoleArn = {runtime['executionRoleArn']}")
    print(f"  runtimeVersion = {runtime['runtimeVersion']}")
    for k, v in env.items():
        shown = "(hidden)" if k == "OPS_API_KEY" else v
        print(f"  {k} = {shown}")
    print("The promotions tools are not set up on Runtime (that service stays inside the Day 1 VPC).")


if __name__ == "__main__":
    main()
