# D1 M05 — Deploy to ECS (30m)

## Objectives
- Deploy MCP server to ECS Fargate with pre-built CDK.
- Understand each component and why it is there.

## Pre-built (`infra/`)
`RstDataStack` and `RstAuthStack` are already deployed in your account. You deploy `RstMcpStack`.

## Architecture diagram

```mermaid
flowchart TB
    client["Quick / Kiro<br/>(MCP client)"]
    cognito["Amazon Cognito<br/>user pool<br/>(RstAuthStack, M06)"]

    subgraph aws["Your AWS account"]
        cf["CloudFront<br/>https://&lt;id&gt;.cloudfront.net/mcp"]
        subgraph vpc["VPC (RstDataStack)"]
            subgraph app["Private app subnets"]
                alb["Internal ALB<br/>(not public)"]
                mcp["ECS Fargate: mcp-server<br/>2 tasks, task role"]
                ops["ECS: mock-api<br/>mock-api.rst.local:8080"]
                promo["ECS: legacy-app<br/>legacy-app.rst.local:8081"]
            end
            subgraph data["Private data subnets"]
                rs["Redshift Serverless<br/>DB role mcp_reader"]
            end
            nat["NAT gateway<br/>(outbound only)"]
        end
        sm["Secrets Manager<br/>Ops API key, Promo token"]
        cw["CloudWatch Logs"]
    end

    client -- "HTTPS + bearer token" --> cf
    client -. "sign in, get token (M06)" .-> cognito
    cf -- "VPC origin" --> alb --> mcp
    mcp -- "Redshift Data API" --> rs
    mcp -- "Cloud Map DNS" --> ops
    mcp -- "Cloud Map DNS" --> promo
    mcp -. "checks token signature (M06)" .-> cognito
    sm -. "injected as env vars" .-> mcp
    mcp -.-> cw
    mcp -. "AWS APIs" .-> nat
```

Open full size: [PNG](img/diagrams/05-deploy-ecs-1.png) · [SVG](img/diagrams/05-deploy-ecs-1.svg)

| Box | What it is | Why it's there | What if it were missing |
|---|---|---|---|
| CloudFront | HTTPS front door with a `*.cloudfront.net` certificate | Quick only connects to HTTPS. No custom domain or certificate needed | You would need a domain and an ACM certificate, or tokens would travel over plain HTTP |
| Internal ALB | Load balancer inside the VPC | Spreads requests over the 2 MCP server tasks; only CloudFront can reach it | Exposing tasks directly would put them on the internet |
| ECS Fargate: mcp-server | Your MCP server container, 2 tasks | Runs without servers to manage; 2 tasks survive one failing | A single task means downtime on every deploy or crash |
| Task role | IAM role the containers run as | No AWS keys in code or env vars; maps to the read-only `mcp_reader` database role | Someone would paste access keys into config |
| mock-api, legacy-app | The internal Ops API and Promotions service, found by name through Cloud Map | Stand-ins for internal systems the MCP server wraps (M03) | The API tools would have nothing to call |
| Redshift Serverless | The data warehouse, in isolated subnets | History for the Redshift tools (M02); `mcp_reader` can only read the `mcp` views | — |
| Secrets Manager | Stores the Ops API key and Promo token | ECS injects them at start-up, so they never sit in code | Secrets end up in the image or the repo |
| NAT gateway | Outbound-only internet path for private subnets | Lets tasks reach AWS APIs (Redshift Data API, Secrets Manager, logs) | Tasks can't call AWS services without VPC endpoints |
| CloudWatch Logs | Container logs | Where you debug tool calls and sign-in errors | You are blind when something fails |
| Cognito (M06) | Issues and signs user and service tokens | The server checks every token, then uses role and branch claims to limit data | Anyone with the URL can call the tools (the state right after this module) |

