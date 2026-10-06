# Learning Plan — Building MCP Servers and AI Agents

## Audience

Data analysts at a (fictional) restaurant chain moving into owning MCP-building tasks.

- **Strong:** SQL, Redshift, business domain (branches, sales, inventory).
- **New:** Python, containers, AWS infrastructure, OAuth, agents.

**Design principle:** analysts own the *what* (SQL, tool names, descriptions, review, testing). Kiro writes the *how* (Python). Infrastructure and auth middleware are pre-built — analysts run, read, and configure them, not author them.

## Workshop outcomes

By the end of the workshop, participants can:

1. Explain what MCP is and when to use tools vs resources vs prompts.
2. Turn an existing SQL query into a safe, well-described MCP tool using Kiro.
3. Turn an existing internal API (from its contract or its code) into MCP tools using Kiro.
4. Review AI-generated code for SQL injection, over-broad access, and poor tool design.
5. Deploy an MCP server to ECS behind HTTPS and connect Amazon Quick and Kiro to it.
6. Configure service-to-service (2LO) and user (3LO) OAuth, and use user identity to scope data.
7. Deploy the same capability on AgentCore Runtime and Gateway, and choose between ECS and AgentCore.
8. Explain the agent loop and build a Strands agent that uses the workshop's MCP tools for multi-step questions.
9. Require human approval before an agent runs a write tool (`issue_refund`, `request_stock_transfer`), on top of Cedar policy.
10. Test agent behaviour with a 15–20 question set: score tool choice and answer accuracy, and use the score to drive changes.

## Environment

