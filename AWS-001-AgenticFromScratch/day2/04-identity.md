# D2 M04 — AgentCore Identity (45m)

> **Preview** — this module has not yet been tested end to end.

## Objectives
- Distinguish inbound auth (who calls the MCP) vs outbound auth (how MCP calls downstream).
- Store downstream credentials in the Identity token vault.
- Understand user-delegated outbound OAuth.

## Content
1. **Inbound vs outbound (10m).** Inbound = Cognito JWT from Quick/Kiro (Day 1 M06). Outbound = mock API key, or OAuth to a downstream SaaS.
2. **API key provider (10m).** Move `X-API-Key` from Secrets Manager (Day 1) into an Identity API key credential provider; attach to Gateway target.
3. **OAuth provider (20m).** Scenario: a downstream system (e.g. HR rostering) requires the *user's* own OAuth consent.
    - Create OAuth2 credential provider (any OIDC IdP — reuse a second Cognito app client to simulate).
    - First call triggers consent URL; token stored in vault per user; later calls reuse it.
4. **Recap (5m).** Day 1: secrets in Secrets Manager + our code. Day 2: vault + config.

## Checkpoint
Gateway OpenAPI target uses Identity-managed API key; no secret in code or env vars.
