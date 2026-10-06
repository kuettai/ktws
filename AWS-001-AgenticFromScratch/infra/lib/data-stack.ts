import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import { CfnOutput, CustomResource, Duration, RemovalPolicy, Stack, StackProps, Tags } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as redshift from 'aws-cdk-lib/aws-redshiftserverless';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as cr from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';

const DATA_DIR = path.join(__dirname, '../../data');
const SEED_LAMBDA_DIR = path.join(__dirname, '../lambda/seed');

export interface DataStackProps extends StackProps {
  /** Last day of mock history. Set to the day before the workshop. */
  seedEndDate: string;
  /** Extra IAM role names (e.g. Workshop Studio participant role) mapped to mcp_reader. */
  localDevRoleNames: string[];
}

/**
 * VPC, Redshift Serverless with seeded mock data, and the MCP server's IAM task role
 * (created here so the seed step can grant it the mcp_reader database role).
 */
export class DataStack extends Stack {
  readonly vpc: ec2.Vpc;
  readonly mcpTaskRole: iam.Role;
  readonly workgroupName = 'rst-workshop';
  readonly database = 'dev';

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);

    this.vpc = new ec2.Vpc(this, 'Vpc', {
      // Redshift Serverless needs subnets in 3 AZs. Explicit AZs avoid a context lookup.
      availabilityZones: ['a', 'b', 'c'].map((z) => `${this.region}${z}`),
      natGateways: 1,
      subnetConfiguration: [
        { name: 'public', subnetType: ec2.SubnetType.PUBLIC },
        { name: 'app', subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        { name: 'data', subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });

    const seedBucket = new s3.Bucket(this, 'SeedBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const adminSecret = new secretsmanager.Secret(this, 'RedshiftAdmin', {
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'rstadmin' }),
        generateStringKey: 'password',
        passwordLength: 32,
        excludeCharacters: `"'@/\\ `,
        requireEachIncludedType: true,
      },
    });

    const copyRole = new iam.Role(this, 'RedshiftCopyRole', {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('redshift.amazonaws.com'),
        new iam.ServicePrincipal('redshift-serverless.amazonaws.com'),
      ),
    });
    seedBucket.grantRead(copyRole);

    const namespace = new redshift.CfnNamespace(this, 'Namespace', {
      namespaceName: 'rst-workshop',
      dbName: this.database,
      adminUsername: 'rstadmin',
      adminUserPassword: adminSecret.secretValueFromJson('password').unsafeUnwrap(),
      iamRoles: [copyRole.roleArn],
      defaultIamRoleArn: copyRole.roleArn,
    });

    const sg = new ec2.SecurityGroup(this, 'RedshiftSg', { vpc: this.vpc, allowAllOutbound: false });
    const workgroup = new redshift.CfnWorkgroup(this, 'Workgroup', {
      workgroupName: this.workgroupName,
      namespaceName: namespace.namespaceName,
      baseCapacity: 8,
      publiclyAccessible: false,
      subnetIds: this.vpc.isolatedSubnets.map((s) => s.subnetId),
      securityGroupIds: [sg.securityGroupId],
      configParameters: [{ parameterKey: 'max_query_execution_time', parameterValue: '60' }],
    });
    workgroup.addResourceDependency(namespace);

    const workgroupArn = workgroup.attrWorkgroupWorkgroupArn;

    // MCP server identity. Tag maps IAM role to the mcp_reader DB role; the seed step
    // also creates the IAMR: user and grants the role explicitly.
    this.mcpTaskRole = new iam.Role(this, 'McpTaskRole', {
      roleName: `rst-mcp-task-${this.region}`,
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
        new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'), // Day 2 Runtime
      ),
    });
    Tags.of(this.mcpTaskRole).add('RedshiftDbRoles', 'mcp_reader');
    this.mcpTaskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['redshift-data:ExecuteStatement', 'redshift-serverless:GetCredentials'],
      resources: [workgroupArn],
    }));
    this.mcpTaskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['redshift-data:DescribeStatement', 'redshift-data:GetStatementResult', 'redshift-data:CancelStatement'],
      resources: ['*'], // statement-level APIs; callers can only see their own statements
    }));

    const seedFn = new lambda.Function(this, 'SeedFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.on_event',
      memorySize: 2048,
      timeout: Duration.minutes(14),
      code: lambda.Code.fromAsset(SEED_LAMBDA_DIR, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: ['bash', '-c', 'cp -r /asset-input/* /asset-output/'],
          local: {
            // Copy handler + data/ files without Docker.
            tryBundle(outputDir: string) {
              fs.copyFileSync(path.join(SEED_LAMBDA_DIR, 'handler.py'), path.join(outputDir, 'handler.py'));
              for (const f of ['generate_seed.py', 'ddl.sql', 'copy.sql', 'views.sql', 'grants.sql']) {
                fs.copyFileSync(path.join(DATA_DIR, f), path.join(outputDir, f));
              }
              return true;
            },
          },
        },
      }),
    });
    seedBucket.grantPut(seedFn);
    adminSecret.grantRead(seedFn);
    seedFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['redshift-data:ExecuteStatement', 'redshift-data:DescribeStatement'],
      resources: ['*'],
    }));

    const seed = new CustomResource(this, 'Seed', {
      serviceToken: new cr.Provider(this, 'SeedProvider', { onEventHandler: seedFn }).serviceToken,
      properties: {
        WorkgroupName: this.workgroupName,
        Database: this.database,
        AdminSecretArn: adminSecret.secretArn,
        SeedBucket: seedBucket.bucketName,
        SeedEndDate: props.seedEndDate,
        ReaderRoleNames: [this.mcpTaskRole.roleName, ...props.localDevRoleNames].join(','),
        // Re-run the seed when SQL or generator changes
        DataHash: fs.readdirSync(DATA_DIR).sort()
          .reduce((h, f) => h.update(fs.readFileSync(path.join(DATA_DIR, f))), crypto.createHash('sha256'))
          .digest('hex'),
      },
    });
    seed.node.addDependency(workgroup);

    new CfnOutput(this, 'WorkgroupName', { value: this.workgroupName });
    new CfnOutput(this, 'DatabaseName', { value: this.database });
    new CfnOutput(this, 'AdminSecretArn', { value: adminSecret.secretArn });
  }
}
