#!/usr/bin/env node
import { App } from 'aws-cdk-lib';
import { AgentCoreStack } from '../lib/agentcore-stack';
import { AuthStack } from '../lib/auth-stack';
import { DataStack } from '../lib/data-stack';
import { McpStack } from '../lib/mcp-stack';

const app = new App();
const ctx = (key: string): string => String(app.node.tryGetContext(key) ?? '');
const list = (key: string): string[] => ctx(key).split(',').map((s) => s.trim()).filter(Boolean);
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION };

// Last day of mock orders, YYYY-MM-DD. Empty: the seed uses yesterday (UTC) on first deploy and
// keeps the loaded data on later deploys. Checked here so a typo fails now, not inside the deploy.
const seedEndDate = ctx('seedEndDate');
const isRealDate = (d: string) => /^\d{4}-\d{2}-\d{2}$/.test(d) && new Date(`${d}T00:00:00Z`).toISOString().startsWith(d);
if (seedEndDate && !isRealDate(seedEndDate)) {
  throw new Error(`seedEndDate must be a date as YYYY-MM-DD, e.g. 2026-10-05 (got "${seedEndDate}")`);
}

// Shared-account mode: each participant deploys their own RstMcpStack-<participant>.
const participant = ctx('participant').toLowerCase();
if (participant && !/^[a-z][a-z0-9]{1,19}$/.test(participant)) {
  throw new Error(`participant must be 2-20 lowercase letters and digits, starting with a letter (no - or _, so the name works in every AWS service) (got "${participant}")`);
}

// Pre-provisioned by the instructor / Workshop Studio
const data = new DataStack(app, 'RstDataStack', {
  env,
  seedEndDate,
  localDevRoleNames: list('localDevRoleNames'),
});
new AuthStack(app, 'RstAuthStack', {
  env,
  fullAuth: ctx('fullAuth') === 'true',
  quickCallbackUrls: list('quickCallbackUrls'),
  mcpResourceUrl: ctx('mcpResourceUrl'),
  sharedDomain: ctx('sharedDomain') === 'true',
});

// Deployed by participants in Day 1 Module 05, redeployed with -c oidcIssuer=... in Module 06
new McpStack(app, participant ? `RstMcpStack-${participant}` : 'RstMcpStack', {
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
  participant,
});

// Day 2: the Gateway's IAM role and request interceptor (Module 03)
new AgentCoreStack(app, participant ? `RstAgentCoreStack-${participant}` : 'RstAgentCoreStack', { env, participant });
