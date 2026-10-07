# Prerequisites

This page has two parts:

- **[Participants: before Day 1](#participants-before-day-1)**: install the tools, get the code, set up the AWS access your instructor gives you, and read two short guides. You deploy **nothing** to AWS before Day 1.
- **[Account setup](#account-setup)**: for the instructor (or for yourself, if you work through the workshop alone). It prepares the AWS account: data warehouse, user directory, test users.

## Participants: before Day 1

About **30 minutes** to install and check your laptop, plus about **1h30 of reading**. No CDK, no stacks and no AWS console work: your instructor has prepared the account.

- [ ] [Get the workshop code](#get-the-workshop-code)
- [ ] [Install the laptop tools](#laptop-tools)
- [ ] [Set up your AWS profile](#set-up-your-aws-profile) with the access your instructor sends you
- [ ] [Run the pre-event check](#run-the-pre-event-check)
- [ ] [Read the two pre-work guides](#reading)

### Get the workshop code

Clone the repository once, then move into this workshop's folder:

```bash
git clone https://github.com/kuettai/ktws.git
cd ktws/AWS-001-AgenticFromScratch
```

```powershell
git clone https://github.com/kuettai/ktws.git
cd ktws\AWS-001-AgenticFromScratch
```

**Run every command in these guides from this folder** (`ktws/AWS-001-AgenticFromScratch`, called the **workshop folder** in all guides), unless a step says otherwise (for example `cd infra`). Open this same folder in Kiro.

No Git yet? Install it first (see the list below), or download the code as a ZIP from the [repository page](https://github.com/kuettai/ktws) (**Code → Download ZIP**) and unzip it.

### Laptop tools

- [ ] Kiro installed and signed in
- [ ] Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) (`uv` creates every Python environment for you, so you never set up a venv by hand; the AgentCore CLI also uses it on Days 2–3)
- [ ] Docker Desktop or Finch (needed from Module 04; Modules 01-03 run without it). Can't install either on your laptop? Run the Module 05 deploy from AWS CloudShell, which has Docker built in.
- [ ] AWS CLI v2, version 2.34 or later (`aws --version`; Day 2 uses the `bedrock-agentcore-control` commands)
- [ ] Node.js 22.19+ (MCP Inspector needs it; current LTS versions are fine)
- [ ] Days 2–3: the AgentCore CLI, `npm install -g @aws/agentcore@0.31` (Day 2 M02 step 1 shows it)
- [ ] Git
- [ ] Browser access to the AWS Console and Amazon Quick (and Workshop Studio, if your event uses it)

#### Windows

Every command in the guides has a **Windows (PowerShell)** tab next to the macOS / Linux one. Windows PowerShell 5.1, which ships with Windows 10 and 11, is enough.

- Install the tools with winget (or download them from each vendor's site):

    ```powershell
    winget install Python.Python.3.12 astral-sh.uv OpenJS.NodeJS.LTS Git.Git Amazon.AWSCLI
    ```

- Containers: Finch on Windows needs WSL2. Docker Desktop also works.
- Run commands from the workshop folder, as the guides do.
- Use `py` where the guides say `python3` for a script, e.g. `py scripts/rst_preflight.py`.
- If PowerShell refuses to run a script such as `.venv\Scripts\Activate.ps1`, allow local scripts once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Set up your AWS profile

Every AWS command in the workshop (CDK, the AWS CLI, and the MCP server you run locally) uses one named profile: **`workshop`**. Kiro's `mcp.json` uses the same name. Use the **sandbox** access your instructor sends you (or your own sandbox when self-paced), never production.

**1. Create the profile.** Pick the way your access was given to you:

- **IAM Identity Center (single sign-on):** `aws configure sso --profile workshop`, then follow the prompts (start URL, region, account, role). Sign in again later with `aws sso login --profile workshop`.
- **Temporary keys** (copied from your sandbox portal, Workshop Studio, or the console's "access keys" page). They include a session token and expire, usually after a few hours; repeat this when they do:

    ```bash
    aws configure set aws_access_key_id <access key id> --profile workshop
    aws configure set aws_secret_access_key <secret access key> --profile workshop
    aws configure set aws_session_token <session token> --profile workshop
    aws configure set region <region> --profile workshop
    ```

    ```powershell
    aws configure set aws_access_key_id <access key id> --profile workshop
    aws configure set aws_secret_access_key <secret access key> --profile workshop
    aws configure set aws_session_token <session token> --profile workshop
    aws configure set region <region> --profile workshop
    ```

- **Long-lived access keys** (least preferred): `aws configure --profile workshop`.

**2. Use it in every terminal.** CDK takes the account and region from the profile. Setting the region explicitly avoids a stale `AWS_REGION` sending deploys to the wrong region:

```bash
export AWS_PROFILE=workshop AWS_REGION=<region> CDK_DEFAULT_REGION=<region>
```

```powershell
$env:AWS_PROFILE = "workshop"; $env:AWS_REGION = "<region>"; $env:CDK_DEFAULT_REGION = "<region>"
```

**3. Check it.** `aws sts get-caller-identity --profile workshop` shows the account and role behind the profile. (Without `--profile` it checks whatever credentials the terminal uses by default, which may be a different account.) Note the **role name**: in `arn:aws:sts::<account>:assumed-role/WSParticipantRole/jane` it is `WSParticipantRole`. Account setup below needs it (`localDevRoleNames`); send it to your instructor if they ask.

Never paste keys or tokens into chats, tickets or code; keep them in the profile only.

If your instructor gave you a **participant name** (for example `alice`), note it: you use it from Day 1 Module 05.

### Run the pre-event check

- [ ] `python3 scripts/rst_preflight.py --deep` (Windows: `py scripts/rst_preflight.py --deep`) passes. See [PREFLIGHT-CHECK.md](PREFLIGHT-CHECK.md) for what it checks and how to fix a FAIL.

### Reading

| Item | Time | |
|---|---|---|
| [Python reading primer](prework/python-reading-primer.md): read, not write, the code Kiro produces | 60m | Day 1 opens with a 15m recap for anyone who skipped it |
| [Reviewing Kiro specs, steering and hooks](prework/kiro-guide.md) | 25m | Read only; nothing to create |
| Optional: one or two of your own report queries, anonymised (no real data) | — | Day 1 tool, Day 3 test question |

### What you need to know already

- Comfortable writing SQL `SELECT` with joins and `GROUP BY`
- Basic terminal usage (cd, run commands, edit env vars)
- No Python, Docker, AWS or OAuth experience required

## Account setup

For the **instructor** before an event, or for yourself when self-paced. Set up and select the `workshop` profile first ([Set up your AWS profile](#set-up-your-aws-profile)), in the same terminal.

### Choose a mode

| | Shared account | One account per participant |
|---|---|---|
| Best for | Groups new to AWS; customers who can't give everyone a sandbox | Self-paced learners; events with one sandbox each (e.g. Workshop Studio) |
| Data warehouse, user directory, test users | Deployed **once**, shared by everyone | Deployed in **every** account |
| Each participant deploys | `RstMcpStack-<name>` (their MCP server) on Day 1 | `RstMcpStack` on Day 1 |
| Cognito sign-in domain | Created once by the instructor; each participant adds their own resource server and app clients (Module 06) | Each participant creates it (Module 06) |
| Cost | One NAT gateway and one Redshift for the group | One of each per account |
| Risk | One mistake can affect everyone: see [safety rules](#shared-account-checklist) | Isolated |

### What the two stacks create

You deploy two of the workshop's three stacks here, so the data and the user directory are ready before Day 1. Participants deploy the third, their MCP server on ECS (`RstMcpStack`, or `RstMcpStack-<name>` in a shared account), in Day 1 Module 05.

**`RstDataStack`: the data warehouse and its mock data** (about 5 minutes)

| Part | What it is | Why |
|---|---|---|
| VPC | A private network with public, app and data subnets, and one NAT gateway | Redshift and, later, the MCP server run privately; the NAT gives private subnets outbound access to AWS APIs |
| Redshift Serverless | Namespace and workgroup `rst-workshop` (8 base capacity units), database `dev` | Holds the restaurant chain's history: orders, items, waste |
| Mock data | A one-off Lambda that generates 180 days of orders for 30 branches and loads them | Every account gets the same realistic data, no real data involved |
| Views and grants | Curated views in schema `mcp`; a read-only database role `mcp_reader` | The MCP server may read only these views (Day 1 Module 02) |
| `rst-mcp-task-<region>` role | IAM role for the MCP server (ECS on Day 1, AgentCore on Day 2), mapped to `mcp_reader` | The server reads Redshift without any keys in code |
| Your laptop role | The role(s) in `localDevRoleNames`, also mapped to `mcp_reader` | Local MCP servers get the same read-only access |
| Secret and bucket | Redshift admin password (Secrets Manager), S3 bucket for loading the data | Used by the loader only |

Outputs you may need: `WorkgroupName`, `DatabaseName`.

**`RstAuthStack`: the user directory** (under a minute)

| Part | What it is | Why |
|---|---|---|
| Cognito user pool `rst-workshop` | Users with two extra attributes, `custom:role` (`hq`, `manager`, `staff`) and `custom:branch_id`. No self sign-up | The test users sign in here (Day 1 Module 06) |
| Pre-token trigger | A small Lambda that copies role and branch into each access token | The MCP server reads them to limit each user to their own branch |
| Sign-in domain (shared account only, `-c sharedDomain=true`) | The user pool's hosted sign-in pages | A user pool has only one domain, so the instructor creates it for everyone |

Outputs: `UserPoolId` (for the test users below), `OidcIssuer`, and `CognitoDomain` with `-c sharedDomain=true`. App clients and scopes are **not** created here: participants build them by hand in Module 06. In a one-account-per-participant setup, `-c fullAuth=true` creates the domain, clients and scopes too, as a catch-up for anyone who falls behind.

**Cost:** mostly the NAT gateway (charged per hour) and Redshift Serverless (charged only while queries run). Cognito and Lambda cost little or nothing at workshop scale.

### Shared account: steps

> **Not yet tested end to end.** Shared-account mode is new; the one-account-per-participant steps below are the tested path. Please report anything that doesn't work.

- [ ] `cd infra && npm install && npx cdk bootstrap` (PowerShell: `cd infra; npm install; npx cdk bootstrap`)
- [ ] `npx cdk deploy RstDataStack -c seedEndDate=<YYYY-MM-DD> -c localDevRoleNames=<participant role>` (about 5 min). See [seedEndDate and localDevRoleNames](#seedenddate-and-localdevrolenames). In a shared account `<participant role>` is the role everyone signs in with (often one IAM Identity Center or Workshop Studio role).
- [ ] `npx cdk deploy RstAuthStack -c sharedDomain=true`. Note the `UserPoolId` and `CognitoDomain` outputs and share `CognitoDomain` with participants. Pass `-c sharedDomain=true` on **every** later `RstAuthStack` deploy: leaving it out removes the domain.
- [ ] [Create the test users](#create-the-test-users) once. Everyone shares them.
- [ ] Give each participant access: an IAM Identity Center user (or a role) that can deploy CDK stacks through the bootstrap roles (`cdk-hnb659fds-*`), push container images to ECR, and use the Cognito, ECS, CloudFormation and CloudWatch consoles.
- [ ] Give each participant a **participant name**: 2–20 lowercase letters and digits, starting with a letter, no `-` or `_` (for example `alice` or `bob2`). It goes into their stack name, `RstMcpStack-<name>`, and their Cognito resources.
- [ ] Optional: [Amazon Quick](#amazon-quick-optional) with participants as Enterprise users
- [ ] Go through the [shared account checklist](#shared-account-checklist)

### One account per participant: steps

Repeat in every account (or once, when self-paced):

- [ ] `cd infra && npm install && npx cdk bootstrap` (PowerShell: `cd infra; npm install; npx cdk bootstrap`)
- [ ] `npx cdk deploy RstDataStack -c seedEndDate=<YYYY-MM-DD> -c localDevRoleNames=<participant role>` (about 5 min). See [seedEndDate and localDevRoleNames](#seedenddate-and-localdevrolenames).
- [ ] `npx cdk deploy RstAuthStack`. Note the `UserPoolId` output.
- [ ] [Create the test users](#create-the-test-users)
- [ ] Optional: [Amazon Quick](#amazon-quick-optional) with participants as Enterprise users
- [ ] Delete the stacks when you finish: `npx cdk destroy --all` from `infra/` (one account per participant only).

### seedEndDate and localDevRoleNames

- `seedEndDate` is the last day of mock orders, as `YYYY-MM-DD` (for example `2026-10-05`): use the day before the workshop, so "yesterday" has data. Leave it out and the first deploy uses yesterday (UTC). Later deploys keep the loaded data unless you pass a new, different date on purpose (that reloads all data).
- `localDevRoleNames` is the role name from step 3 of [Set up your AWS profile](#set-up-your-aws-profile) (the role people use on their laptops), so local MCP servers get the same read-only database access. Several roles: separate with commas.

### Create the test users

From the workshop folder (not `infra/`): `python scripts/create_test_users.py <UserPoolId>` (PowerShell: `py scripts/create_test_users.py <UserPoolId>`). It asks for one password for all test users (8+ characters, with a lowercase letter, an uppercase letter, a number and a symbol):

- `analyst_hq` — `custom:role=hq`, no branch restriction
- `manager_branch_12` — `custom:role=manager`, `custom:branch_id=12`
- `staff_branch_12` — `custom:role=staff`, `custom:branch_id=12`
- `manager_branch_5` — `custom:role=manager`, `custom:branch_id=5`

### Shared account checklist

- [ ] **Service Quotas** (console → Service Quotas), for N participants plus some headroom:
    - **Fargate On-Demand vCPU:** each participant runs 4 small tasks (0.25 vCPU each), about 1 vCPU per participant, so at least N + 2.
    - **CloudFront:** 1 distribution and 1 VPC origin per participant.
    - **Application Load Balancers:** 1 per participant (internal).
- [ ] **Cost:** shared once for the group: one NAT gateway, one Redshift Serverless. Per participant: an internal load balancer, 4 small Fargate tasks and a CloudFront distribution, from Module 05 until they delete their stack.
- [ ] **Safety rules** (tell participants at the start):
    - Deploy and delete **only your own stack**: `RstMcpStack-<name>`, always with `-c participant=<name>` and `--exclusively`.
    - Delete it with `npx cdk destroy RstMcpStack-<name> -c participant=<name>`.
    - Never run `npx cdk destroy --all` in a shared account: it deletes everyone's data and sign-in.
    - Only the instructor deploys or changes `RstDataStack` and `RstAuthStack`.
- [ ] **Clean-up after the event (instructor):** delete any `RstMcpStack-*` stacks left, then `RstAuthStack`, then `RstDataStack`.

### Before Day 1 (both modes)

- [ ] AgentCore available in the region (Days 2 and 3)
- [ ] Amazon Bedrock model access enabled for the Day 3 agent model (including any one-time model use-case form)
- [ ] Mock API and Promotions service: nothing to do, participants deploy them as part of their MCP stack (Module 05)
- [ ] In an instructor-led event, instructors may hold back `solutions/` and hand it out as catch-up.

## Amazon Quick (optional)

Quick appears in Day 1 Module 06 Part C and the Module 07 demo, and in the Quick parts of Days 2 and 3. **Without Quick, do the same steps in Kiro**: the guides show both, and every checkpoint can be met with Kiro.

- **What is needed:** an Amazon Quick account, and each participant as an **Enterprise** user (the "Author Pro" role). Quick requires the Enterprise subscription for MCP connectors.
- **Any account works:** Quick connects to each participant's MCP server over its public HTTPS URL, so it does not have to be in the participant's sandbox account. A group can share one Quick account.
- **Cost:** Enterprise is a monthly per-user subscription, unlike the hourly AWS resources. Check [Amazon Quick pricing](https://aws.amazon.com/quick/pricing/) and remove the users (or the subscription) after the workshop.
- **Check before the event:** sign in, open **Connectors → Create**, and confirm **Model Context Protocol** is offered. The pre-event check (`--aws`) does not test this.

## Day 3 dependencies

- [ ] `agent/` starter and `solutions/agent/` install with `uv sync` (pulls `strands-agents` and the MCP client)
- [ ] Pinned `strands-agents` version supports the approval hook used in [day3/03-human-approval.md](day3/03-human-approval.md)
- [ ] Write tools `issue_refund` and `request_stock_transfer` available (reference `solutions/mcp-server`, or via Gateway from Day 2)
- [ ] `evals/` question set and scoring script run against the local MCP server before the event

## Instructor dry-run

- [ ] Full Day 1 run by someone with analyst profile
- [ ] Quick user auth works end-to-end with Cognito
- [ ] Kiro remote MCP works with OAuth sign-in and with a bearer header
- [ ] Day 2 Runtime + Gateway reachable from Kiro with a bearer token (Quick optional, not yet tested)
- [ ] Bedrock model access for `global.anthropic.claude-sonnet-5-5` in the workshop accounts (Day 3)
- [ ] Full Day 3 run by someone with analyst profile; agent approval flow and scoring script work end to end
- [ ] Shared account: two participants deploy `RstMcpStack-<name>` side by side and both pass the Module 06 checkpoint
