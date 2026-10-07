# D3 M07 — Wrap-up (15m)

## Three days in one table

| Day | You built | You own (analyst skill) | Platform / security own |
|---|---|---|---|
| 1 | MCP server: Redshift + internal API tools, on ECS with sign-in | SQL, tool names and descriptions, code review | ALB, Cognito, DB grants |
| 2 | Same tools on AgentCore Runtime and Gateway, Cedar policy, traces | Tool descriptions (OpenAPI too), which tools exist | Gateway, Identity, policies |
| 3 | An agent that plans, calls tools, asks before changing data; a test set | Questions and expected answers, approval rules, the system prompt | Runtime, model access, where approval prompts appear |

## Take home
- [kiro/steering/](../kiro/steering/): SQL rules and tool design rules for Kiro.
- [Review checklist](../prework/python-reading-primer.md#checklist-reviewing-kiros-code) for AI-written code.
- [solutions/mcp-server/](../solutions/mcp-server/): reference MCP server, read and write tools, branch scoping.
- [solutions/agent/](../solutions/agent/): reference agent, step-by-step recorder, approval hook, Runtime entrypoint.
- [evals/](../evals/): question set, ground-truth SQL, scorer. Start your own team's set from it.
- [Decision matrix](../day2/07-decision-matrix.md): ECS vs Runtime vs Gateway.

## Next steps for your team
1. **Pick one real use case** and write its 15–20 test questions **before** building anything. The questions are the spec.
2. **Run the tests on every change**: a tool description, a prompt, a model upgrade. Add a question for every wrong answer users report.
3. **Agree who approves what**: which actions change data, who may approve them, where the prompt appears (Quick, web app, ticket).
4. **Production sign-in**: connect your corporate identity provider instead of the workshop Cognito users.
5. **Follow-up session** (optional): production rollout, multi-agent patterns, AgentCore Memory and Evaluations.

## Feedback
Please fill in the feedback form before you leave. What should we cut, and what needed more time?
