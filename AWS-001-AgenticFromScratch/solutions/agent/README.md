# Restaurant agent (reference solution)

A branch analyst agent built with [Strands Agents](https://strandsagents.com/). It uses the tools on the workshop MCP server, shows every tool call as a numbered step, and stops for a person to approve anything that changes data.

| File | What it does |
|---|---|
| `src/rst_agent/agent.py` | `build_agent()`: model, system prompt, hooks. `ask()`: runs one question and handles approval pauses |
| `src/rst_agent/hooks.py` | `ToolCallRecorder` (step-by-step trace) and `ApprovalHook` (a person approves write tools) |
| `src/rst_agent/connections.py` | Connect to the MCP server: local (stdio) or remote (Streamable HTTP + bearer token) |
| `src/rst_agent/__main__.py` | Interactive chat in the terminal |
| `tests/` | Tests with a scripted model and fake tools. No AWS or Bedrock calls |

## Run

```bash
uv sync
uv run pytest                                     # no AWS needed

# Chat. Needs Bedrock model access in AWS_REGION, plus the data sources the MCP server uses
export AWS_PROFILE=workshop AWS_REGION=us-east-1
uv run python -m rst_agent                        # local server, HQ user
uv run python -m rst_agent --role manager --branch 12

# Remote server (ECS, AgentCore Runtime or Gateway)
export MCP_URL=https://xxxx.cloudfront.net/mcp
export MCP_TOKEN=$(python3 ../../scripts/get_token.py --domain https://<prefix>.auth.<region>.amazoncognito.com \
    --client-id <kiro-user client id>)       # signs you in as a test user, e.g. manager_branch_12
uv run python -m rst_agent
```

```powershell
uv sync
uv run pytest                                     # no AWS needed

# Chat. Needs Bedrock model access in AWS_REGION, plus the data sources the MCP server uses
$env:AWS_PROFILE = "workshop"; $env:AWS_REGION = "us-east-1"
uv run python -m rst_agent                        # local server, HQ user
uv run python -m rst_agent --role manager --branch 12

# Remote server (ECS, AgentCore Runtime or Gateway)
$env:MCP_URL = "https://xxxx.cloudfront.net/mcp"
$env:MCP_TOKEN = (py ..\..\scripts\get_token.py --domain https://<prefix>.auth.<region>.amazoncognito.com `
    --client-id <kiro-user client id>)       # signs you in as a test user, e.g. manager_branch_12
uv run python -m rst_agent
```

Settings:

| Variable | Default | Meaning |
|---|---|---|
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-sonnet-5-5` | Any Bedrock model with tool use. Use an `apac.` or `us.` profile if `global.` is not enabled |
| `MCP_URL` / `MCP_TOKEN` | unset | Remote server. Unset = start `solutions/mcp-server` locally |
| `MCP_SERVER_DIR` | `solutions/mcp-server` | Local server folder. Point it at your own `mcp-server/` |

The local server reads its own settings (Redshift, Operations API) from the environment. See `solutions/mcp-server/.env.example`.

## What you see

```text
you> What is my best seller this month and am I low on it?
[step 1] calling get_top_items {"branch_id": 12, "start_date": "2026-09-01", "end_date": "2026-09-30", "top_n": 1}
[step 1] get_top_items success: {"rows": [{"item_name": "Spicy Chicken Burger", ...
[step 2] calling get_current_stock {"branch_id": 12, "item_id": 3}
[step 2] get_current_stock success: {"on_hand": 14, "is_low_stock": true, ...

agent> Spicy Chicken Burger (1,240 sold). You have 14 left, which is below the reorder level.
```

## How approval works

`issue_refund` and `request_stock_transfer` are in `WRITE_TOOLS`. Before either runs, `ApprovalHook` raises a Strands **interrupt**:

- **With an approver** (the terminal chat uses `console_approver`): the person is asked straight away. Yes runs the tool. No cancels it, and the model is told it was declined.
- **Without one** (a web app, AgentCore Runtime): the agent stops with `stop_reason == "interrupt"` and returns the pending action. Show it to a person, then resume:

    ```python
    result = agent("Refund my most recent completed order at branch 12, the food was cold")
    if result.stop_reason == "interrupt":
        pending = result.interrupts[0]          # pending.reason = {"tool", "input", "message"}
        answer = "approved" if person_says_yes(pending.reason) else "declined"
        result = agent([{"interruptResponse": {"interruptId": pending.id, "response": answer}}])
    ```

    `ask(agent, question, approver)` does this loop for you. With no approver, it declines.

Approval sits on top of the server's own checks, not instead of them. The MCP server still refuses a refund at another manager's branch, and on AgentCore Gateway a Cedar policy decides what is allowed at all. A person approves; the server and policy enforce.
