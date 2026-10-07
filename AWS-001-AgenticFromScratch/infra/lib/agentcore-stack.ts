import * as path from 'path';
import { CfnOutput, Duration, Stack, StackProps } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface AgentCoreStackProps extends StackProps {
  /** Shared-account mode: the participant's short name. Empty: one participant per account. */
  participant: string;
}

/**
 * Day 2 helpers for AgentCore Gateway: the IAM role the Gateway runs as, and the request
 * interceptor that forwards the caller's token to the MCP server target. The Gateway itself,
 * its targets and policies are created by hand in Day 2 (that is the lesson).
 */
export class AgentCoreStack extends Stack {
  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);
    const suffix = props.participant ? `-${props.participant}` : '';
    const arn = (resource: string) => `arn:aws:bedrock-agentcore:${this.region}:${this.account}:${resource}`;

    const interceptor = new lambda.Function(this, 'GatewayInterceptor', {
      functionName: `rst-gateway-interceptor${suffix}`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      timeout: Duration.seconds(5),
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/gateway_interceptor')),
    });

    const role = new iam.Role(this, 'GatewayRole', {
      roleName: `rst-gateway-role${suffix}-${this.region}`,
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com', {
        conditions: {
          StringEquals: { 'aws:SourceAccount': this.account },
          ArnLike: { 'aws:SourceArn': arn('gateway/*') },
        },
      }),
    });
    interceptor.grantInvoke(role);
    // Outbound credentials from AgentCore Identity: the Ops API key and the OAuth token for Runtime.
    role.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:GetWorkloadAccessToken', 'bedrock-agentcore:GetResourceApiKey',
        'bedrock-agentcore:GetResourceOauth2Token'],
      resources: [arn('workload-identity-directory/*'), arn('token-vault/*')],
    }));
    role.addToPolicy(new iam.PolicyStatement({
      actions: ['secretsmanager:GetSecretValue'],
      resources: [`arn:aws:secretsmanager:${this.region}:${this.account}:secret:bedrock-agentcore-identity!*`],
    }));
    // Policy (Day 2 M05): the Gateway asks the policy engine before each tool call.
    role.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:GetPolicyEngine', 'bedrock-agentcore:AuthorizeAction',
        'bedrock-agentcore:PartiallyAuthorizeActions'],
      resources: [arn('policy-engine/*'), arn('gateway/*')],
    }));

    new CfnOutput(this, 'GatewayRoleArn', { value: role.roleArn });
    new CfnOutput(this, 'InterceptorArn', { value: interceptor.functionArn });
  }
}
