# D3 M01 — First Agent (60m)

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
1. **Set up (10m).** From the workshop folder:

    ```bash
    cp solutions/mcp-server/.env.example solutions/mcp-server/.env   # then set AWS_PROFILE in it
    docker compose up -d                       # mock Ops API + Promotions service (Finch: finch compose up -d)
    cd agent && uv sync
    uv run pytest tests/test_lab1_recorder.py  # fails now: that is the TODO
    ```

    ```powershell
    Copy-Item solutions\mcp-server\.env.example solutions\mcp-server\.env   # then set AWS_PROFILE in it
    docker compose up -d                       # mock Ops API + Promotions service (Finch: finch compose up -d)
    cd agent; uv sync
    uv run pytest tests/test_lab1_recorder.py  # fails now: that is the TODO
    ```

    The agent starts the reference MCP server (`solutions/mcp-server`) on your laptop, which reads its Redshift and Ops API settings from that `.env`. Open it and set `AWS_PROFILE` to your profile, as for `mcp-server/.env` on Day 1. Expected from `pytest`: `3 failed, 2 passed`.

2. **Read the agent (10m).** Open `agent/src/rst_agent/agent.py` with the [primer checklist](../prework/python-reading-primer.md#checklist-reviewing-kiros-code) in mind.
    - `SYSTEM_PROMPT`: the house rules. Plan first, a tool for every number, which tools are history and which are live, ask if unclear.
    - `build_agent()`: model + tools + system prompt + hooks. Note that `ApprovalHook` is always installed (M03).
    - Where are the tools defined? Not here. They come from the MCP server: `__main__.py` asks for them with `all_tools()` from `connections.py`, which reads the whole tool list.

3. **First run (10m).**

    ```bash
    export AWS_PROFILE=<your profile> AWS_REGION=<workshop region>   # the profile from prework, often workshop
    uv run python -m rst_agent --role manager --branch 12
    ```

    ```powershell
    $env:AWS_PROFILE = "<your profile>"; $env:AWS_REGION = "<workshop region>"   # the profile from prework, often workshop
    uv run python -m rst_agent --role manager --branch 12
    ```
    Ask: *What are my best sellers this month?* It answers, but you can't see how. That's the gap. (The mock history ends the day before the workshop. If "this month" has only a few days, the agent may say so and offer last month instead.)

4. **Recorder with Kiro (20m).** Open `agent/src/rst_agent/hooks.py`, `ToolCallRecorder`. Prompt Kiro with:
    > Complete the TODOs in `ToolCallRecorder._before` and `_after` in `agent/src/rst_agent/hooks.py`. Follow the comments exactly and make `agent/tests/test_lab1_recorder.py` pass. Don't change the tests.

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
