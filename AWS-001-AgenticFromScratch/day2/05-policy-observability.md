# D2 M05 — Policy + Observability (60m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Expose write tools safely with Cedar policies.
- Trace a tool call end to end.

## Part A — Policy (35m)
1. Enable write operations from OpenAPI target: `issueRefund`, `requestStockTransfer`.
2. Add Cognito scope `rst-mcp/write`, granted only to managers (pre-token trigger).
3. Create policy (Cedar) on the Gateway, e.g.:
    - `issueRefund` permitted only when caller role = `manager` and caller `branch_id` = request `branchId`.
    - `requestStockTransfer` permitted for `manager` and `hq`.
    - Default deny for other write tools.
    (Exact Cedar entity/attribute names: take from current AgentCore Policy docs during prep.)

4. Test in Quick:
    - `staff_branch_12`: "Refund order 1234" → denied.
    - `manager_branch_12`: refund at branch 12 → allowed; at branch 5 → denied.

## Part B — Observability (25m)
1. Open CloudWatch GenAI observability dashboard.
2. Find the trace for the refund call: Gateway → policy decision → target → response.
3. Find the slowest Redshift tool call. Discuss: add `LIMIT`, materialized view?

## Checkpoint
Policy blocks/permits as expected; trace visible for each case.

## Discussion
- Day 1 equivalent would be hand-written `if role != 'manager'` in each tool. Central policy = auditable, reviewable by non-developers.
