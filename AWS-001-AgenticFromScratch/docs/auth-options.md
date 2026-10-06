# Authentication Options

## How MCP auth works (one paragraph)

The MCP authorization spec is based on OAuth 2.1. The **MCP server is a resource server**: it does not log anyone in, it only validates access tokens. A separate **authorization server (IdP)** issues tokens. An unauthenticated request gets `401` with a `WWW-Authenticate` header pointing at the server's Protected Resource Metadata (RFC 9728), which tells the client which IdP to use.

Because the MCP server only validates JWTs, swapping IdP = changing three config values:

```
OIDC_ISSUER   = https://<idp>/...
OIDC_JWKS_URL = https://<idp>/.../jwks
OIDC_AUDIENCE = <client id or API identifier>
```

## Flows

| Flow | OAuth grant | Who is the caller | Workshop use |
|---|---|---|---|
| Service-to-service (2LO) | `client_credentials` | An application | Quick service auth; batch jobs |
| User (3LO) | `authorization_code` + PKCE | A human, via browser login | Quick user auth; Kiro OAuth |

User auth is only meaningful if the identity changes behaviour. In the workshop: `custom:branch_id` claim restricts which branch's data a manager sees.

## IdP options

| IdP | DCR support | Typical fit | Notes |
|---|---|---|---|
| Amazon Cognito | No | Workshop default | No external tenant needed. Supports federation with SAML / OIDC corporate IdP |
| Microsoft Entra ID | No | Likely corporate IdP | Watch v1 vs v2 token `aud` / `iss` differences. Use app roles or groups for claims |
| Okta | Yes | Common enterprise | Custom authorization server needed for custom scopes |
| Auth0 | Yes | Good dev experience | DCR must be enabled per tenant |
| Keycloak (self-hosted) | Yes | Full control | Run on ECS. Fills DCR gap. You operate it |
| Ping Identity | Yes (PingFederate) | Enterprise | Standard OIDC |
| Google | No | Consumer / Workspace | Limited custom claims |

**DCR (Dynamic Client Registration)** lets an MCP client register itself with the IdP automatically. Some MCP clients expect it for "just works" OAuth. Without DCR, pre-register a client and give the client ID/secret to the MCP client.

## Recommended approach

- **Workshop:** Cognito, pre-registered app clients.
- **Optional module:** swap to Keycloak or Entra by changing the three config values above.
- **Production pattern:** Cognito federated with your corporate IdP (often Entra ID). Users sign in with corporate credentials; Cognito issues tokens with consistent claims (`custom:branch_id`, `custom:role`).
- **AgentCore (Day 2):** Runtime and Gateway inbound JWT authorizers accept any OIDC discovery URL, so the same IdP choice carries over.

## Resource binding (RFC 8707)

MCP clients (Kiro, Quick) send `resource=<McpUrl>` in the authorization request, as the MCP spec requires. Cognito then:

- accepts only custom scopes of a resource server whose **identifier equals that URL**, otherwise: `invalid_request: custom scopes requested for resource-binding must be assigned to the resource being requested`;
- sets the access token `aud` to the URL.

