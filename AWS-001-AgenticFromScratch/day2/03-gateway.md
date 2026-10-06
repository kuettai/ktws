# D2 M03 — AgentCore Gateway (90m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Expose the mock Ops API as MCP tools from OpenAPI with zero code.
- Expose Redshift via a Lambda target.
- Put the Runtime MCP server behind the same Gateway.
- Use semantic tool search when the tool list grows.

## Steps
1. **Create Gateway (15m).** Inbound auth: JWT, Cognito discovery URL, allowed clients. Note Gateway MCP URL.
2. **OpenAPI target (25m).**
    - Upload `mock-api/openapi.yaml` (to S3 or inline).
    - Outbound auth: API key credential provider (`X-API-Key`) — created in M04, or quick-create here.
    - Mock API must be reachable from Gateway (public endpoint with API key, or verify private connectivity options).
    - List tools in Kiro. Compare to Day 1 M03 hand-built tools: naming, descriptions, 1:1 mapping.
3. **Improve tool descriptions (15m).** Edit `summary` / `description` in OpenAPI → redeploy target → see better tool selection. Analyst skill again, no code.
4. **Lambda target for Redshift (20m).** Pre-built Lambda wraps 3 approved query patterns; define tool schema for the target. Discuss: Lambda target vs keeping SQL tools in Runtime.
5. **MCP server target (10m).** Add Runtime server from M02 as a target. One Gateway URL now fronts everything.
6. **Semantic search (5m).** Enable; show the built-in search tool returns relevant tools for "waste".

## Checkpoint
One Gateway URL in Kiro exposes: Ops API tools (OpenAPI), Redshift tools (Lambda), Runtime MCP tools.

## Discussion
- Day 1 M03 Exercise A took 30m of Kiro + review. Gateway took 10m. When would you still hand-build? (Combined/composite tools, custom logic, response shaping.)
