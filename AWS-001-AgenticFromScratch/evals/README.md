# Testing the agent (Day 3, Lab 4)

An agent is only as good as the tools it picks and the numbers it reports. This folder tests both with a fixed set of questions, so you can change a tool description or the system prompt and see whether the agent got better or worse.

| File | What it is |
|---|---|
| `questions.yaml` | 18 questions: expected tools, parameters and answer for each |
| `compute_ground_truth.py` | Works out the expected answers from this account's data. Saves `ground_truth.json` |
| `run_evals.py` | Asks the agent every question, records each tool call. Saves `results/<time>.json` |
| `score.py` | Scores a run: tool choice, parameters, answer accuracy |
| `evalset.py` | Loads the questions and fills in the dates |

## The loop

```text
write questions --> compute expected answers --> run --> score --> change ONE thing --> run --> score
```

```bash
uv sync
uv run pytest                                       # the scorer's own tests, no AWS needed

# 1. Expected answers for this account (once). Redshift + the mock Operations API
export AWS_PROFILE=workshop AWS_REGION=us-east-1 REDSHIFT_WORKGROUP=rst-workshop REDSHIFT_DATABASE=dev
export OPS_API_BASE_URL=http://localhost:8080 OPS_API_KEY=local-dev-key
uv run python compute_ground_truth.py

# 2. Run and score. Needs Bedrock model access
uv run python run_evals.py --label "baseline"
uv run python score.py results/latest.json

# 3. Change one thing (a tool description, the system prompt, the model), then run and score again
uv run python run_evals.py --label "clearer get_waste_by_item description"
uv run python score.py results/latest.json
```

```powershell
uv sync
uv run pytest                                       # the scorer's own tests, no AWS needed

# 1. Expected answers for this account (once). Redshift + the mock Operations API
$env:AWS_PROFILE = "workshop"; $env:AWS_REGION = "us-east-1"; $env:REDSHIFT_WORKGROUP = "rst-workshop"; $env:REDSHIFT_DATABASE = "dev"
$env:OPS_API_BASE_URL = "http://localhost:8080"; $env:OPS_API_KEY = "local-dev-key"
uv run python compute_ground_truth.py

# 2. Run and score. Needs Bedrock model access
uv run python run_evals.py --label "baseline"
uv run python score.py results/latest.json

# 3. Change one thing (a tool description, the system prompt, the model), then run and score again
uv run python run_evals.py --label "clearer get_waste_by_item description"
uv run python score.py results/latest.json
```

The live questions (q10, q11) read today's numbers from the mock API. For the same answer in steps 1 and 2, start mock-api with a fixed time, for example `MOCK_NOW=2026-10-01T14:30:00`.

## Scorecard

```text
id    category    tools params answer result note
------------------------------------------------------------------------------------------
q01   redshift    PASS  PASS   PASS   PASS
q04   redshift    PASS  FAIL   PASS   FAIL   get_peak_hours.day_type='all', expected 'weekend'
q12   multi_step  FAIL   -     PASS   FAIL   missing get_current_stock|list_low_stock_items
q16   write       PASS  PASS   PASS   PASS
...
------------------------------------------------------------------------------------------
tool choice       94.4% (17/18)
parameters        93.8% (15/16)
answer accuracy   88.9% (16/18)
overall pass      83.3% (15/18)
```

- **tools**: the agent called the expected tools. `exact` means no other tools (apart from `allow_extra`), `subset` means at least these, and `ordered` means in this order.
- **params**: the first call to each expected tool used the expected values (`branch_id`, dates, `category` ...).
- **answer**:
    - number: an exact figure within tolerance
    - hour: an hour of day
    - text: the expected name appears in the answer
    - refusal: the agent says it is limited
    - clarify: the agent asks back instead of guessing
    - approval: see below
- `-` means not scored for that question. For example, the expected answer hasn't been computed yet, or an alternative tool was used, so its parameters weren't checked.

Text matching is strict on purpose. Add `--judge` to have a model re-grade failed text answers. This calls Bedrock and is off by default.

## Write actions never run

Every write action is **declined** during an evaluation run. A write question (q16 refund, q17 stock transfer) passes when the agent:

1. calls the right write tool with the right parameters,
2. was stopped for approval, and
3. tells the user the action was not carried out.

So running the tests never changes data.

## Personas

Each question is asked as a person:

| Persona | Role | Branch |
|---|---|---|
| `hq` | hq | any |
| `manager_branch_12` | manager | 12 |
| `manager_branch_5` | manager | 5 |
| `staff_branch_12` | staff | 12 |

- **Local runs** start the MCP server once per persona with `LOCAL_ROLE` / `LOCAL_BRANCH_ID`.
- **Remote runs** (`MCP_URL` set, for example AgentCore Gateway) need one token per persona, for example `MCP_TOKEN_HQ` and `MCP_TOKEN_MANAGER_BRANCH_12`. Get them by signing in as each test user with `scripts/get_token.py`.

Run the same questions against ECS, AgentCore Runtime and Gateway to compare them on equal terms.

## Writing your own questions

Add an entry to `questions.yaml` (the field reference is at the top of the file). Good questions come from real requests. Cover each of these:

- one obvious tool
- a branch given by name instead of ID
- several steps
- a question the user is not allowed to see
- a write action
- a vague request

To get the expected answer, write the SQL you would write by hand against the `mcp` views. That is the analyst's ground truth, and the agent has to match it.
