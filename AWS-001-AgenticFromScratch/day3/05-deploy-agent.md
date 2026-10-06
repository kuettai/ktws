# D3 M05 — Deploy the agent (45m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Host the M01–M03 agent on AgentCore Runtime, using the Day 2 Gateway as its tool source.
- Keep the user's identity end to end: Runtime checks the sign-in, Gateway and the tools still see the real user.
- Keep the approval step when there is no terminal to type "y" into.
- Trace one run in Observability and compare test scores with the local agent.

## What changes from M01–M03
Nothing in `rst_agent`. One new file, [solutions/agent/runtime_app.py](../solutions/agent/runtime_app.py), wraps it for Runtime:

| Local chat (`python -m rst_agent`) | Runtime (`runtime_app.py`) |
|---|---|
| Starts the MCP server locally, or `MCP_URL` | `MCP_URL` = Day 2 Gateway URL |
| You are the user (`--role`, `--branch`) | User comes from the bearer token, forwarded to Gateway |
| `console_approver` asks "Approve? [y/N]" | Agent pauses, returns `needs_approval`; next call sends `{"approve": true\|false}` |
| One conversation per process | One agent per Runtime session ID |

## Steps
1. **Read the entrypoint (5m).** Open `runtime_app.py`: the payloads it accepts, the responses, and how `handle()` keeps one agent per session. Run its tests: `cd solutions/agent && uv run pytest -q tests/test_runtime_app.py` (PowerShell: `cd solutions/agent; uv run pytest -q tests/test_runtime_app.py`).
2. **Configure (10m).** Install the toolkit (`uv tool install bedrock-agentcore-starter-toolkit`), then:

    ```bash
    cd solutions/agent
    agentcore configure -e runtime_app.py --disable-memory \
      --authorizer-config '{"customJWTAuthorizer": {"discoveryUrl": "https://cognito-idp.<region>.amazonaws.com/<user_pool_id>/.well-known/openid-configuration", "allowedClients": ["<kiro-user client id>"]}}' \
      --request-header-allowlist Authorization
    ```

    ```powershell
    # Windows PowerShell 5.1 needs \" inside JSON arguments. In PowerShell 7.3+, use the JSON exactly as in the bash tab.
    cd solutions/agent
    agentcore configure -e runtime_app.py --disable-memory `
      --authorizer-config '{\"customJWTAuthorizer\": {\"discoveryUrl\": \"https://cognito-idp.<region>.amazonaws.com/<user_pool_id>/.well-known/openid-configuration\", \"allowedClients\": [\"<kiro-user client id>\"]}}' `
      --request-header-allowlist Authorization
    ```

    - Accept the default to create an execution role (it needs Bedrock model access and CloudWatch Logs; no Redshift access, because data goes through Gateway).
    - `--request-header-allowlist Authorization` lets the agent forward the caller's token to Gateway.
3. **Deploy (10m).**

    ```bash
    agentcore deploy --env MCP_URL=<Day 2 Gateway MCP URL> \
                     --env BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-5-5
    agentcore status
    ```

    ```powershell
    agentcore deploy --env MCP_URL=<Day 2 Gateway MCP URL> `
                     --env BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-5-5
    agentcore status
    ```

4. **Invoke as a branch manager (10m).**

    ```bash
    export TOKEN=$(python3 ../../scripts/get_token.py --domain https://<prefix>.auth.<region>.amazoncognito.com \
        --client-id <kiro-user client id>)              # sign in as manager_branch_12
    export SID=$(uuidgen)                               # session IDs need 33+ characters
    agentcore invoke '{"prompt": "What were my best sellers last month? Am I low on any of them right now?"}' \
        --session-id $SID --bearer-token $TOKEN
    ```

    ```powershell
    $env:TOKEN = (py ..\..\scripts\get_token.py --domain https://<prefix>.auth.<region>.amazoncognito.com `
        --client-id <kiro-user client id>)              # sign in as manager_branch_12
    $env:SID = [guid]::NewGuid().ToString()             # session IDs need 33+ characters
    agentcore invoke '{\"prompt\": \"What were my best sellers last month? Am I low on any of them right now?\"}' `
        --session-id $env:SID --bearer-token $env:TOKEN
    ```
    The response has `answer` and `tool_calls`, the same steps the recorder printed locally. Then the approval path:

    ```bash
    agentcore invoke '{"prompt": "Refund order 1001 at my branch, the food was cold"}' --session-id $SID --bearer-token $TOKEN
    # -> "status": "needs_approval", "pending": [{"tool": "...issue_refund", "input": {...}}]
    agentcore invoke '{"approve": false}' --session-id $SID --bearer-token $TOKEN
    ```

    ```powershell
    agentcore invoke '{\"prompt\": \"Refund order 1001 at my branch, the food was cold\"}' --session-id $env:SID --bearer-token $env:TOKEN
    # -> "status": "needs_approval", "pending": [{"tool": "...issue_refund", "input": {...}}]
    agentcore invoke '{\"approve\": false}' --session-id $env:SID --bearer-token $env:TOKEN
    ```
    Sign in as `staff_branch_12` and approve a refund: the Day 2 Cedar policy still denies it. A person approves; policy enforces.

