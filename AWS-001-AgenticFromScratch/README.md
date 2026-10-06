# MCP Workshop: build MCP servers and AI agents on AWS

A three-day, hands-on workshop for **data analysts** who want to own MCP (Model Context Protocol) servers and the AI agents that use them. The story is a fictional quick-service restaurant chain with about 30 branches, sales history in Amazon Redshift, and a couple of internal applications.

Participants direct Kiro (an AI coding assistant) to write the code. They focus on what analysts are good at: the right SQL, clear tool descriptions, review and testing.

- **Pre-work** (~2h): install software, a Python *reading* primer, a guide to reviewing Kiro specs, steering and hooks.
- **Day 1**: build an MCP server locally (Redshift + internal APIs), deploy it to Amazon ECS, secure it with OAuth (Amazon Cognito), connect Amazon Quick and Kiro, scope data by user.
- **Day 2** *(preview)*: run the same workload on Amazon Bedrock AgentCore (Runtime, Gateway, Identity, Policy, Observability).
- **Day 3** *(preview)*: build a Strands agent on the same tools: the agent loop, multi-step reasoning, human approval for actions that change data, testing with a scored question set, and deploying on AgentCore Runtime.

Start with [learning-plan.md](learning-plan.md), then [prereqs.md](prereqs.md).

## Status

| Part | State |
|---|---|
| Day 1 | **Tested end to end** in an AWS sandbox account: Redshift tools, ECS + CloudFront, Cognito OAuth, branch scoping, Kiro IDE and Amazon Quick (web) user sign-in |
| Day 2 | Preview: guides written, not yet tested end to end |
| Day 3 | Preview: agent, approval hook and test harness have unit tests and were checked live against the Day 1 server; Runtime deploy not yet tested |

See [Status and known limitations](learning-plan.md#status-and-known-limitations).

## Quick start (local, no AWS)

```bash
docker compose up -d                       # mock POS/Inventory/Sales API + legacy Promotions service
cd solutions/mcp-server && cp .env.example .env && uv sync
npx @modelcontextprotocol/inspector uv run python server.py
```

```powershell
docker compose up -d                       # mock POS/Inventory/Sales API + legacy Promotions service
cd solutions/mcp-server
Copy-Item .env.example .env
uv sync
npx @modelcontextprotocol/inspector uv run python server.py
```

The Redshift tools need AWS credentials and the deployed `RstDataStack` (see [prereqs.md](prereqs.md)).

Before an event, each participant can run the pre-event check: [PREFLIGHT-CHECK.md](PREFLIGHT-CHECK.md).

## Folder map

```
learning-plan.md            Objectives, agenda, environment, status
prereqs.md                  Participant + instructor checklist
PREFLIGHT-CHECK.md          Laptop / network pre-event check (scripts/rst_preflight.py)
prework/                    Python reading primer, Kiro specs / steering / hooks guide
day1/ day2/ day3/           Module guides
docs/                       Data dictionary, approved query patterns, auth options
data/                       DDL, curated views, read-only grants, COPY, mock data generator
mcp-server/                 STARTER (Module 01 state): app, lib/ helpers, ping + who_am_i
solutions/mcp-server/       REFERENCE: Redshift, Ops API (incl. write tools issue_refund, request_stock_transfer), Promotions; branch scoping
agent/                      STARTER (Day 3 Module 01 state): Strands agent skeleton
solutions/agent/            REFERENCE: Strands agent, tool-call recorder, approval hook
evals/                      Day 3 test questions, expected-answer SQL, scoring script
mock-api/                   Mock Operations API (FastAPI) + openapi.yaml contract
legacy-app/                 Undocumented Promotions service (Node) for Exercise B
infra/                      CDK: RstDataStack, RstAuthStack, RstMcpStack
scripts/                    get_token.py, get_test_tokens.py (OAuth), create_test_users.py, rst_preflight.py
kiro/                       Steering files, mcp.json example
docker-compose.yml          Local mock-api + legacy-app (+ mcp-server with --profile http)
```

## Tests

```bash
cd mcp-server && uv run pytest               # starter: helpers + auth over HTTP
cd solutions/mcp-server && uv run pytest     # reference: SQL rules, scoping, auth over HTTP, write tools
cd mock-api && uv run pytest
cd legacy-app && TZ=UTC npm test
cd solutions/agent && uv run pytest          # agent, recorder, approval hook (scripted model, no AWS)
cd evals && uv run pytest                    # scoring
cd infra && npx cdk synth                    # needs CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION
```

```powershell
# from the workshop folder; each line returns to it with Pop-Location
Push-Location mcp-server; uv run pytest; Pop-Location               # starter: helpers + auth over HTTP
Push-Location solutions/mcp-server; uv run pytest; Pop-Location     # reference: SQL rules, scoping, auth, write tools
Push-Location mock-api; uv run pytest; Pop-Location
Push-Location legacy-app; $env:TZ = "UTC"; npm test; Pop-Location
Push-Location solutions/agent; uv run pytest; Pop-Location          # agent, recorder, approval hook (no AWS)
Push-Location evals; uv run pytest; Pop-Location                    # scoring
Push-Location infra; npx cdk synth; Pop-Location                    # needs CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION
```

`cd agent && uv run pytest` (PowerShell: `cd agent; uv run pytest`) fails on purpose until the Day 3 Lab 1 and Lab 3 TODOs are done.

## Costs and safety

- Use a **sandbox** AWS account, never production. The stacks create a VPC with a NAT gateway, Redshift Serverless, an internal load balancer, ECS Fargate tasks and a CloudFront distribution — roughly a few US dollars per day while deployed. Delete the stacks when you're done (`npx cdk destroy --all`).
- Test users and tokens are for the workshop only. Don't paste passwords or tokens into chats or tickets.

## Disclaimer

This is a community workshop, **not an official AWS workshop**. The code is sample code for learning: review it before reusing it, and don't run it against production data. Some Day 3 explanations are adapted from the AWS "Building with Amazon Bedrock" workshop and credited where used.

## License

MIT-0. See [LICENSE](../LICENSE).
