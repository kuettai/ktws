import * as path from 'path';
import { CfnOutput, Duration, Stack, StackProps } from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

const ROOT = path.join(__dirname, '../..');

export interface McpStackProps extends StackProps {
  vpc: ec2.IVpc;
  mcpTaskRole: iam.IRole;
  workgroupName: string;
  database: string;
  /** Path to the MCP server to deploy, relative to infra/. ../mcp-server or ../solutions/mcp-server */
  mcpServerDir: string;
  cpuArch: 'ARM64' | 'X86_64';
  /** Empty until Module 06: auth disabled. */
  oidcIssuer: string;
  oidcAllowedAudiences: string;
  /** Scope the server requires (RstAuthStack output ReadScope). Empty: rst-mcp/read. */
  oidcRequiredScopes: string;
}

/**
 * Internet -> CloudFront (HTTPS, *.cloudfront.net) -> VPC origin -> internal ALB -> ECS Fargate MCP server
 *                                                                   ECS: mock-api, legacy-app (Cloud Map, internal)
 * The ALB is never public. CloudFront provides HTTPS without a custom domain or ACM certificate.
 */
export class McpStack extends Stack {
  constructor(scope: Construct, id: string, props: McpStackProps) {
    super(scope, id, props);
    const { vpc } = props;
    const appSubnets = { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS };
    const arch = props.cpuArch === 'ARM64'
      ? { platform: Platform.LINUX_ARM64, runtime: ecs.CpuArchitecture.ARM64 }
      : { platform: Platform.LINUX_AMD64, runtime: ecs.CpuArchitecture.X86_64 };

    const cluster = new ecs.Cluster(this, 'Cluster', {
      vpc,
      containerInsightsV2: ecs.ContainerInsights.ENABLED,
      defaultCloudMapNamespace: { name: 'rst.local', useForServiceConnect: false },
    });

    const opsApiKey = new secretsmanager.Secret(this, 'OpsApiKey', {
      generateSecretString: { excludePunctuation: true, passwordLength: 32 },
    });
    const promoToken = new secretsmanager.Secret(this, 'PromoApiToken', {
      generateSecretString: { excludePunctuation: true, passwordLength: 32 },
    });

    const service = (name: string, dir: string, port: number, opts: {
      env?: Record<string, string>;
      secrets?: Record<string, ecs.Secret>;
      taskRole?: iam.IRole;
      desiredCount?: number;
      cloudMap?: boolean;
    }) => {
      const task = new ecs.FargateTaskDefinition(this, `${name}Task`, {
        cpu: 256,
        memoryLimitMiB: 512,
        taskRole: opts.taskRole,
        runtimePlatform: { cpuArchitecture: arch.runtime, operatingSystemFamily: ecs.OperatingSystemFamily.LINUX },
      });
      task.addContainer('app', {
        image: ecs.ContainerImage.fromAsset(path.join(ROOT, dir), { platform: arch.platform }),
        portMappings: [{ containerPort: port }],
        environment: opts.env,
        secrets: opts.secrets,
        logging: ecs.LogDrivers.awsLogs({
          streamPrefix: name,
          logGroup: new logs.LogGroup(this, `${name}Logs`, { retention: logs.RetentionDays.ONE_WEEK }),
        }),
      });
      return new ecs.FargateService(this, `${name}Service`, {
        cluster,
        taskDefinition: task,
        desiredCount: opts.desiredCount ?? 1,
        minHealthyPercent: 100,
        vpcSubnets: appSubnets,
        circuitBreaker: { rollback: true },
        cloudMapOptions: opts.cloudMap ? { name } : undefined,
      });
    };

    // ---- Simulated internal applications --------------------------------------------------
    const mockApi = service('mock-api', 'mock-api', 8080, {
      env: { MOCK_TZ: 'UTC' },
      secrets: { MOCK_API_KEY: ecs.Secret.fromSecretsManager(opsApiKey) },
      cloudMap: true,
    });
    const legacyApp = service('legacy-app', 'legacy-app', 8081, {
      env: { TZ: 'UTC' },
      secrets: { SVC_TKN: ecs.Secret.fromSecretsManager(promoToken) },
      cloudMap: true,
    });

    // ---- Load balancer + CloudFront ---------------------------------------------------------
    const alb = new elbv2.ApplicationLoadBalancer(this, 'Alb', {
      vpc,
      internetFacing: false,
      vpcSubnets: appSubnets,
      idleTimeout: Duration.seconds(120),
    });
    // CloudFront VPC origin ENIs live in the VPC; nothing outside the VPC can reach the ALB.
    alb.connections.allowFrom(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(80), 'CloudFront VPC origin');

    const distribution = new cloudfront.Distribution(this, 'Cdn', {
      comment: 'restaurant MCP server',
      defaultBehavior: {
        origin: origins.VpcOrigin.withApplicationLoadBalancer(alb, {
          protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
          readTimeout: Duration.seconds(60),
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        // Forwards all viewer headers except Host. CloudFront forwards Authorization on POST,
        // which is what Streamable HTTP uses for every MCP call.
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      },
    });
    const publicUrl = `https://${distribution.distributionDomainName}/mcp`;

    // ---- MCP server -------------------------------------------------------------------------
    const authEnv: Record<string, string> = props.oidcIssuer
      ? {
        OIDC_ISSUER: props.oidcIssuer,
        OIDC_ALLOWED_AUDIENCES: props.oidcAllowedAudiences,
        OIDC_REQUIRED_SCOPES: props.oidcRequiredScopes || 'rst-mcp/read',
        MCP_PUBLIC_URL: publicUrl,
      }
      : {};
    const mcp = service('mcp-server', props.mcpServerDir, 8000, {
      taskRole: props.mcpTaskRole,
      desiredCount: 2,
      env: {
        MCP_TRANSPORT: 'http',
        AWS_REGION: this.region,
        REDSHIFT_WORKGROUP: props.workgroupName,
        REDSHIFT_DATABASE: props.database,
        OPS_API_BASE_URL: 'http://mock-api.rst.local:8080',
        PROMO_API_BASE_URL: 'http://legacy-app.rst.local:8081',
        ...authEnv,
      },
      secrets: {
        OPS_API_KEY: ecs.Secret.fromSecretsManager(opsApiKey),
        PROMO_API_TOKEN: ecs.Secret.fromSecretsManager(promoToken),
      },
    });
    for (const backend of [mockApi, legacyApp]) {
      backend.connections.allowFrom(mcp, ec2.Port.allTcp(), 'MCP server');
    }

    alb.addListener('Http', { port: 80 }).addTargets('Mcp', {
      port: 8000,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [mcp],
      healthCheck: { path: '/health', healthyHttpCodes: '200' },
      deregistrationDelay: Duration.seconds(10),
    });

    new CfnOutput(this, 'McpUrl', { value: publicUrl });
    new CfnOutput(this, 'McpPublicUrlNote', {
      value: props.oidcIssuer ? 'Auth ENABLED' : 'Auth DISABLED - public and unauthenticated until Module 06',
    });
    new CfnOutput(this, 'OpsApiKeySecretArn', { value: opsApiKey.secretArn });
    new CfnOutput(this, 'PromoApiTokenSecretArn', { value: promoToken.secretArn });
  }
}
