# Glossary

Plain meanings of the terms used in the guides, in alphabetical order. For sign-in terms in more depth, see [Sign-in and tokens, explained](sign-in-and-tokens.md).

| Term | Meaning |
|---|---|
| **Access token** | A signed, short-lived (1 hour) text string from Cognito that proves who you are. Sent as `Authorization: Bearer <token>` |
| **Agent** | A program where a model decides which tools to call, in a loop, until it can answer (Day 3) |
| **AgentCore** | Amazon Bedrock AgentCore: AWS services to run agents and tools (Runtime, Gateway, Identity, Policy, Observability) |
| **ALB** | Application Load Balancer: spreads requests over the ECS tasks (Day 1) |
| **App client** | An app registered in the Cognito user pool (`kiro-user`, `quick-user`, `quick-s2s`). Its ID appears in every token it gets |
| **ARN** | Amazon Resource Name: the full unique ID of an AWS resource, `arn:aws:<service>:<region>:<account>:<resource>` |
| **Cedar** | AWS's language for access rules: `permit(...)` and `forbid(...)`, with `when { ... }` conditions (Day 2 M05) |
| **CDK** | AWS Cloud Development Kit: infrastructure written as code, deployed through CloudFormation ([CDK infrastructure](infra.md)) |
| **Claim** | One field inside a token, such as `role`, `branch_id` or `client_id`. Always text |
| **CLI input JSON** | `--cli-input-json file://x.json`: an AWS CLI command takes all its options from a file instead of a long command line |
| **CloudFront** | AWS's content delivery network. Here it gives your server an HTTPS address (`https://<id>.cloudfront.net`) |
| **Credential provider** | An entry in the AgentCore Identity vault that holds an API key or OAuth client secret for the Gateway to use |
| **Discovery URL** | `https://cognito-idp.<region>.amazonaws.com/<user pool id>/.well-known/openid-configuration`: where Runtime and Gateway learn how to check Cognito tokens |
| **ECS / Fargate** | Elastic Container Service, running containers without servers to manage (Day 1) |
| **Gateway** | AgentCore Gateway: one MCP address in front of many tool sources (targets), with sign-in checks and rules |
| **Ground truth** | The correct answer to a test question, worked out by you (SQL or an API call), used to score the agent (Day 3 M04) |
| **Hook** | Code the agent framework runs at a fixed moment, e.g. before each tool call. The recorder and approval step are hooks |
| **Inbound / outbound** | Inbound: checking who calls you. Outbound: the credential you use to call something else |
| **Interceptor** | A small Lambda the Gateway runs on every request. Here it passes the user's token on to your MCP server |
| **Interrupt** | The agent pausing to wait for a person (the approval step), then resuming with their answer |
| **JWT** | JSON Web Token: the token format. Three parts joined by dots; the middle one is readable JSON with the claims |
| **MCP** | Model Context Protocol: a standard way for AI apps (Kiro, Quick, agents) to find and call tools |
| **MCP server** | A program that offers tools over MCP. Yours offers the restaurant tools |
| **OpenAPI** | A file that describes a REST API's operations and parameters (`mock-api/openapi.yaml`). The Gateway turns each operation into a tool |
| **operationId** | The name of one operation in an OpenAPI file, e.g. `getStockLevels`. It becomes the tool name |
| **Persona** | The test user a question runs as (`manager_branch_12`, `analyst_hq`, ...) |
| **Policy engine** | AgentCore Policy's container for Cedar rules. Attached to a Gateway, it decides each tool call before it runs |
| **Runtime** | AgentCore Runtime: runs your code (an MCP server or an agent) for you, behind an HTTPS address with sign-in checks |
| **Scope** | A named permission written into a token, here `<McpUrl>/read`. It looks like a URL but is only a label |
| **Session** | One conversation with the agent on Runtime, identified by a session ID; it keeps the agent's memory between calls |
| **Span / trace** | A trace is the timeline of one request; a span is one timed step in it (token check, policy check, tool call) |
| **stdio** | Standard input/output: how Kiro or the agent talks to a local MCP server it started itself |
| **Target** | One tool source behind the Gateway, e.g. `OpsApi` or `RstMcp`. Its tools are named `<target>___<tool>` |
| **User pool** | Cognito's list of users and its sign-in service (`rst-workshop`) |
| **Vault** | The AgentCore Identity store for outbound credentials, kept in Secrets Manager under `bedrock-agentcore-identity!...` |