## Steps
1. **Start the deploy first** (it takes about 15 minutes, most of it CloudFront). Needs Docker or Finch to build images; with Finch set `CDK_DOCKER=finch`. Set the profile and region explicitly in this terminal: without them the deploy uses your default credentials, and a stale `AWS_REGION` overrides the profile's region, both sending the deploy to the wrong place. Use your own profile name if it isn't `workshop`, and check the account with `aws sts get-caller-identity` before deploying.

    ```bash
    export AWS_PROFILE=workshop AWS_REGION=<workshop region> CDK_DEFAULT_REGION=<workshop region>
    aws sts get-caller-identity                                          # the account you are about to deploy into
    export CDK_DOCKER=finch                                              # only if you use Finch
    cd infra && npm install
    npx cdk deploy RstMcpStack                                           # your server from ../mcp-server
    npx cdk deploy RstMcpStack -c mcpServerDir=../solutions/mcp-server   # catch-up: reference solution
    ```

    ```powershell
    $env:AWS_PROFILE = "workshop"; $env:AWS_REGION = "<workshop region>"; $env:CDK_DEFAULT_REGION = "<workshop region>"
    aws sts get-caller-identity                                          # the account you are about to deploy into
    $env:CDK_DOCKER = "finch"                                            # only if you use Finch
    cd infra; npm install
    npx cdk deploy RstMcpStack                                           # your server from ../mcp-server
    npx cdk deploy RstMcpStack -c mcpServerDir=../solutions/mcp-server   # catch-up: reference solution
    ```

    **Shared account?** If your instructor gave you a participant name (for example `alice`), use your own stack name and pass the name, so you don't overwrite anyone else's server. `--exclusively` deploys only your stack, not the shared data stack it builds on:

    ```bash
    npx cdk deploy RstMcpStack-<name> --exclusively -c participant=<name>
    npx cdk deploy RstMcpStack-<name> --exclusively -c participant=<name> -c mcpServerDir=../solutions/mcp-server   # catch-up
    ```

    ```powershell
    npx cdk deploy RstMcpStack-<name> --exclusively -c participant=<name>
    npx cdk deploy RstMcpStack-<name> --exclusively -c participant=<name> -c mcpServerDir=../solutions/mcp-server   # catch-up
    ```

    Use the **same** participant name on every later deploy (Module 06 too), and wherever the guides say `RstMcpStack`, read `RstMcpStack-<name>`.

2. While it deploys, walk through the [architecture diagram](#architecture-diagram) (10m, while the deploy runs). For each box: what, why, what if missing (see the table under the diagram).
3. Still waiting: tour the ECS console, CloudWatch log groups, task role permissions, Secrets Manager.

    > **Screenshot** — `<SCREENSHOT_YET_TO_PREPARE>` ECS console: the cluster with mcp-server, mock-api and legacy-app services running · save as `img/m05-ecs-services.png`

4. Test: Inspector → `McpUrl` stack output. **Note the `McpUrl` value**: M06 uses it as the OAuth resource identifier.

    > **Screenshot** — `<SCREENSHOT_YET_TO_PREPARE>` CloudFormation `RstMcpStack` Outputs tab with `McpUrl` · save as `img/m05-stack-outputs.png`

## Key concepts
- **HTTPS without a domain.** CloudFront gives a `*.cloudfront.net` certificate. Quick only connects to HTTPS endpoints; tokens must never travel over plain HTTP.
- **ALB is internal.** Only CloudFront (via VPC origin) can reach it.
- **Task role, not keys.** No AWS credentials in code or env vars. The role is mapped to the read-only `mcp_reader` database role.
- **Secrets Manager** holds the Ops API key and Promo token; ECS injects them as env vars.

## Checkpoint
Remote endpoint answers in Inspector. It is **public and unauthenticated** right now (stack output says so) — move to M06 immediately. If the session breaks here, run `npx cdk destroy RstMcpStack` (shared account: `npx cdk destroy RstMcpStack-<name> -c participant=<name>`, never `--all`).

## Instructor notes
- Measured deploy time: about 16 minutes for a first deploy (images, ECS, CloudFront). Redeploys that only change settings take 3–4 minutes. Start the deploy before the walkthrough, or the module overruns: in 30 minutes the walkthrough and the console tour happen while CloudFront deploys.
- The first Redshift query after the workgroup has been idle can fail with "Internal error encountered". The reference server retries that error once (`lib/redshift.py`); if a participant's own server shows it, ask again.
