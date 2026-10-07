# AgentCore cheat sheet (Days 2–3)

Everything you create on Days 2 and 3, how to find it again, and how to delete it. Commands assume `AWS_PROFILE` and `AWS_REGION` are set.

## Two command-line tools

| Tool | Install | Used for |
|---|---|---|
| **AgentCore CLI** (`agentcore`) | `npm install -g @aws/agentcore@0.31` | Runtimes: `create`, `add agent`, `deploy`, `status`, `logs`, `invoke`. Works in a project folder (`rstday2/`, `rstday3/`) and deploys with CloudFormation |
| **AWS CLI** (`aws bedrock-agentcore-control ...`) | AWS CLI v2.34+ | Gateway, targets, credential providers, policies. Reads its settings from JSON files with `--cli-input-json file://...` |

`--cli-input-json file://rstday2/gateway/gateway.json` means "take all the options from this file". `scripts/make_gateway_inputs.py` writes those files for you.

## What you create

| Day / module | Thing | Name | Created with |
|---|---|---|---|
| D2 M02 | Runtime (your MCP server) | `rstday2_RstMcp` | `agentcore deploy` in `rstday2/` |
| D2 M03 | Stack: Gateway role + interceptor | `RstAgentCoreStack` | `npx cdk deploy` |
| D2 M03 | API key credential provider | `rst-ops-api-key` | `aws ... create-api-key-credential-provider` |
| D2 M03 | OAuth credential provider | `rst-runtime-s2s` | `aws ... create-oauth2-credential-provider` |
| D2 M03 | Gateway | `rst-gateway` (ID `rst-gateway-<random>`) | `aws ... create-gateway` |
| D2 M03 | Gateway targets | `OpsApi`, `RstMcp` | `aws ... create-gateway-target` |
| D2 M05 | Policy engine + 4 policies | `rst_policy_engine` | `aws ... create-policy-engine`, `create-policy` |
| D2 M05 | Log deliveries + log group | `rst-gateway-logs`, `rst-gateway-traces` | `aws logs ...` |
| D3 M05 | Runtime (the agent) | `rstday3_RstAgent` | `agentcore deploy` in `rstday3/` |

Shared account: the same names with your participant name added (the scripts print them).

## Find things again

```bash
agentcore status                                   # in rstday2/ or rstday3/: runtime state and URL
aws bedrock-agentcore-control list-agent-runtimes --query "agentRuntimes[].[agentRuntimeName,status]" --output table
aws bedrock-agentcore-control list-gateways --query "items[].[name,gatewayId,status]" --output table
aws bedrock-agentcore-control get-gateway --gateway-identifier $GATEWAY_ID --query "[gatewayUrl,gatewayArn]" --output text
aws bedrock-agentcore-control list-gateway-targets --gateway-identifier $GATEWAY_ID --query "items[].[name,targetId,status]" --output table
aws bedrock-agentcore-control list-policy-engines --query "policyEngines[].[name,policyEngineId,status]" --output table
aws bedrock-agentcore-control list-policies --policy-engine-id $ENGINE_ID --query "policies[].[name,status]" --output table
```

```powershell
agentcore status                                   # in rstday2/ or rstday3/: runtime state and URL
aws bedrock-agentcore-control list-agent-runtimes --query "agentRuntimes[].[agentRuntimeName,status]" --output table
aws bedrock-agentcore-control list-gateways --query "items[].[name,gatewayId,status]" --output table
aws bedrock-agentcore-control get-gateway --gateway-identifier $env:GATEWAY_ID --query "[gatewayUrl,gatewayArn]" --output text
aws bedrock-agentcore-control list-gateway-targets --gateway-identifier $env:GATEWAY_ID --query "items[].[name,targetId,status]" --output table
aws bedrock-agentcore-control list-policy-engines --query "policyEngines[].[name,policyEngineId,status]" --output table
aws bedrock-agentcore-control list-policies --policy-engine-id $env:ENGINE_ID --query "policies[].[name,status]" --output table
```

The **Runtime MCP URL** is the `agentcore status` URL with `?qualifier=DEFAULT` added. The **Gateway URL** ends in `/mcp`.

## Logs and traces

| What | Where |
|---|---|
| Your MCP server or agent on Runtime | `agentcore logs --runtime <name> --since 15m`, or log group `/aws/bedrock-agentcore/runtimes/<runtime id>-DEFAULT` |
| Gateway requests | Log group `/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/<gateway id>` (after D2 M05 Part B) |
| Gateway spans (token check, interceptor, policy, target) | CloudWatch Logs Insights on `aws/spans` |
| Agent sessions and traces | CloudWatch → GenAI Observability → Bedrock AgentCore |

## Delete everything (in this order)

1. **Day 3 agent:** in `rstday3/`: `agentcore remove all -y`, then `agentcore deploy -y`.
2. **Policy:** detach the engine from the Gateway, then delete the policies and the engine:

    ```bash
    aws bedrock-agentcore-control update-gateway --gateway-identifier $GATEWAY_ID --cli-input-json file://rstday2/gateway/gateway.json
    aws bedrock-agentcore-control list-policies --policy-engine-id $ENGINE_ID --query "policies[].policyId" --output text
    aws bedrock-agentcore-control delete-policy --policy-engine-id $ENGINE_ID --policy-id <policy id>   # each one
    aws bedrock-agentcore-control delete-policy-engine --policy-engine-id $ENGINE_ID
    ```

3. **Gateway logs and traces:**

    ```bash
    aws logs describe-deliveries --query "deliveries[].[id,deliverySourceName]" --output text
    aws logs delete-delivery --id <delivery id>                      # each one
    aws logs delete-delivery-source --name rst-gateway-logs
    aws logs delete-delivery-source --name rst-gateway-traces
    aws logs delete-delivery-destination --name rst-gateway-logs
    aws logs delete-delivery-destination --name rst-gateway-traces
    aws logs delete-log-group --log-group-name /aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/$GATEWAY_ID
    ```

4. **Gateway:** targets first, then the Gateway, then the credential providers:

    ```bash
    aws bedrock-agentcore-control delete-gateway-target --gateway-identifier $GATEWAY_ID --target-id <target id>   # each one
    aws bedrock-agentcore-control delete-gateway --gateway-identifier $GATEWAY_ID
    aws bedrock-agentcore-control delete-api-key-credential-provider --name rst-ops-api-key
    aws bedrock-agentcore-control delete-oauth2-credential-provider --name rst-runtime-s2s
    ```

5. **Day 2 runtime:** in `rstday2/`: `agentcore remove all -y`, then `agentcore deploy -y`.
6. **Stacks:** from `infra/`: `npx cdk destroy RstAgentCoreStack`, then the Day 1 stacks (see [CDK infrastructure](infra.md)).

The PowerShell commands are the same; only the comment marker differs.