So the resource server identifier is the `McpUrl` (a URL is allowed as identifier; the display name can't contain `:` or `/`), and the scope string becomes `<McpUrl>/read`. In CDK: `RstAuthStack -c mcpResourceUrl=<McpUrl>` and `RstMcpStack -c oidcRequiredScopes=<McpUrl>/read`. The stack output `ReadScope` shows the value. The URL is only known after M05, which is why M06 creates the resource server after the first ECS deploy.

## Client configuration reference

Validated against Amazon Quick and Kiro documentation and tested end to end against a real Cognito pool (Kiro IDE OAuth, Quick web user auth). Items marked **not yet tested** still need a live run.

### Amazon Quick

How Quick connects: it sends an unauthenticated request, gets `401` + `WWW-Authenticate: ... resource_metadata=...`, and reads the Protected Resource Metadata (RFC 9728). Our server does this out of the box. Cognito has no DCR, so credentials are entered manually.

Console path (Quick web): **Connectors → Create → Model Context Protocol (MCP)**, auth configuration **Custom OAuth app**. Fields: Name, Description, MCP server endpoint, Connection type (Public network or a VPC connection), Auth server connection type. Then:

| Field | User authentication (3LO) | Service authentication (2LO) |
|---|---|---|
| Client ID | `quick-user` client ID | `quick-s2s` client ID |
| Public OAuth client | Leave unchecked (`quick-user` has a secret) | n/a |
| Client Secret | `quick-user` secret | `quick-s2s` secret |
| Token URL | `https://<domain>.auth.<region>.amazoncognito.com/oauth2/token` | same |
| Authorization URL | `https://<domain>.auth.<region>.amazoncognito.com/oauth2/authorize` | n/a |
| Redirect URL | Pre-filled by Quick and read-only: `https://<region>.quicksight.aws.amazon.com/sn/oauthcallback`. **Add it to `quick-user` allowed callbacks** (`-c quickCallbackUrls=`) | n/a |
| Scopes | Taken from the metadata's `scopes_supported` (`<McpUrl>/read`). If a scope field is shown, enter `openid <McpUrl>/read` | same |

Behaviour that matters for the workshop:

- Quick always sends `resource=<MCP URL>` (RFC 8707). For user auth, Cognito accepts it **only if the requested custom scope belongs to a resource server whose identifier is that exact URL** (see [Resource binding](#resource-binding-rfc-8707)). It then sets the access token `aud` to the MCP URL. Our verifier accepts it because `client_id` still matches (covered by a test).
- **Not yet tested:** Cognito says resource binding is not available for client-credentials grants. Unclear whether Cognito ignores or rejects `resource` on a `client_credentials` request. If rejected, Quick service auth fails against Cognito. Fallback: use user auth only, or an IdP that supports it.
- Quick web connectors take no custom HTTP headers: OAuth or no auth only. **Quick Desktop** installs a published web connector (Capabilities → Connectors → Browse more → Install); its own "Add MCP → Remote" only takes a static token header, which expires with the token.
- 5-minute timeout per MCP operation; max 100 tools per connection; tool `inputSchema` must be JSON Schema Draft 7 or later (all 20 reference tools pass).
- Tool list does not auto-update for custom connectors: press **Sync** after adding tools (re-authorizes).
- Needs Amazon Quick **Enterprise** subscription.
- Private alternative: Quick can reach an MCP server through a Quick VPC connection (DNS resolver endpoints required), instead of CloudFront.

### Kiro

Option 1 — Kiro OAuth with a pre-registered client (recommended). Setting `oauth.clientId` skips DCR:

```json
"rst-remote-ecs": {
  "url": "https://<distribution-id>.cloudfront.net/mcp",
  "oauth": {
    "clientId": "<kiro-user client id>",
    "redirectUri": "http://localhost:7778/oauth/callback",
    "oauthScopes": ["openid", "<McpUrl>/read"]
  }
}
```

- Kiro **IDE supports public clients only** (PKCE, no secret) → `kiro-user` has no secret. Kiro CLI also supports `clientSecret`.
- **Pin `redirectUri`.** Default is a random localhost port, which Cognito would reject. Register exactly `http://localhost:7778/oauth/callback` (`localhost` and `127.0.0.1` are not interchangeable).
- **Set `oauthScopes`.** Kiro's default is `openid email profile offline_access`; `offline_access` is not a Cognito scope and the request would fail.
- Kiro discovers Cognito's authorize/token endpoints from the metadata's `authorization_servers` (Cognito publishes OIDC discovery at `<issuer>/.well-known/openid-configuration`). Tested: works.
- Kiro sends `resource=<McpUrl>`, so the scope must be `<McpUrl>/read` (see [Resource binding](#resource-binding-rfc-8707)).
- Kiro IDE and Kiro CLI can't sign in at the same time: both listen on port 7778 for the redirect ("Address already in use").

Option 2 — static bearer token (fallback, works with any IdP):

```json
"rst-remote-ecs-token": {
  "url": "https://<distribution-id>.cloudfront.net/mcp",
  "headers": { "Authorization": "Bearer ${RST_MCP_TOKEN}" }
}
```

Kiro IDE only expands env vars listed in the **Mcp Approved Env Vars** setting — add `RST_MCP_TOKEN` there. Get the token with `scripts/get_token.py` (set `RST_MCP_SCOPE="openid <McpUrl>/read"` first).

### Microsoft Entra ID notes (if you swap IdP)

- `AADSTS9010010`: Entra v2.0 endpoint rejects `resource` + `scope` together. Use v1.0 endpoints with `accessTokenAcceptedVersion: 2`.
- `AADSTS90009`: for user auth, use two app registrations (Quick client app, MCP resource app).

### Cognito pieces to create (Day 1 M06)

1. User pool with custom attributes `custom:branch_id`, `custom:role`
2. Managed login domain
3. Resource server named `rst-mcp`, **identifier = the `McpUrl`** (`-c mcpResourceUrl=`), scope `read` (and `write` for Day 2). Scope string: `<McpUrl>/read`
4. App client `quick-s2s` — client credentials, scope `<McpUrl>/read`
5. App client `quick-user` — auth code + PKCE, callback = `https://<region>.quicksight.aws.amazon.com/sn/oauthcallback`
6. App client `kiro-user` — public client, auth code + PKCE, callbacks `http://localhost:7778/oauth/callback` (Kiro IDE) and `http://localhost:8765/callback` (`scripts/get_token.py`)
7. Managed login style for `quick-user` and `kiro-user` (otherwise "Login pages unavailable")
8. Pre-token-generation Lambda (pre-built in `RstAuthStack`, V2 trigger, requires Essentials feature plan) copies `custom:role` / `custom:branch_id` into the access token as `role` / `branch_id`
