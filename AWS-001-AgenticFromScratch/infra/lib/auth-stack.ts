import * as path from 'path';
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps } from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface AuthStackProps extends StackProps {
  /**
   * false (default): user pool + attributes + pre-token trigger only. Participants create the
   *   domain, resource server and app clients by hand in Day 1 Module 06 Part B.
   * true: also create them (instructor dry-run, catch-up path).
   */
  fullAuth: boolean;
  /** Quick's OAuth callback URL(s), copied from the Quick MCP integration screen. */
  quickCallbackUrls: string[];
  /**
   * The MCP server's public URL (RstMcpStack output McpUrl). MCP clients such as Kiro send it as
   * the OAuth `resource` (RFC 8707), and Cognito then only accepts scopes of a resource server
   * whose identifier is that exact URL. Set it, and the read scope becomes `<url>/read`.
   * Empty: identifier `rst-mcp`, scope `rst-mcp/read` (fine for clients that send no resource).
   */
  mcpResourceUrl: string;
}

/** Kiro IDE OAuth redirect (pinned in mcp.json `oauth.redirectUri`) and scripts/get_token.py. */
export const KIRO_CALLBACK_URLS = ['http://localhost:7778/oauth/callback', 'http://localhost:8765/callback'];

export class AuthStack extends Stack {
  readonly userPool: cognito.UserPool;

  constructor(scope: Construct, id: string, props: AuthStackProps) {
    super(scope, id, props);

    const preToken = new lambda.Function(this, 'PreTokenFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      timeout: Duration.seconds(5),
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/pre_token')),
    });

    this.userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: 'rst-workshop',
      featurePlan: cognito.FeaturePlan.ESSENTIALS, // needed to customise access tokens
      selfSignUpEnabled: false,
      signInAliases: { username: true },
      customAttributes: {
        role: new cognito.StringAttribute({ minLen: 2, maxLen: 20, mutable: true }),
        branch_id: new cognito.StringAttribute({ minLen: 1, maxLen: 10, mutable: true }),
      },
      passwordPolicy: { minLength: 12 },
      removalPolicy: RemovalPolicy.DESTROY,
    });
    this.userPool.addTrigger(
      cognito.UserPoolOperation.PRE_TOKEN_GENERATION_CONFIG, preToken, cognito.LambdaVersion.V2_0,
    );

    new CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId });
    new CfnOutput(this, 'OidcIssuer', {
      value: `https://cognito-idp.${this.region}.amazonaws.com/${this.userPool.userPoolId}`,
    });

    if (!props.fullAuth) return;

    // ---- Everything below is what participants build by hand in Module 06 Part B ----
    const domain = this.userPool.addDomain('Domain', {
      cognitoDomain: { domainPrefix: `rst-mcp-${this.account}` },
      managedLoginVersion: cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
    });

    const read = new cognito.ResourceServerScope({ scopeName: 'read', scopeDescription: 'Read restaurant data' });
    const write = new cognito.ResourceServerScope({ scopeName: 'write', scopeDescription: 'Change restaurant data (Day 2)' });
    const api = this.userPool.addResourceServer('ResourceServer', {
      identifier: props.mcpResourceUrl || 'rst-mcp', scopes: [read, write],
      userPoolResourceServerName: 'rst-mcp', // the name cannot contain ':' or '/', the identifier can
    });
    const readScope = cognito.OAuthScope.resourceServer(api, read);
    new CfnOutput(this, 'ReadScope', { value: readScope.scopeName });

    const s2s = this.userPool.addClient('QuickS2s', {
      userPoolClientName: 'quick-s2s',
      generateSecret: true,
      oAuth: { flows: { clientCredentials: true }, scopes: [readScope] },
    });

    const userClient = (id: string, name: string, callbackUrls: string[], secret: boolean) =>
      this.userPool.addClient(id, {
        userPoolClientName: name,
        generateSecret: secret,
        oAuth: {
          flows: { authorizationCodeGrant: true },
          scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE, readScope],
          callbackUrls,
        },
        accessTokenValidity: Duration.hours(1),
      });

    const quickUser = userClient('QuickUser', 'quick-user',
      props.quickCallbackUrls.length ? props.quickCallbackUrls : ['https://example.com/replace-with-quick-callback'], true);
    const kiroUser = userClient('KiroUser', 'kiro-user', KIRO_CALLBACK_URLS, false); // Kiro IDE: public clients only

    // Managed login (version 2) shows "Login pages unavailable" until each app client that signs
    // users in has a branding style. Use Cognito's default look.
    for (const [id, client] of [['QuickUserLogin', quickUser], ['KiroUserLogin', kiroUser]] as const) {
      new cognito.CfnManagedLoginBranding(this, id, {
        userPoolId: this.userPool.userPoolId,
        clientId: client.userPoolClientId,
        useCognitoProvidedValues: true,
      }).node.addDependency(domain);
    }

    new CfnOutput(this, 'CognitoDomain', { value: domain.baseUrl() });
    new CfnOutput(this, 'QuickS2sClientId', { value: s2s.userPoolClientId });
    new CfnOutput(this, 'QuickUserClientId', { value: quickUser.userPoolClientId });
    new CfnOutput(this, 'KiroUserClientId', { value: kiroUser.userPoolClientId });
    new CfnOutput(this, 'AllowedAudiences', {
      value: [s2s.userPoolClientId, quickUser.userPoolClientId, kiroUser.userPoolClientId].join(','),
    });
  }
}
