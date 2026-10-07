# D2 M06 — Capstone (60m)

## Task (pairs)
Pick a real analyst question set (the questions you listed in Day 1 M00, or one below). Deliver it end to end on AgentCore.

Suggested scenarios:

1. **Weekend staffing** — peak hours on weekends vs weekdays for my branch.
2. **Waste reduction** — top waste items, current stock, suggest transfer to busier branch (uses write tool + policy).
3. **Delivery growth** — channel mix trend for a region, top delivery items.

## Requirements
- At least one new SQL tool following `sample-queries.md` patterns (add a new pattern if needed, reviewed by instructor).
- Exposed through the Gateway, and used from Kiro (`rst-gateway`) with a manager's token.
- Branch scoping correct for a manager user. If the scenario changes data (scenario 2), a Gateway rule covers it.
- A trace of one of your tool calls from `aws/spans` (M05 Part B).

## Ship a new tool to the Gateway
1. Write and test the tool locally (Day 1 way: Kiro, `uv run pytest`, Inspector).
2. Copy the changed files into the Runtime project (`rstday2/app/RstMcp/`, as in M02 step 3), then `agentcore deploy -y` in `rstday2/`.
3. Tell the Gateway to read the server's tool list again:

    ```bash
    aws bedrock-agentcore-control list-gateway-targets --gateway-identifier $GATEWAY_ID --query "items[].[name,targetId]" --output text
    aws bedrock-agentcore-control synchronize-gateway-targets --gateway-identifier $GATEWAY_ID --target-id-list <RstMcp target id>
    ```

    ```powershell
    aws bedrock-agentcore-control list-gateway-targets --gateway-identifier $env:GATEWAY_ID --query "items[].[name,targetId]" --output text
    aws bedrock-agentcore-control synchronize-gateway-targets --gateway-identifier $env:GATEWAY_ID --target-id-list <RstMcp target id>
    ```

4. With the policy engine on ENFORCE, a new tool is allowed by `signed_in_users.cedar`. If it changes data, add a rule for it (M05).

## Next: agents on Day 3
No agent work today. Keep your capstone tools and Gateway endpoint: on Day 3 a Strands agent uses them as its tool source ([day3/05-deploy-agent.md](../day3/05-deploy-agent.md)), and your scenario can become the Day 3 capstone ([day3/06-capstone.md](../day3/06-capstone.md)).

## Presentation
3 minutes per pair: question, tools built, one thing Kiro got wrong and how they caught it.