5. **Trace it (5m).** CloudWatch → **GenAI Observability** → pick the session: prompt → model calls → each Gateway tool call → answer. The Runtime log group is `/aws/bedrock-agentcore/runtimes/<agent name>-*-DEFAULT`. `agentcore invoke` also prints a log command; `agentcore obs` lists and shows traces from the terminal.
6. **Compare scores (5m).** Run the M04 set with the agent's tools coming from Gateway instead of the local server:

    ```bash
    cd ../../evals
    export MCP_URL=<Day 2 Gateway MCP URL>
    export MCP_TOKEN_HQ=... MCP_TOKEN_MANAGER_BRANCH_12=... MCP_TOKEN_MANAGER_BRANCH_5=... MCP_TOKEN_STAFF_BRANCH_12=...
    uv run python run_evals.py --label "via Gateway"
    uv run python score.py results/latest.json
    ```

    ```powershell
    cd ..\..\evals
    $env:MCP_URL = "<Day 2 Gateway MCP URL>"
    $env:MCP_TOKEN_HQ = "..."; $env:MCP_TOKEN_MANAGER_BRANCH_12 = "..."
    $env:MCP_TOKEN_MANAGER_BRANCH_5 = "..."; $env:MCP_TOKEN_STAFF_BRANCH_12 = "..."
    uv run python run_evals.py --label "via Gateway"
    uv run python score.py results/latest.json
    ```
    Then ask the Runtime-hosted agent 2–3 of the same questions with `agentcore invoke` and check its `tool_calls` against the run. Same model, prompt and tools should give the same tool choices.

## Checkpoint
Same question answered by the Runtime-hosted agent; trace visible.

## Discussion
- Gateway names tools `<target>___<tool>`. Did the scores change because of tool names, descriptions (OpenAPI `summary` vs our docstrings) or the model? How do you tell?
- What did Runtime take away (process, scaling, sign-in check), and what stayed yours (prompt, tools, approval rule, tests)?
- Where would the approval prompt live for real users: Quick, a web app, a ticket? `needs_approval` is the hook for any of them.

## Instructor notes (verify in dry-run)
- CLI flags above match `bedrock-agentcore-starter-toolkit` 0.3.13 help text, not yet run against AWS. Check the `--authorizer-config` JSON shape and that `Authorization` reaches the container with a JWT authorizer.
- Check that deployment packages `src/rst_agent` (use `--requirements-file` / container deployment if it is not picked up).
- Gateway tool names are prefixed `<target>___`. `ApprovalHook` (via `is_write_tool`) and `score.py` already match on the part after `___`, and `WRITE_TOOLS` includes the OpenAPI operation IDs `issueRefund` / `requestStockTransfer`. Covered by `test_write_tools_behind_gateway_still_need_approval`. Still run q16/q17 through the real Gateway before the event to confirm the names it produces.
- Clean up after the lab: `agentcore destroy`.

## Learn more
- Runtime + Gateway pattern adapted from *Building with Amazon Bedrock* (Workshop Studio), AgentCore labs "Runtime: Deploy" and "Gateway + Runtime".
- Observability walkthrough adapted from *Building an Enterprise Agentic AI Platform on Amazon Bedrock AgentCore*, Module 4 "Observe the Platform".
- [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html), [Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html).
