# MCP Workshop: Pre-event Check

Run this check on each participant laptop **at least one week before Day 1**, on the network you will use on the day (office network, with VPN on if you normally use it). This gives IT time to fix anything that is blocked.

The script is `rst_preflight.py`. It only reads: it installs nothing, changes no settings and sends no data anywhere. It takes about 1–3 minutes.

## How to run it

1. Get `scripts/rst_preflight.py` from this repository and save it to any folder, for example Downloads.
2. Open a terminal in that folder:
    - **macOS:** Terminal
    - **Windows:** PowerShell
3. Run:

    | | macOS / Linux | Windows |
    |---|---|---|
    | Standard check | `python3 rst_preflight.py --deep` | `py rst_preflight.py --deep` |

    If Python is not installed yet, install Python 3.12 or newer first (it is needed for the workshop anyway).

4. Each line shows **PASS**, **WARN** or **FAIL**. At the end the script saves `rst-preflight-report-<date>.txt` in the same folder.
5. If you attend an instructor-led event, send the report file to the instructor. It contains no passwords, keys or tokens.

## What it checks

| Area | What is checked |
|---|---|
| Software | Python 3.12+, uv, Node.js 20+, npm/npx, Git, AWS CLI v2, Docker or Finch (running), Kiro |
| Network | HTTPS access to Kiro, AWS sign-in, Workshop Studio, AWS Console, Amazon Quick, the AWS service APIs used in the labs, and package registries. Also whether a proxy re-signs HTTPS traffic to AWS |
| Local ports | 7778, 8000, 8080, 8081 and 8765 are free and reachable on `127.0.0.1` |
| Downloads (`--deep`) | Python packages from PyPI, npm packages, and one container image (`python:3.12-slim`, about 50 MB) |

## Reading the result

| Result | Meaning | Usual fix |
|---|---|---|
| **FAIL** on software | Not installed, or too old | Install it, or ask IT if you have no install rights |
| **FAIL** on a host: "DNS lookup failed" or "timed out" | The firewall or proxy blocks that site | Ask IT to allowlist the domains below |
| **FAIL** on a host: "TLS certificate not trusted" | A proxy inspects HTTPS traffic | Ask IT for an inspection exception for the domains below |
| **WARN** "HTTPS inspection on AWS traffic?" | Traffic to AWS is re-signed by a proxy | Same as above; the AWS CLI and SDKs may fail |
| **WARN** on a port | Another app is using it | Close that app before the workshop |
| **FAIL** on a port | Local security software blocks local connections | Ask IT to allow local (`127.0.0.1`) connections on those ports |

## Domains for IT to allowlist

Required unless marked optional. If your firewall matches only one subdomain level, list multi-level hosts (such as `assets.app.kiro.dev`) explicitly.

| Purpose | Domains |
|---|---|
| Kiro | `app.kiro.dev`, `assets.app.kiro.dev`, `prod.us-east-1.auth.desktop.kiro.dev`, `runtime.us-east-1.kiro.dev`, `management.us-east-1.kiro.dev`, `telemetry.us-east-1.kiro.dev`, `prod.us-east-1.telemetry.desktop.kiro.dev`, `q.us-east-1.amazonaws.com`; optional: `prod.download.desktop.kiro.dev` (updates) |
| AWS sign-in | `signin.aws`, `*.signin.aws`, `signin.aws.amazon.com`, `*.awsapps.com`, `oidc.us-east-1.amazonaws.com`, `portal.sso.us-east-1.amazonaws.com` |
| Workshop Studio | `catalog.workshops.aws`, `*.prod.workshops.aws` |
| AWS Console and Amazon Quick | `console.aws.amazon.com`, `*.console.aws.amazon.com`, `quicksight.aws.amazon.com`, `*.quicksight.aws.amazon.com` |
| AWS service APIs | `*.amazonaws.com` (or at least the `us-east-1` endpoints for STS, CloudFormation, S3, ECR, ECS, CloudWatch Logs, SSM, Secrets Manager, Lambda, IAM, Cognito, Redshift Serverless, Redshift Data, Bedrock, Bedrock AgentCore) |
| Lab sign-in pages and lab endpoints | `*.amazoncognito.com` (Cognito hosted sign-in), `*.cloudfront.net` (the participant's deployed server), `*.gateway.bedrock-agentcore.us-east-1.amazonaws.com` |
| Packages | `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, `registry-1.docker.io`, `auth.docker.io`, `production.cloudflare.docker.com`, `public.ecr.aws`; optional: `github.com`, `raw.githubusercontent.com` |

The last three lab domains are created during the workshop, so the script cannot test them in advance. Please include them in the allowlist.

Also needed:

- Browser pop-ups and redirects allowed for the AWS and Cognito sign-in pages.
- Kiro honours `HTTPS_PROXY` / `NO_PROXY`, but its browser sign-in uses the normal system network. So the Kiro and sign-in domains must be allowed at network level, not only through the proxy.

## Optional: AWS account check

Checks that your AWS sandbox account (or an instructor's test account) can reach the services the labs use. Read-only:

```bash
python3 rst_preflight.py --aws --profile <aws-profile> --region us-east-1
python3 rst_preflight.py --aws --profile <aws-profile> --invoke-model   # + one tiny Bedrock call
```

```powershell
py rst_preflight.py --aws --profile <aws-profile> --region us-east-1
py rst_preflight.py --aws --profile <aws-profile> --invoke-model   # + one tiny Bedrock call
```

This checks access to CloudFormation, CDK bootstrap, S3, ECR, ECS, load balancers, CloudFront, Lambda, Secrets Manager, CloudWatch Logs, Cognito, Redshift Serverless, Bedrock (including Claude Sonnet 5.5) and AgentCore Runtime, Gateway, Identity and Policy. The region defaults to `us-east-1`; pass `--region` for another workshop region. The report then includes the AWS account ID and role name.
