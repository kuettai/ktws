# D3 M02 — Multi-step Reasoning (45m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Answer one question that needs Redshift and live API tools together, in one run.
- Read the agent's plan from the recorder.
- Diagnose the common failures (wrong tool, extra or repeated calls, early stop) and fix them with tool descriptions or the system prompt.

## Steps
1. **The combined question (10m).** As `manager_branch_12`:

    ```bash
    uv run python -m rst_agent --role manager --branch 12
    ```

    ```powershell
    uv run python -m rst_agent --role manager --branch 12
    ```
    > What are my top 3 items this month, am I low on any of them right now, and how much of them did I waste last month?

    Expected shape (yours may differ):

    ```text
    [step 1] calling get_top_items {"branch_id": 12, "start_date": "2026-10-01", "end_date": ..., "top_n": 3}
    [step 2] calling get_current_stock {"branch_id": 12}
    [step 3] calling get_waste_by_item {"branch_id": 12, "start_date": "2026-09-01", "end_date": "2026-09-30"}
    ```
    Review the plan, check:

    - Did it resolve "this month" and "last month" to exact dates, and state them?
    - History from Redshift (`get_top_items`, `get_waste_by_item`), "right now" from the Ops API (`get_current_stock`)?
    - Every number in the answer appears in a tool result? (System prompt rule 2: never guess.)

2. **Break it on purpose (20m).** Pairs pick two, observe in the recorder, then fix.

    | Failure | How to cause it | What you see | Fix |
    |---|---|---|---|
    | Wrong tool | Ask *how much chicken is left at branch 12?* after weakening the `get_current_stock` docstring (e.g. "Returns inventory data") in your own `mcp-server/` with `MCP_SERVER_DIR=../mcp-server` (PowerShell: `$env:MCP_SERVER_DIR = "../mcp-server"`) | Picks a Redshift tool, or asks you | Restore a description that says **live, today** |
    | Guessing | Remove rule 2 from `SYSTEM_PROMPT` and ask about a branch name without an ID | Invents a branch ID or skips `find_branch` | Restore rule 2 and rule 4 |
    | Too many calls | *Compare every branch's waste last month* as `--role hq` | One `get_waste_by_item` per branch, 30+ steps | Use `get_top_branches`; or add a step limit (below) |
    | Early stop | Vague question: *how are we doing?* | Asks a clarifying question, no tools | Correct per rule 8. Discuss: is this a failure? |

    Prompt Kiro with (for a description fix):
    > Improve the docstring of `get_current_stock` following `kiro/steering/mcp-tool-design.md`. Make clear it is live, today-only stock, and when to use it instead of the Redshift tools.

    Review, check: only the docstring changed; it says when to use it and when not to; parameter examples kept.

3. **Step limit (optional, 10m).** Strands has no per-question tool budget in this agent. Prompt Kiro with:
    > Add a `max_tool_calls` option to `ToolCallRecorder` in `src/rst_agent/hooks.py`. When the limit is reached, set `event.cancel_tool` with a message telling the model to stop calling tools and answer with what it has. Add a test with the scripted model in `tests/fakes.py`.

    Review, check: the count resets with `reset()`; a cancelled call still shows as `cancelled` in the trace; existing tests still pass.

4. **Debrief (5m).** Which fix worked best: tool description, system prompt or limit? M04 measures this instead of eyeballing it.

## Checkpoint
The combined question (top sellers → current stock → last month's waste) answered in one run, with the plan visible in the recorder.

## Instructor notes
- Timing: 45m = 10 + 20 + 10 + 5. Skip step 3 if behind.
- Model behaviour varies between runs. That's a point for M04: one run proves nothing.
- Tool descriptions are analyst-owned (Day 1 teaching thread 3). The agent makes the cost of a weak description visible.
