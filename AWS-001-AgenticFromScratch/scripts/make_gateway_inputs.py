#!/usr/bin/env python3
"""Write the input files for the Day 2 Module 03 AWS CLI commands (AgentCore Gateway).

    python scripts/make_gateway_inputs.py rstday2 [--participant <name>]
    (on Windows: py scripts\\make_gateway_inputs.py rstday2)

Run from the workshop folder, after Module 02 and after deploying RstAgentCoreStack. It reads
your Day 1 and Day 2 stacks, Cognito app clients and the Runtime, then writes JSON files into
rstday2/gateway/. Each AWS CLI command in Module 03 reads one of them with
`--cli-input-json file://...`, so you don't have to type long JSON (or escape quotes on Windows).

    api-key-provider.json   the Ops API key, for the AgentCore Identity vault
    oauth-provider.json     the quick-s2s app client, so the Gateway can sign in to Runtime
    gateway.json            the Gateway: Cognito sign-in, semantic search, the request interceptor
    target-ops-api.json     target 1: the Ops API, from mock-api/openapi.yaml
    target-runtime.json     target 2: your MCP server on AgentCore Runtime

Module 05 (Policy): run it again with --policies, after creating the policy engine. It adds
    policy-<name>.json                     each rule in day2/policies/*.cedar, for your gateway
    gateway-policy-log-only.json           attach the policy engine: only log decisions
    gateway-policy-enforce.json            ... then enforce them

Two files contain secrets (the API key and the client secret). rstday2/ is in .gitignore;
delete the two files after Module 03. Needs the AWS CLI v2 and AWS_PROFILE / AWS_REGION set.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # the workshop folder


def aws(*args: str, as_json: bool = False):
    out = subprocess.run(["aws", *args, "--output", "json" if as_json else "text"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"AWS CLI failed: aws {' '.join(args[:2])}\n{out.stderr.strip()}")
    return json.loads(out.stdout) if as_json else out.stdout.strip()


def output(stack: str, key: str) -> str:
    value = aws("cloudformation", "describe-stacks", "--stack-name", stack,
                "--query", f"Stacks[0].Outputs[?OutputKey=='{key}'].OutputValue")
    if not value or value == "None":
        sys.exit(f"Stack {stack} has no output {key}. Is it deployed in this account and region?")
    return value


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("project", help="AgentCore project folder from Module 02, e.g. rstday2")
    p.add_argument("--agent", default="RstMcp", help="runtime name from Module 02 (default RstMcp)")
    p.add_argument("--participant", default="", help="shared account: your participant name")
    p.add_argument("--policies", action="store_true", help="Module 05: also write the policy files")
    args = p.parse_args()
    if not shutil.which("aws"):
        sys.exit("The AWS CLI v2 is not on the PATH.")
    project = Path(args.project)
    if not (project / "agentcore" / "agentcore.json").exists():
        sys.exit(f"{project}/agentcore/agentcore.json not found. Run this from the workshop folder.")

    suffix = f"-{args.participant}" if args.participant else ""
    name = f"rst-gateway{suffix}"
    account = aws("sts", "get-caller-identity", "--query", "Account")
    region = aws("ec2", "describe-availability-zones", "--query", "AvailabilityZones[0].RegionName")
    vault = f"arn:aws:bedrock-agentcore:{region}:{account}:token-vault/default"
    api_key_name, oauth_name = f"rst-ops-api-key{suffix}", f"rst-runtime-s2s{suffix}"

    pool_id = output("RstAuthStack", "UserPoolId")
    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
    mcp_stack = f"RstMcpStack{suffix}"
    read_scope = output(mcp_stack, "McpUrl") + "/read"
    ops_url = output(mcp_stack, "OpsApiUrl")
    ops_key = aws("secretsmanager", "get-secret-value", "--secret-id", output(mcp_stack, "OpsApiKeySecretArn"),
                  "--query", "SecretString")
    ac_stack = f"RstAgentCoreStack{suffix}"
    role_arn, interceptor_arn = output(ac_stack, "GatewayRoleArn"), output(ac_stack, "InterceptorArn")

    clients = dict(aws("cognito-idp", "list-user-pool-clients", "--user-pool-id", pool_id, "--max-results", "60",
                       "--query", "UserPoolClients[].[ClientName,ClientId]", as_json=True))
    missing = [c for c in (f"kiro-user{suffix}", f"quick-user{suffix}", f"quick-s2s{suffix}") if c not in clients]
    if missing:
        sys.exit(f"App clients not found in user pool {pool_id}: {', '.join(missing)} (Day 1 Module 06 Part B).")
    s2s_id = clients[f"quick-s2s{suffix}"]
    s2s_secret = aws("cognito-idp", "describe-user-pool-client", "--user-pool-id", pool_id, "--client-id", s2s_id,
                     "--query", "UserPoolClient.ClientSecret")

    runtime_name = f"{project.name}_{args.agent}"
    runtimes = aws("bedrock-agentcore-control", "list-agent-runtimes", "--query",
                   f"agentRuntimes[?agentRuntimeName=='{runtime_name}'].agentRuntimeArn", as_json=True)
    if not runtimes:
        sys.exit(f"No AgentCore runtime named {runtime_name}. Finish Module 02 (agentcore deploy) first.")
    runtime_url = (f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
                   f"{urllib.parse.quote(runtimes[0], safe='')}/invocations?qualifier=DEFAULT")

    # The Gateway calls the Ops API at its public address, so the spec's server URL must be that address.
    spec = (HERE / "mock-api" / "openapi.yaml").read_text()
    spec = re.sub(r"(?m)^servers:\n  - url: \S+", f"servers:\n  - url: {ops_url}", spec)
    # Branch IDs as text for the Gateway: Cedar policies (Module 05) compare them with the token's
    # branch_id claim, and token claims are always text. The API itself reads "12" as 12.
    spec = spec.replace("      name: branchId\n      required: true\n      schema: { type: integer, minimum: 1 }",
                        "      name: branchId\n      required: true\n      schema: { type: string, pattern: \"^[0-9]+$\" }")
    for field in ("fromBranchId", "toBranchId"):
        spec = spec.replace(f"                {field}: {{ type: integer }}", f"                {field}: {{ type: string, pattern: \"^[0-9]+$\" }}")

    files = {
        "api-key-provider.json": {"name": api_key_name, "apiKey": ops_key},
        "oauth-provider.json": {
            "name": oauth_name,
            "credentialProviderVendor": "CustomOauth2",
            "oauth2ProviderConfigInput": {"customOauth2ProviderConfig": {
                "oauthDiscovery": {"discoveryUrl": discovery_url},
                "clientId": s2s_id, "clientSecret": s2s_secret}},
        },
        "gateway.json": {
            "name": name,
            "description": "Restaurant tools for Kiro, Quick and agents",
            "roleArn": role_arn,
            "protocolType": "MCP",
            "protocolConfiguration": {"mcp": {"searchType": "SEMANTIC"}},
            "authorizerType": "CUSTOM_JWT",
            "authorizerConfiguration": {"customJWTAuthorizer": {
                "discoveryUrl": discovery_url,
                "allowedClients": [clients[f"kiro-user{suffix}"], clients[f"quick-user{suffix}"]],
                "allowedScopes": [read_scope]}},
            "interceptorConfigurations": [{
                "interceptor": {"lambda": {"arn": interceptor_arn}},
                "interceptionPoints": ["REQUEST"],
                "inputConfiguration": {"passRequestHeaders": True}}],
            "exceptionLevel": "DEBUG",
        },
        "target-ops-api.json": {
            "name": "OpsApi",
            "description": "Restaurant Operations API: live stock, today's orders and sales, refunds, transfers",
            "targetConfiguration": {"mcp": {"openApiSchema": {"inlinePayload": spec}}},
            "credentialProviderConfigurations": [{"credentialProviderType": "API_KEY", "credentialProvider": {
                "apiKeyCredentialProvider": {"providerArn": f"{vault}/apikeycredentialprovider/{api_key_name}",
                                             "credentialLocation": "HEADER", "credentialParameterName": "X-API-Key"}}}],
        },
        "target-runtime.json": {
            "name": "RstMcp",
            "description": "Restaurant MCP server on AgentCore Runtime: Redshift history and live operations",
            "targetConfiguration": {"mcp": {"mcpServer": {"endpoint": runtime_url}}},
            "credentialProviderConfigurations": [{"credentialProviderType": "OAUTH", "credentialProvider": {
                "oauthCredentialProvider": {"providerArn": f"{vault}/oauth2credentialprovider/{oauth_name}",
                                            "scopes": [read_scope], "grantType": "CLIENT_CREDENTIALS"}}}],
        },
    }
    if args.policies:
        add_policy_files(files, name, suffix)
    out_dir = project / "gateway"
    out_dir.mkdir(exist_ok=True)
    for file_name, body in files.items():
        (out_dir / file_name).write_text(json.dumps(body, indent=2) + "\n")
        print(f"wrote {out_dir / file_name}")
    print(f"\nGateway name: {name}\nOps API:      {ops_url}\nRuntime:      {runtime_name}")
    print("api-key-provider.json and oauth-provider.json contain secrets: delete them after Module 03.")


def add_policy_files(files: dict, gateway_name: str, suffix: str) -> None:
    """Module 05: policy definitions for this gateway, and the gateway update to attach the engine."""
    gateways = aws("bedrock-agentcore-control", "list-gateways", "--query",
                   f"items[?name=='{gateway_name}'].gatewayId", as_json=True)
    if not gateways:
        sys.exit(f"No gateway named {gateway_name}. Create it first (Module 03).")
    gateway = aws("bedrock-agentcore-control", "get-gateway", "--gateway-identifier", gateways[0], as_json=True)
    engine_name = f"rst_policy_engine{suffix.replace('-', '_')}"
    engines = aws("bedrock-agentcore-control", "list-policy-engines", "--query",
                  f"policyEngines[?name=='{engine_name}'].policyEngineArn", as_json=True)
    if not engines:
        sys.exit(f"No policy engine named {engine_name}. Create it first (Module 05 step 1).")
    for cedar in sorted((HERE / "day2" / "policies").glob("*.cedar")):
        statement = cedar.read_text().replace("<GATEWAY_ARN>", gateway["gatewayArn"])
        files[f"policy-{cedar.stem}.json"] = {"cedar": {"statement": statement}}
    update = {"gatewayIdentifier": gateway["gatewayId"], **{
        k: gateway[k] for k in ("name", "description", "roleArn", "protocolType", "protocolConfiguration",
                                "authorizerType", "authorizerConfiguration", "interceptorConfigurations",
                                "exceptionLevel") if k in gateway}}
    for mode in ("LOG_ONLY", "ENFORCE"):
        files[f"gateway-policy-{mode.lower().replace('_', '-')}.json"] = {
            **update, "policyEngineConfiguration": {"arn": engines[0], "mode": mode}}


if __name__ == "__main__":
    main()