- One AWS **sandbox** account per participant (or per pair) — never a production account. An instructor-run event can provide these through AWS Workshop Studio; self-paced, use your own sandbox.
- Set up before Day 1 (instructor, or yourself when self-paced): Redshift Serverless with seeded mock data, S3 bucket, Cognito user pool skeleton (`RstDataStack`, `RstAuthStack`). Steps: [Prerequisites, Account setup](prereqs.md#account-setup).
- Also needed: Amazon Quick (Enterprise) for the Quick modules, and Amazon Bedrock model access for the Day 3 agent.
- Laptop: Kiro, Python 3.12+, `uv`, Docker (or Finch), AWS CLI v2, Node.js (MCP Inspector). Full checklist: [Prerequisites](prereqs.md).

## Pre-work (~2h)

| Item | Time | Guide |
|---|---|---|
| Install and check software, sign in to Kiro | 30m | [Prerequisites](prereqs.md) |
| Python reading primer — read, not write, the code Kiro produces | 60m | [Python reading primer](prework/python-reading-primer.md) |
| Reviewing Kiro specs, steering and hooks | 25m | [Kiro guide](prework/kiro-guide.md) |

Day 1 opens with a 15m warm-up that recaps the primer for anyone who skipped it.

## Data model

Fictional quick-service restaurant chain: ~30 branches, 20 menu items, 180 days of orders, daily inventory. Base tables in schema `rst`. Curated views in schema `mcp` — the MCP server may only query `mcp`. See [docs/data-dictionary.md](docs/data-dictionary.md).

Split of responsibilities between data sources:

| Source | Answers | Example |
|---|---|---|
| Redshift (`mcp` views) | Historical / analytical | "Revenue for branch 12 last week" |
| Mock API (POS / Inventory / Sales) | Real-time / operational | "Current stock of chicken at branch 12" |

Combined question for the final demo: *"Branch 12 is low on chicken right now. How much chicken did it waste last month?"*

---

## Day 1 — Build local, deploy to ECS, secure it

Target: 08:30–17:15 (7h15 content, 1h30 breaks).

| # | Module | Time | Outcome |
|---|---|---|---|
| — | Python reading warm-up (recap of [primer](prework/python-reading-primer.md)) | 15m | Read a tool function: decorator, type hints, docstring, parameterized SQL |
| 00 | [MCP fundamentals](day1/00-mcp-fundamentals.md) | 30m | Understand host / client / server, tools / resources / prompts, stdio vs Streamable HTTP |
| 01 | [Hello MCP](day1/01-hello-mcp.md) | 40m | Run a local stdio MCP server, test in MCP Inspector, use it from Kiro |
| 02 | [Redshift tools](day1/02-redshift-tools.md) | 90m | Turn SQL into parameterized MCP tools via Kiro, gated by steering files |
| 03 | [Wrap internal API](day1/03-wrap-internal-api.md) | 75m | Generate MCP tools from OpenAPI contract (A) and from legacy code (B) |
| 04 | [Go remote](day1/04-go-remote.md) | 30m | Switch to stateless Streamable HTTP, run in a container |
| 05 | [Deploy to ECS](day1/05-deploy-ecs.md) | 45m | Deploy via pre-built CDK; understand ALB, task role, secrets |
| 06 | [Authentication](day1/06-auth.md) | 90m | 2LO + 3LO with Cognito; branch-scoped data; connect Quick and Kiro |
| 07 | [End-to-end](day1/07-end-to-end.md) | 20m | Quick + Kiro answer combined Redshift + API question |

**Day 1 schedule**

| Time | Item |
|---|---|
| 08:30–08:45 | Python reading warm-up |
| 08:45–09:15 | M00 MCP fundamentals |
| 09:15–09:55 | M01 Hello MCP |
| 09:55–10:10 | Break |
| 10:10–11:40 | M02 Redshift tools |
| 11:40–12:55 | M03 Wrap internal API |
| 12:55–13:55 | Lunch |
| 13:55–14:25 | M04 Go remote |
| 14:25–15:10 | M05 Deploy to ECS |
| 15:10–15:25 | Break |
| 15:25–16:55 | M06 Authentication |
| 16:55–17:15 | M07 End-to-end |

**Day 1 checkpoints**

- After M02: `get_daily_branch_sales`, `find_branch` and one more tool pass MCP Inspector and the review checklist.
- After M03: at least 3 API tools work; group compares Exercise A vs B output.
- After M05: `https://<alb>/mcp` responds (401 is fine once auth is on).
- After M06: Quick user signed in as `manager_branch_12` only sees branch 12 data.

---

## Day 2 — Same workload on AgentCore

> **Preview** — Day 2 has not yet been tested end to end.

Target: 09:00–17:00 (6h30 content, 1h30 breaks).

| # | Module | Time | Outcome |
|---|---|---|---|
| 01 | [AgentCore overview](day2/01-agentcore-overview.md) | 30m | Map Day 1 components to AgentCore services |
| 02 | [Runtime](day2/02-runtime.md) | 75m | Host Day 1 MCP server on AgentCore Runtime with JWT inbound auth |
| 03 | [Gateway](day2/03-gateway.md) | 90m | Zero-code MCP from OpenAPI; Lambda target for Redshift; semantic tool search |
| 04 | [Identity](day2/04-identity.md) | 45m | Outbound credentials (API key, OAuth) via token vault |
| 05 | [Policy + Observability](day2/05-policy-observability.md) | 60m | Cedar policy restricting write tools; CloudWatch traces |
| 06 | [Capstone](day2/06-capstone.md) | 60m | Quick + Kiro on Gateway, one restaurant scenario end to end |
| 07 | [Decision matrix](day2/07-decision-matrix.md) | 30m | Choose ECS vs Runtime vs Gateway for common use cases |

**Day 2 schedule**

| Time | Item |
|---|---|
| 09:00–09:30 | M01 AgentCore overview |
| 09:30–10:45 | M02 Runtime |
| 10:45–11:00 | Break |
| 11:00–12:30 | M03 Gateway |
| 12:30–13:30 | Lunch |
| 13:30–14:15 | M04 Identity |
| 14:15–15:15 | M05 Policy + Observability |
| 15:15–15:30 | Break |
| 15:30–16:30 | M06 Capstone |
| 16:30–17:00 | M07 Decision matrix |

**Day 2 checkpoints**

- After M02: Kiro calls Runtime-hosted MCP with a Cognito bearer token.
- After M03: Gateway exposes mock API tools without code written by participant.
- After M05: `issue_refund` denied for non-manager, allowed for manager; trace visible.

---

## Day 3 — Agents: plan, act, ask, measure

> **Preview** — Day 3 has not yet been tested end to end. The agent and test harness have unit tests, and the agent was checked live against the Day 1 server.

Target: 09:00–17:00 (6h30 content, 1h30 breaks).

The agent uses the same tools as Days 1–2 — no new data sources. Code lives in [agent/](agent/) (starter) and [solutions/agent/](solutions/agent/) (reference: Strands agent, tool-call recorder, approval hook). Test assets live in [evals/](evals/) (questions, expected-answer SQL, scoring script).

| # | Module | Time | Outcome |
|---|---|---|---|
| 00 | [Agent fundamentals](day3/00-agent-fundamentals.md) | 30m | Explain the agent loop (plan → tool call → result → next step), stop conditions; read a Day 1 Quick/Kiro trace as an agent loop |
| 01 | [First agent](day3/01-first-agent.md) | 60m | Strands agent on the Day 1 MCP server; tool-call recorder prints every step |
| 02 | [Multi-step reasoning](day3/02-multi-step.md) | 45m | Combined question across Redshift + API; diagnose wrong tool, loops, early stop; fix with tool descriptions, system prompt, step limit |
| 03 | [Human approval](day3/03-human-approval.md) | 60m | Agent pauses before `issue_refund` / `request_stock_transfer`; user approves or denies; Cedar policy still applies |
| 04 | [Evaluation](day3/04-evaluation.md) | 90m | Write 15–20 questions with expected tool, parameters and SQL-derived answer; score tool choice + answer accuracy; change one thing, rerun, compare |
| 05 | [Deploy the agent](day3/05-deploy-agent.md) | 45m | Agent on AgentCore Runtime, tools via Gateway; trace a run in Observability |
| 06 | [Capstone](day3/06-capstone.md) | 45m | Pairs: one restaurant scenario as an agent, with approval and a test score |
| 07 | [Wrap-up](day3/07-wrap-up.md) | 15m | What to take home; next steps for your team |

**Day 3 schedule**

| Time | Item |
|---|---|
| 09:00–09:30 | M00 Agent fundamentals |
| 09:30–10:30 | M01 First agent |
| 10:30–10:45 | Break |
| 10:45–11:30 | M02 Multi-step reasoning |
| 11:30–12:30 | M03 Human approval |
| 12:30–13:30 | Lunch |
| 13:30–15:00 | M04 Evaluation |
| 15:00–15:15 | Break |
| 15:15–16:00 | M05 Deploy the agent |
| 16:00–16:45 | M06 Capstone |
| 16:45–17:00 | M07 Wrap-up |

**Day 3 checkpoints**

- After M01: agent answers "best sellers at branch 12 this month" and the recorder shows each tool call with its parameters.
- After M02: combined question (top sellers → current stock → last month's waste) answered in one run, with the plan visible in the recorder.
- After M03: agent stops before `issue_refund`; deny → no refund in mock API; approve → refund created. Non-manager still denied by policy.
- After M04: each pair has a scored question set and one before/after comparison of a change.
- After M05: same question answered by the Runtime-hosted agent; trace visible.

---

## Teaching threads (repeat across modules)

1. **Kiro fast, human reviews.** Every Kiro output gets a review step: injection, scope, descriptions.
2. **Defense in depth.** Steering file guides Kiro; DB grants enforce. Neither alone is enough. On Day 3: policy decides what is allowed, a person confirms each change.
3. **Tool design is the analyst skill.** Names, descriptions, parameters decide whether Quick and the agent pick the right tool.
4. **Identity matters.** User auth is only meaningful if it changes what data the user sees.
5. **Measure, don't guess.** A change to a tool or prompt is only an improvement if the test score says so. Analysts already know how to produce ground truth: SQL.

## Status and known limitations

**Tested end to end (Day 1):** data and auth stacks, Redshift tools through MCP, ECS deploy behind CloudFront, 401 for missing or invalid tokens, branch scoping and write-tool rules for manager / staff / HQ, the M07 combined question, Kiro IDE OAuth sign-in, and Amazon Quick (web) user authentication — all against a real Cognito pool. Findings from that run are built into M05, M06 and [docs/auth-options.md](docs/auth-options.md).

**Not yet verified:**

- Quick **service auth** against Cognito: Quick always sends `resource` (RFC 8707), and Cognito doesn't support resource binding on client credentials. It may be rejected.
- Amazon Quick availability and cost in your accounts (needs Enterprise).
- AgentCore Runtime / Gateway / Policy availability in your region.
- Day 2 end to end.
- Day 3 end to end: `agentcore` CLI flags in M05 come from help text, not a live run. Bedrock model access (including any one-time model use-case form) must be enabled. Quick does not show the agent's approval prompts — the approval demo runs in the agent CLI.
- Module timings beyond Day 1's measured deploy times: dry-run each day with an analyst-profile tester (M02 and Day 3 M04 especially).
