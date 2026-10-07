# D2 M01 — AgentCore Overview (30m)

> **Shared account?** Everyone works in one AWS account, so names must not clash. Put your participant name (the one from Day 1 Module 05) in every AgentCore resource you create today: the project `rstday2<name>`, and `--participant <name>` for the helper scripts, which then name the gateway `rst-gateway-<name>`, the credential providers `rst-ops-api-key-<name>` / `rst-runtime-s2s-<name>`, and expect the policy engine `rst_policy_engine_<name>`. Delete only your own resources at the end.

## Objectives
- Map every Day 1 component to its AgentCore equivalent.
- Know what each AgentCore service does and doesn't do.

## Day 1 → Day 2 mapping

| Day 1 (built/ran ourselves) | Day 2 (AgentCore) |
|---|---|
| ECS + ALB + ACM + autoscaling | **Runtime** — serverless hosting, session isolation |
| Hand-written API wrapper tools (M03) | **Gateway** OpenAPI target — zero code |
| Redshift tools in our server | Same server on **Runtime** (M02), behind the **Gateway** (M03) |
| `auth.py` JWT middleware | Runtime / Gateway **inbound JWT authorizer** |
| Ops API key in Secrets Manager, given to the container | **Identity** credential provider (vault), used by the Gateway |
| `if role != ...` checks in each tool | **Policy** (Cedar rules) on the Gateway, for every tool |
| CloudWatch logs only | **Observability** — traces, tool-call spans |

## Key message
Same MCP protocol, same Quick / Kiro clients, same Cognito pool. Less infrastructure, more configuration.

## Instructor notes
- Day 2 was tested in us-east-1. Check that AgentCore Runtime, Gateway, Identity and Policy are available in your workshop region.
- Participants need: Node.js 20+ (`@aws/agentcore` CLI), AWS CLI 2.34+ (`bedrock-agentcore-control` commands with `--cli-input-json`), and Day 1 finished with auth on.
