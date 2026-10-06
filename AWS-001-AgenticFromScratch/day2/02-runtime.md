# D2 M02 — AgentCore Runtime (75m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Deploy the Day 1 MCP server to AgentCore Runtime with minimal change.
- Configure inbound JWT auth reusing Day 1 Cognito.
- Connect Kiro and Quick to the Runtime endpoint.

## Code changes from Day 1
- Already compliant if M04 done: `host="0.0.0.0"`, `port=8000`, `stateless_http=True`, path `/mcp`.
- Runtime validates the JWT before the request reaches the container. Keep `OIDC_*` env vars set anyway: the server re-validates (defense in depth) and `current_caller()` still needs the claims for branch scoping. Requires Runtime to forward the `Authorization` header to the container — verify the header allowlist setting in current docs.
- Execution role: reuse `rst-mcp-task-<region>` from `RstDataStack` (already trusts `bedrock-agentcore.amazonaws.com` and is mapped to `mcp_reader`).

## Steps
1. Install toolkit: `pip install bedrock-agentcore-starter-toolkit` (verify current CLI name/commands).
2. Configure:

    ```bash
    agentcore configure -e server.py --protocol MCP
    ```

    ```powershell
    agentcore configure -e server.py --protocol MCP
    ```
    When prompted for OAuth: discovery URL
    `https://cognito-idp.<region>.amazonaws.com/<user_pool_id>/.well-known/openid-configuration`,
    allowed clients = `kiro-user`, `quick-user`, `quick-s2s` client IDs.

3. Execution role: `rst-mcp-task-<region>`. Ops API / Promo service must be reachable from Runtime (VPC networking mode, or expose via Gateway in M03).
4. Deploy: `agentcore launch`.
5. Endpoint:

    ```text
    https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<url-encoded-runtime-arn>/invocations?qualifier=DEFAULT
    ```

6. Kiro: new `mcpServers` entry with that URL + `Authorization: Bearer ${RST_MCP_TOKEN}`.
7. Quick: new MCP integration pointing at Runtime endpoint, user auth with `quick-user`.

## Checkpoint
Same M07 demo questions work against Runtime. Branch scoping still enforced.

## Discussion
- What disappeared: ALB, ACM, ECS service, autoscaling config, JWT middleware.
- What remained: our code, our SQL, our tool descriptions — the analyst-owned part.
