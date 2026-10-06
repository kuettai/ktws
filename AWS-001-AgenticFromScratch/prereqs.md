# Prerequisites

## Get the workshop code

Clone the repository once, then move into this workshop's folder:

```bash
git clone https://github.com/kuettai/ktws.git
cd ktws/AWS-001-AgenticFromScratch
```

```powershell
git clone https://github.com/kuettai/ktws.git
cd ktws\AWS-001-AgenticFromScratch
```

**Run every command in these guides from this folder** (`ktws/AWS-001-AgenticFromScratch`), unless a step says otherwise (for example `cd infra`). Open this same folder in Kiro.

No Git yet? Install it first (see the list below), or download the code as a ZIP from the [repository page](https://github.com/kuettai/ktws) (**Code → Download ZIP**) and unzip it.

## Participant laptop

- [ ] Kiro installed and signed in
- [ ] Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- [ ] Docker Desktop or Finch (needed from Module 04; Modules 01-03 run without it). Can't install either on your laptop? Run the Module 05 deploy from AWS CloudShell, which has Docker built in.
- [ ] AWS CLI v2
- [ ] Node.js 20+ (for `npx @modelcontextprotocol/inspector`)
- [ ] Git
- [ ] Browser access to the AWS Console and Amazon Quick (and Workshop Studio, if your event uses it)
- [ ] Pre-event check passes: `python3 scripts/rst_preflight.py --deep` (Windows: `py scripts/rst_preflight.py --deep`) (see [PREFLIGHT-CHECK.md](PREFLIGHT-CHECK.md))

### Windows

Every command in the guides has a **Windows (PowerShell)** tab next to the macOS / Linux one. Windows PowerShell 5.1, which ships with Windows 10 and 11, is enough.

- Install the tools with winget (or download them from each vendor's site):

    ```powershell
    winget install Python.Python.3.12 astral-sh.uv OpenJS.NodeJS.LTS Git.Git Amazon.AWSCLI
    ```

- Containers: Finch on Windows needs WSL2. Docker Desktop also works.
- Run commands from the workshop folder, as the guides do.
- Use `py` where the guides say `python3` for a script, e.g. `py scripts/rst_preflight.py`.
- If PowerShell refuses to run a script such as `.venv\Scripts\Activate.ps1`, allow local scripts once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Participant knowledge

- Comfortable writing SQL `SELECT` with joins and `GROUP BY`
- Basic terminal usage (cd, run commands, edit env vars)
- No Python, Docker, or OAuth experience required

## Participant pre-work (~2h, before Day 1)

- [ ] Install and check the laptop software above; sign in to Kiro once (30m)
- [ ] [Python reading primer](prework/python-reading-primer.md) (60m) — reading, not writing; Day 1 opens with a 15m recap for anyone who skipped it
- [ ] [Reviewing Kiro specs, steering and hooks](prework/kiro-guide.md) (25m)
- [ ] Optional: one or two of your own report queries, anonymised (no real data) — Day 1 tool, Day 3 test question

## Account setup

Once per **sandbox** account: done by the instructor before an event, or by yourself when self-paced. Set the region explicitly in every shell (`export AWS_REGION=<region> CDK_DEFAULT_REGION=<region>`; PowerShell: `$env:AWS_REGION = "<region>"; $env:CDK_DEFAULT_REGION = "<region>"`): a stale `AWS_REGION` overrides your profile's region.

- [ ] `cd infra && npm install && npx cdk bootstrap` (PowerShell: `cd infra; npm install; npx cdk bootstrap`)
- [ ] `npx cdk deploy RstDataStack -c seedEndDate=<day before workshop> -c localDevRoleNames=<participant role>`: VPC, Redshift Serverless, generated mock data, views and grants (about 5–10 min).
    `<participant role>` is the IAM role name people use on their laptops, so local MCP servers get the same read-only database access. Find it with `aws sts get-caller-identity`: in `arn:aws:sts::<account>:assumed-role/Admin/jane`, the role name is `Admin`.
- [ ] `npx cdk deploy RstAuthStack`: user pool, custom attributes, pre-token trigger. Note the `UserPoolId` output.
- [ ] From the workshop folder (not `infra/`): `python scripts/create_test_users.py <UserPoolId>` (PowerShell: `py scripts/create_test_users.py <UserPoolId>`). It asks for one password for all test users (12+ characters):
    - `analyst_hq` — `custom:role=hq`, no branch restriction
    - `manager_branch_12` — `custom:role=manager`, `custom:branch_id=12`
    - `staff_branch_12` — `custom:role=staff`, `custom:branch_id=12`
    - `manager_branch_5` — `custom:role=manager`, `custom:branch_id=5`
- [ ] Amazon Quick (Enterprise) enabled; participant users invited
- [ ] Mock API and Promotions service are deployed by participants as part of `RstMcpStack` (Module 05)
- [ ] AgentCore available in region (Days 2 and 3)
- [ ] Amazon Bedrock model access enabled for the Day 3 agent model (including any one-time model use-case form)
- [ ] Repo cloned. In an instructor-led event, instructors may hold back `solutions/` and hand it out as catch-up.

## Day 3 dependencies

- [ ] `agent/` starter and `solutions/agent/` install with `uv sync` (pulls `strands-agents` and the MCP client)
- [ ] Pinned `strands-agents` version supports the approval hook used in [day3/03-human-approval.md](day3/03-human-approval.md)
- [ ] Write tools `issue_refund` and `request_stock_transfer` available (reference `solutions/mcp-server`, or via Gateway from Day 2)
- [ ] `evals/` question set and scoring script run against the local MCP server before the event

## Instructor dry-run

- [ ] Full Day 1 run by someone with analyst profile
- [ ] Quick user auth works end-to-end with Cognito
- [ ] Kiro remote MCP works with OAuth sign-in and with a bearer header
- [ ] Day 2 Runtime + Gateway reachable from Quick
- [ ] Full Day 3 run by someone with analyst profile; agent approval flow and scoring script work end to end
