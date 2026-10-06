# D2 M07 — Decision Matrix (30m)

> **Preview** — this module has not yet been tested end to end.

## ECS vs AgentCore Runtime vs AgentCore Gateway

| Factor | ECS (Day 1) | AgentCore Runtime | AgentCore Gateway |
|---|---|---|---|
| Code to write | MCP server + auth + infra | MCP server only | None for OpenAPI / Lambda / MCP targets |
| Infra to operate | ALB, ECS, certs, scaling | None | None |
| Inbound auth | Our middleware | Built-in JWT authorizer | Built-in JWT authorizer |
| Outbound credentials | Secrets Manager + code | Identity | Identity |
| Fine-grained tool policy | Our code | Our code | Cedar policy |
| Custom logic / composite tools | Full control | Full control | Limited (use Lambda or MCP target) |
| Network control (VPC-only) | Full | Check current VPC options | Check current VPC options |
| Cost model | Always-on tasks | Per use | Per use |

## Rules of thumb
- **Existing internal API with OpenAPI spec** → Gateway OpenAPI target. Improve descriptions, done.
- **Curated Redshift queries** → MCP server on Runtime (analyst-owned SQL + descriptions), behind Gateway.
- **Need full network/runtime control or existing ECS platform standard** → ECS, same code.
- **One URL for Quick/Kiro** → Gateway in front of everything.

## Ownership model
| Role | Owns |
|---|---|
| Data analysts | SQL patterns, tool descriptions, review, testing |
| Platform team | Gateway, Runtime, Identity providers, Cognito / IdP federation, policies |
| Security | Policy review, DB grants, IdP config |

## Next steps after workshop
- Federate Cognito with your corporate IdP.
- Move from mock data to a read-only replica / curated `mcp` schema on real Redshift.
- Set up a review process (PR + checklist) for new tools.
