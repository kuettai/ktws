# D2 M01 — AgentCore Overview (30m)

> **Preview** — this module has not yet been tested end to end.

> **Shared account?** Everyone works in one AWS account, so names must not clash. Put your participant name (the one from Day 1 Module 05) in every AgentCore resource you create today: runtimes (`rst_mcp_<name>`), gateways (`rst-gateway-<name>`), credential providers and policy engines. Delete only your own resources at the end.

## Objectives
- Map every Day 1 component to its AgentCore equivalent.
- Know what each AgentCore service does and doesn't do.

## Day 1 → Day 2 mapping

| Day 1 (built/ran ourselves) | Day 2 (AgentCore) |
|---|---|
| ECS + ALB + ACM + autoscaling | **Runtime** — serverless hosting, session isolation |
| Hand-written API wrapper tools (M03) | **Gateway** OpenAPI target — zero code |
| Redshift tools in our server | Keep in Runtime, or **Gateway** Lambda target |
| `auth.py` JWT middleware | Runtime / Gateway **inbound JWT authorizer** |
| `MOCK_API_KEY` in Secrets Manager | **Identity** credential provider (token vault) |
| "Don't expose write tools yet" | **Policy** (Cedar) on Gateway |
| CloudWatch logs only | **Observability** — traces, tool-call spans |

## Key message
Same MCP protocol, same Quick / Kiro clients, same Cognito pool. Less infrastructure, more configuration.

## Instructor notes
- Check service/feature availability in workshop region beforehand (Policy especially).
