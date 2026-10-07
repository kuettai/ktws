# D3 M04 — Evaluation (90m)

## Objectives
- Write test questions the way you write a report: question, expected tool, expected answer from your own SQL.
- Score a run on tool choice, parameters and answer accuracy.
- Change one thing, run again, and decide from the numbers whether it helped.

Everything is in [evals/](../evals/) ([README](../evals/README.md) has the full field reference). Work in pairs.

## Steps
1. **Set up (5m).** From the workshop folder (`cd ..` if you are still in `agent/`):

    ```bash
    cd evals && uv sync
    uv run pytest -q                        # the scorer's own tests, no AWS
    ```

    ```powershell
    cd evals; uv sync
    uv run pytest -q                        # the scorer's own tests, no AWS
    ```

2. **Read the starter set (10m).** Open `questions.yaml`. 18 questions in 6 categories:

    | Category | IDs | What it checks |
    |---|---|---|
    | `redshift` | q01–q08 | One history tool, right dates and branch |
    | `ops` | q09–q11 | One live tool (stock, today's sales) |
    | `multi_step` | q12–q14 | Several tools in a row (the M02 question is q12) |
    | `scope` | q15 | Manager 12 asks for branch 5: agent must say it can't |
    | `write` | q16–q17 | Refund / transfer: agent must stop for approval |
    | `clarify` | q18 | "How are sales?": agent must ask back, not guess |

    For each, find `expected_tools`, `expected_params`, `answer_type` and where the expected answer comes from (`expected_answer`, `ground_truth_sql` or `ground_truth_http`).

3. **Write your own (25m).** Each pair adds 3–5 questions from real requests (the questions you listed in Day 1 M00, your own report queries), so the set reaches 20+. Cover at least: a branch given by name, a multi-step question, and one the persona is not allowed to see.
    - Write the SQL you would write by hand against the `mcp` views ([data dictionary](../docs/data-dictionary.md)). Run it in the Redshift query editor first (console: **Amazon Redshift → Query editor v2**, connect to workgroup `rst-workshop`, database `dev`): the answer is the first column of the first row.
    - Use the date placeholders (`{month_start}`, `{month_end}`, `{week_start}`, `{end}`, `{month_label}`), not fixed dates.
    - Check the filled-in SQL: `uv run python compute_ground_truth.py --print-sql`.
4. **Compute expected answers (10m).** Live questions read the mock API, so pin its clock first:

    ```bash
    cd ..                                           # back to the workshop folder
    docker compose stop mock-api                    # if it is running in Docker
    (cd mock-api && MOCK_NOW=2026-10-01T14:30:00 MOCK_API_KEY=local-dev-key \
        uv run uvicorn app.main:app --port 8080 &)
    cd evals
    export AWS_PROFILE=<your profile> AWS_REGION=<region> REDSHIFT_WORKGROUP=rst-workshop REDSHIFT_DATABASE=dev
    export OPS_API_BASE_URL=http://localhost:8080 OPS_API_KEY=local-dev-key
    export SEED_END_DATE=<seedEndDate from RstDataStack>
    uv run python compute_ground_truth.py           # writes ground_truth.json
    ```

    ```powershell
    cd ..                                           # back to the workshop folder
    docker compose stop mock-api                    # if it is running in Docker
    $env:MOCK_NOW = "2026-10-01T14:30:00"; $env:MOCK_API_KEY = "local-dev-key"
    Start-Process -NoNewWindow -WorkingDirectory mock-api -FilePath uv `
        -ArgumentList "run", "uvicorn", "app.main:app", "--port", "8080"   # runs in the background
    cd evals
    $env:AWS_PROFILE = "<your profile>"; $env:AWS_REGION = "<region>"; $env:REDSHIFT_WORKGROUP = "rst-workshop"; $env:REDSHIFT_DATABASE = "dev"
    $env:OPS_API_BASE_URL = "http://localhost:8080"; $env:OPS_API_KEY = "local-dev-key"
    $env:SEED_END_DATE = "<seedEndDate from RstDataStack>"
    uv run python compute_ground_truth.py           # writes ground_truth.json
    ```

    - `SEED_END_DATE` is the last day of the mock history: the `seedEndDate` your instructor used for `RstDataStack` (the default is `2026-09-30`, in `infra/cdk.json`). Ask if unsure.
    - Keep the pinned mock API running for steps 5–7: the local MCP server reads it. When you finish the module, stop it and start the Docker one again: `pkill -f "app.main:app --port 8080"` then `docker compose start mock-api` (PowerShell: `Get-CimInstance Win32_Process -Filter "CommandLine like '%app.main:app%'" | ForEach-Object { Stop-Process -Id $_.ProcessId }`, then `docker compose start mock-api`).

5. **Baseline run (15m).**

    ```bash
    uv run python run_evals.py --label "baseline"
    uv run python score.py results/latest.json
    ```

    ```powershell
    uv run python run_evals.py --label "baseline"
    uv run python score.py results/latest.json
    ```
    If the starter set already scores close to 100%, good: your own questions from step 3 are where the failures (and the learning) are. Each question gets a fresh agent, signed in as its persona. Every write action is **declined**, so a run never changes data. Each run is kept in `results/<time>.json`; `latest.json` is the most recent.

6. **Read the scorecard (10m).** Go row by row, then look at the four totals.

    | Column | FAIL usually means | First thing to try |
    |---|---|---|
    | `tools` | Wrong or missing tool | Tool name/description; system prompt rule 3 |
    | `params` | Right tool, wrong dates/branch/category | Parameter text in the docstring (`Args:`), allowed values |
    | `answer` (tools and params PASS) | Agent summarised wrongly, **or your ground truth is wrong** | Check your SQL first |
    | `-` | Not scored (no expected answer yet, or alternative tool used) | Compute ground truth |

    The `note` column says what differed, e.g. `get_peak_hours.day_type='all', expected 'weekend'`.

7. **Change one thing, run again (15m).** Pick the most common failure. Change **one** thing, for example the docstring of the tool it got wrong in `solutions/mcp-server/tools/redshift_tools.py`. To test your own Day 1 server instead, set `MCP_SERVER_DIR=../mcp-server` (PowerShell: `$env:MCP_SERVER_DIR = "../mcp-server"`).

    ```bash
    uv run python run_evals.py --label "clearer get_waste_by_item description"
    uv run python score.py results/latest.json
    ```

    ```powershell
    uv run python run_evals.py --label "clearer get_waste_by_item description"
    uv run python score.py results/latest.json
    ```
    Re-run just the failures while you iterate (`--only q06,q13`), but compare full runs.

## Checkpoint
Each pair has a scored question set and one before/after comparison of a change.

## Discussion
- Did the change fix one question and break another? That is why you score the whole set.
- Runs are not fully repeatable (Sonnet 5.5 does not accept `temperature`; `BEDROCK_TEMPERATURE=0` works only with older models such as Sonnet 4.6). Run twice before trusting a 1-question difference.
- Text matching is strict on purpose. `score.py --judge` re-grades failed text answers with a model (calls Bedrock). When is a model a fair judge, and when should a number decide?
- Who owns `questions.yaml` after the workshop? (Analysts: it encodes what "right" means.) Add a question for every bug report.
- AgentCore has a managed option (`agentcore eval`, built-in and custom evaluators on recorded sessions). Not used today; worth a look once the question set exists.
