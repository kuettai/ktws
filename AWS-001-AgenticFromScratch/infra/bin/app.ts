#!/usr/bin/env node
import { App } from 'aws-cdk-lib';
import { AuthStack } from '../lib/auth-stack';
import { DataStack } from '../lib/data-stack';
import { McpStack } from '../lib/mcp-stack';

const app = new App();
const ctx = (key: string): string => String(app.node.tryGetContext(key) ?? '');
const list = (key: string): string[] => ctx(key).split(',').map((s) => s.trim()).filter(Boolean);
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION };

// Pre-provisioned by the instructor / Workshop Studio
const data = new DataStack(app, 'RstDataStack', {
  env,
  seedEndDate: ctx('seedEndDate'),
  localDevRoleNames: list('localDevRoleNames'),
});
new AuthStack(app, 'RstAuthStack', {
  env,
  fullAuth: ctx('fullAuth') === 'true',
  quickCallbackUrls: list('quickCallbackUrls'),
  mcpResourceUrl: ctx('mcpResourceUrl'),
});

// Deployed by participants in Day 1 Module 05, redeployed with -c oidcIssuer=... in Module 06
new McpStack(app, 'RstMcpStack', {
  env,
  vpc: data.vpc,
  mcpTaskRole: data.mcpTaskRole,
  workgroupName: data.workgroupName,
  database: data.database,
  mcpServerDir: ctx('mcpServerDir').replace(/^\.\.\//, ''),
  cpuArch: ctx('cpuArch') === 'X86_64' ? 'X86_64' : 'ARM64',
  oidcIssuer: ctx('oidcIssuer'),
  oidcAllowedAudiences: ctx('oidcAllowedAudiences'),
  oidcRequiredScopes: ctx('oidcRequiredScopes'),
});
