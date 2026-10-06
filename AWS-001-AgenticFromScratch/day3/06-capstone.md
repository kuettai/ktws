# D3 M06 — Capstone (45m)

> **Preview** — this module has not yet been tested end to end.

## Task (pairs)
Take one restaurant scenario (your Day 2 capstone, or one below) and deliver it as an agent: it plans, calls the tools, asks before changing data, and has a test score.

Suggested scenarios (same as [Day 2](../day2/06-capstone.md)):

1. **Weekend staffing:** peak hours on weekends vs weekdays for my branch, and today's sales so far.
2. **Waste reduction:** top waste items last month, current stock of each, then a stock transfer to a busier branch. Uses `request_stock_transfer` and the approval step.
3. **Delivery growth:** channel mix trend for a region, top delivery items, best branch to push delivery promotions.

## Steps
1. **Plan (5m).** Write the question as a manager would ask it. List the tools you expect, in order. Pick the persona (`manager_branch_12` is a good default).
2. **Build and run (20m).** Use the agent from M01–M03 (local: `uv run python -m rst_agent --role manager --branch 12`) or the Runtime agent from M05. Read the recorder trace: does the plan match yours? If not, fix a tool description or add a line to the system prompt, not the question.
3. **Test it (10m).** Add **5 questions** for your scenario to `evals/questions.yaml` with `category: capstone`: the main question, two variations, one the persona must not see, and (scenario 2) the write action with `answer_type: approval`. Compute ground truth and score them:

    ```bash
    uv run python compute_ground_truth.py
    uv run python run_evals.py --only <your ids> --label "capstone <pair name>"
    uv run python score.py results/latest.json
    ```

    ```powershell
    uv run python compute_ground_truth.py
    uv run python run_evals.py --only <your ids> --label "capstone <pair name>"
    uv run python score.py results/latest.json
    ```

4. **Demo (10m).** 2 minutes each, as many pairs as time allows. Others post their scorecard in the workshop channel.

## Requirements
- Agent answers the main question end to end, with the trace shown.
- At least one approval moment (scenario 2), or a sentence on which action in your scenario would need one and why.
- Branch scoping correct for the manager persona.
- 5 scored questions, with the scorecard.

## Presentation
Question, the agent's plan (recorder trace), the score, and one thing the tests caught that you would have missed by eye.
