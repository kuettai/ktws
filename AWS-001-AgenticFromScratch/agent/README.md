# Restaurant agent (starter, Day 3)

A branch analyst agent built with [Strands Agents](https://strandsagents.com/). It already connects to the workshop MCP server and answers questions. Two pieces are missing, and you add them with Kiro:

| Lab | File | TODO |
|---|---|---|
| Lab 1 | `src/rst_agent/hooks.py` | `ToolCallRecorder`: show each tool call as a numbered step |
| Lab 3 | `src/rst_agent/hooks.py` | `ApprovalHook`: a person approves `issue_refund` and `request_stock_transfer` before they run |

The tests in `tests/` describe the expected behaviour. They use a scripted model and fake tools, so they need no AWS access. At the start, the recorder and approval tests fail. When all tests pass, the lab is done.

```bash
uv sync
uv run pytest tests/test_lab1_recorder.py       # Lab 1 checkpoint
uv run pytest tests/test_lab3_approval.py       # Lab 3 checkpoint

export AWS_REGION=us-east-1                # Bedrock model access needed from here
uv run python -m rst_agent                      # chat as an HQ user
uv run python -m rst_agent --role manager --branch 12
```

```powershell
uv sync
uv run pytest tests/test_lab1_recorder.py       # Lab 1 checkpoint
uv run pytest tests/test_lab3_approval.py       # Lab 3 checkpoint

$env:AWS_REGION = "us-east-1"                   # Bedrock model access needed from here
uv run python -m rst_agent                      # chat as an HQ user
uv run python -m rst_agent --role manager --branch 12
```

By default the agent starts the reference server in `solutions/mcp-server`, which has every tool including the write tools. To use the server you built on Day 1, run `export MCP_SERVER_DIR=../mcp-server` (PowerShell: `$env:MCP_SERVER_DIR = "../mcp-server"`). To use a remote server, set `MCP_URL` and `MCP_TOKEN`.

Review what Kiro writes before you accept it. In `ApprovalHook`, check:

- Only the tools in `WRITE_TOOLS` ask for approval, and every one of them does.
- Anything other than an explicit approval counts as declined.
- A declined call is cancelled, and the message tells the model not to retry.

Stuck? The finished version is in `solutions/agent/`.
