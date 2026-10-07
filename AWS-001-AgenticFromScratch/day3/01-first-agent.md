# D3 M01 — First Agent (60m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Run a Strands agent on the Day 1 MCP server tools.
- Add a tool-call recorder with Kiro so every step is printed.
- Review hook code against the tests.

## Pre-built
- `agent/` (starter): `src/rst_agent/agent.py` (`build_agent()`, `ask()`, system prompt), `connections.py` (MCP connection), `__main__.py` (terminal chat). See `agent/README.md`.
- `agent/tests/`: tests with a scripted model and fake tools. No AWS needed.
- Reference answer: `solutions/agent/`.
- By default the agent starts `solutions/mcp-server` locally over stdio. To use your own Day 1 server: `export MCP_SERVER_DIR=../mcp-server` (PowerShell: `$env:MCP_SERVER_DIR = "../mcp-server"`).

## Steps
1. **Set up (10m).**

    ```bash
    docker compose up -d                       # workshop folder: mock Ops API + Promotions service
    cd agent && uv sync
    uv run pytest tests/test_lab1_recorder.py  # fails now: that is the TODO
    ```

    ```powershell
    docker compose up -d                       # workshop folder: mock Ops API + Promotions service
    cd agent; uv sync
    uv run pytest tests/test_lab1_recorder.py  # fails now: that is the TODO
    ```
    The local MCP server reads Redshift and Ops API settings from `solutions/mcp-server/.env` (copy `.env.example`).

2. **Read the agent (10m).** Open `src/rst_agent/agent.py` with the primer checklist in mind.
    - `SYSTEM_PROMPT`: the house rules. Plan first, a tool for every number, which tools are history and which are live, ask if unclear.
    - `build_agent()`: model + tools + system prompt + hooks. Note that `ApprovalHook` is always installed (M03).
    - Where are the tools defined? Not here. They come from the MCP server through `list_tools_sync()` in `__main__.py`.

3. **First run (10m).**

    ```bash
    export AWS_PROFILE=workshop AWS_REGION=<workshop region>
    uv run python -m rst_agent --role manager --branch 12
    ```

    ```powershell
    $env:AWS_PROFILE = "workshop"; $env:AWS_REGION = "<workshop region>"
    uv run python -m rst_agent --role manager --branch 12
    ```
    Ask: *What are my best sellers this month?* It answers, but you can't see how. That's the gap.

4. **Recorder with Kiro (20m).** Open `src/rst_agent/hooks.py`, `ToolCallRecorder`. Prompt Kiro with:
    > Complete the TODOs in `ToolCallRecorder._before` and `_after` in `src/rst_agent/hooks.py`. Follow the comments exactly and make `tests/test_lab1_recorder.py` pass. Don't change the tests.

    Review, check:

    - `_before` records `step`, `name`, `input`, `status="running"` and prints `[step N] calling <name> <input>`.
    - The same `toolUseId` is recorded only once (it comes back when the agent resumes after an approval pause in M03).
    - `_after` sets `cancelled` / `error` / the result's `status`, and doesn't crash when the result is an exception.
    - Only `hooks.py` changed.

    ```bash
    uv run pytest tests/test_lab1_recorder.py
    ```

    ```powershell
    uv run pytest tests/test_lab1_recorder.py
    ```

5. **See the loop (10m).** Run the chat again:

    ```text
    you> What are my best sellers at branch 12 this month?
    [step 1] calling get_top_items {"branch_id": 12, "start_date": "2026-10-01", ...}
    [step 1] get_top_items success: {"rows": [...
    ```
    Try and compare in pairs:

    - As `--role manager --branch 12`, ask about branch 5. What does the recorder show? (Read tools limit the data to your own branch and return a note.)
    - *Which branch is Hillcrest?* Does `find_branch` come first?

## Checkpoint
`uv run pytest tests/test_lab1_recorder.py` passes. The agent answers "best sellers at branch 12 this month" and the recorder shows each tool call with its parameters.

## Instructor notes
- Timing: 60m = 10 + 10 + 10 + 20 + 10.
- Bedrock model access must be enabled in the workshop accounts before the day. If `global.` profiles are off, set `BEDROCK_MODEL_ID` to an `apac.` or `us.` profile.
- Steps 1–4 need no Bedrock: the tests use a scripted model. If model access fails, keep going and demo step 5 from the instructor screen.
- Fast finishers: `uv run python -m rst_agent --role hq` and ask a chain-wide question (`get_top_branches`).

## Learn more
- Hooks (`BeforeToolCallEvent`, `AfterToolCallEvent`) and the tool-call recorder idea are adapted from the *AWS Building with Amazon Bedrock* workshop ("Event hooks").
- Strands docs: strandsagents.com → User guide → Hooks.
