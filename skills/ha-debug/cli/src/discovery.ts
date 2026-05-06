import { SSMClient, GetParameterCommand, ParameterNotFound } from '@aws-sdk/client-ssm';
import { CognitoIdentityProviderClient, ListUserPoolsCommand } from '@aws-sdk/client-cognito-identity-provider';
import { CloudWatchLogsClient, DescribeLogGroupsCommand } from '@aws-sdk/client-cloudwatch-logs';
import type { Environment } from './auth';
import { awsClientConfig } from './aws-session';
import { DataSourceError } from './errors';

export type ResourceSource = 'ssm' | 'derived' | 'discovered' | 'env-override';

export interface ResolvedString {
  value: string;
  source: ResourceSource;
  detail?: string;
}

export interface ResolvedStringArray {
  value: string[];
  source: ResourceSource;
  detail?: string;
}

export interface CognitoPool {
  name: string;
  id: string;
}

export interface ResolvedCognitoPools {
  value: CognitoPool[];
  source: ResourceSource;
  detail?: string;
}

export interface DiscoveredResources {
  accountsTableName: ResolvedString;
  appClientsTableName: ResolvedString;
  superAdminMfaTableName: ResolvedString;
  auth0Domain: ResolvedString;
  auth0ClientId: ResolvedString;
  auth0ClientSecret: ResolvedString;
  cognitoUserPools: ResolvedCognitoPools;
  cwLogGroupNames: ResolvedStringArray;
}

export interface DiscoveryStep {
  name: string;
  ok: boolean;
  detail?: Record<string, unknown>;
  fix?: string;
}

export interface DiscoveryReport {
  steps: DiscoveryStep[];
  resources: Partial<DiscoveredResources>;
}

export interface DiscoveryContext {
  environment: Environment;
  awsRegion: string;
  awsProfile: string | null;
}

export function ssmPaths(env: Environment): {
  accountsTable: string;
  appClientsTable: string;
  superAdminMfaTable: string;
  auth0ClientId: string;
  auth0ClientSecret: string;
} {
  return {
    accountsTable: `/accounts/${env}/accountsTableName`,
    appClientsTable: `/${env}/harmony/auth/app-clients`,
    superAdminMfaTable: `/${env}/harmony/auth/super-admin-mfa`,
    auth0ClientId: `/idp/${env}/userManagement/clientId`,
    auth0ClientSecret: `/idp/${env}/userManagement/clientSecret`,
  };
}

export function derivedAuth0Domain(env: Environment): string {
  // Hostname only — the auth0 SDK's ManagementClient expects a bare hostname,
  // and our verifyToken builds `https://${domain}/oauth/token` from it.
  return `linq-accounts-${env}.us.auth0.com`;
}

export function cognitoPoolNames(env: Environment): string[] {
  return [
    `${env}-harmony-auth-district-user-pool`,
    `${env}-harmony-auth-selfSignup-user-pool`,
  ];
}

export function cwLogGroupPrefix(env: Environment): string {
  return `/aws/lambda/${env}-harmony-auth`;
}

async function getSsmParameter(client: SSMClient, name: string, withDecryption = false): Promise<string> {
  const res = await client.send(new GetParameterCommand({ Name: name, WithDecryption: withDecryption }));
  const v = res.Parameter?.Value;
  if (!v) throw new Error(`SSM parameter '${name}' returned empty value.`);
  return v;
}

function envOverride(key: string): string | undefined {
  const v = process.env[key];
  return v && v.trim() !== '' ? v.trim() : undefined;
}

function envListOverride(key: string): string[] | undefined {
  const v = envOverride(key);
  if (!v) return undefined;
  const parts = v.split(',').map(s => s.trim()).filter(Boolean);
  return parts.length > 0 ? parts : undefined;
}

export async function discoverResources(ctx: DiscoveryContext): Promise<DiscoveredResources> {
  const report = await inspectDiscovery(ctx);
  const failed = report.steps.filter(s => !s.ok);
  if (failed.length > 0) {
    const messages = failed.map(s => `[${s.name}] ${s.fix ?? 'failed'}`).join('\n');
    throw new DataSourceError(
      'discovery',
      'auth',
      false,
      report,
      `Resource discovery failed:\n${messages}\n\nRun \`ha-debug doctor --environment ${ctx.environment}\` for full setup detail.`,
    );
  }
  return report.resources as DiscoveredResources;
}

export async function inspectDiscovery(ctx: DiscoveryContext): Promise<DiscoveryReport> {
  const steps: DiscoveryStep[] = [];
  const resources: Partial<DiscoveredResources> = {};
  const paths = ssmPaths(ctx.environment);
  const ssm = new SSMClient(awsClientConfig(ctx));

  resources.accountsTableName = await resolveSsmString({
    ssm, steps,
    name: 'ssm-accounts-table',
    overrideKey: 'ACCOUNTS_TABLE_NAME',
    ssmPath: paths.accountsTable,
  });
  resources.appClientsTableName = await resolveSsmString({
    ssm, steps,
    name: 'ssm-app-clients-table',
    overrideKey: 'APP_CLIENTS_TABLE_NAME',
    ssmPath: paths.appClientsTable,
  });
  resources.superAdminMfaTableName = await resolveSsmString({
    ssm, steps,
    name: 'ssm-super-admin-mfa-table',
    overrideKey: 'SUPER_ADMIN_MFA_TABLE_NAME',
    ssmPath: paths.superAdminMfaTable,
  });
  resources.auth0ClientId = await resolveSsmString({
    ssm, steps,
    name: 'ssm-auth0-client-id',
    overrideKey: 'AUTH0_CLIENT_ID',
    ssmPath: paths.auth0ClientId,
  });
  resources.auth0ClientSecret = await resolveSsmString({
    ssm, steps,
    name: 'ssm-auth0-client-secret',
    overrideKey: 'AUTH0_CLIENT_SECRET',
    ssmPath: paths.auth0ClientSecret,
    withDecryption: true,
    secret: true,
  });

  const auth0DomainOverride = envOverride('AUTH0_DOMAIN');
  if (auth0DomainOverride) {
    resources.auth0Domain = { value: auth0DomainOverride, source: 'env-override' };
    steps.push({ name: 'auth0-domain', ok: true, detail: { source: 'env-override', value: auth0DomainOverride } });
  } else {
    const derived = derivedAuth0Domain(ctx.environment);
    resources.auth0Domain = { value: derived, source: 'derived', detail: `derived from --environment ${ctx.environment}` };
    steps.push({ name: 'auth0-domain', ok: true, detail: { source: 'derived', value: derived } });
  }

  resources.cognitoUserPools = await resolveCognitoPools({ ctx, steps });
  resources.cwLogGroupNames = await resolveCwLogGroups({ ctx, steps });

  return { steps, resources };
}

interface ResolveSsmArgs {
  ssm: SSMClient;
  steps: DiscoveryStep[];
  name: string;
  overrideKey: string;
  ssmPath: string;
  withDecryption?: boolean;
  secret?: boolean;
}

async function resolveSsmString(args: ResolveSsmArgs): Promise<ResolvedString> {
  const override = envOverride(args.overrideKey);
  if (override !== undefined) {
    args.steps.push({
      name: args.name,
      ok: true,
      detail: { source: 'env-override', overrideKey: args.overrideKey, value: args.secret ? '<redacted>' : override },
    });
    return { value: override, source: 'env-override' };
  }
  try {
    const value = await getSsmParameter(args.ssm, args.ssmPath, args.withDecryption ?? false);
    args.steps.push({
      name: args.name,
      ok: true,
      detail: {
        source: 'ssm',
        path: args.ssmPath,
        value: args.secret ? '<redacted>' : value,
        decrypted: args.withDecryption ?? false,
      },
    });
    return { value, source: 'ssm', detail: args.ssmPath };
  } catch (err) {
    const e = err as { name?: string; message?: string };
    const errName = e?.name ?? '';
    let fix: string;
    if (errName === 'ParameterNotFound' || err instanceof ParameterNotFound) {
      fix =
        `SSM parameter '${args.ssmPath}' does not exist in this account/region. ` +
        `Confirm the env (--environment) matches the AWS account, or set ${args.overrideKey}=<value> in ha-debug/.env to override.`;
    } else if (errName === 'AccessDeniedException') {
      fix =
        `Access denied reading SSM parameter '${args.ssmPath}'. ` +
        `Your SSO role lacks ssm:GetParameter${args.withDecryption ? ' or kms:Decrypt' : ''}. ` +
        `Ask Operations to grant read on /accounts/*, /<env>/harmony/auth/*, and /idp/*/userManagement/* (with KMS Decrypt for the secret).`;
    } else {
      fix = `SSM lookup failed for '${args.ssmPath}': ${e?.message ?? String(err)}`;
    }
    args.steps.push({
      name: args.name,
      ok: false,
      detail: { source: 'ssm', path: args.ssmPath, error: errName },
      fix,
    });
    return { value: '', source: 'ssm', detail: args.ssmPath };
  }
}

interface ResolveCognitoArgs {
  ctx: DiscoveryContext;
  steps: DiscoveryStep[];
}

async function resolveCognitoPools(args: ResolveCognitoArgs): Promise<ResolvedCognitoPools> {
  const overrideList = envListOverride('COGNITO_USER_POOL_IDS');
  if (overrideList) {
    const pools: CognitoPool[] = overrideList.map(id => ({ name: '<override>', id }));
    args.steps.push({
      name: 'cognito-pool-discovery',
      ok: true,
      detail: { source: 'env-override', poolIds: overrideList },
    });
    return { value: pools, source: 'env-override' };
  }
  const targetNames = cognitoPoolNames(args.ctx.environment);
  try {
    const cog = new CognitoIdentityProviderClient(awsClientConfig(args.ctx));
    const found: CognitoPool[] = [];
    let nextToken: string | undefined;
    let scanned = 0;
    do {
      const res = await cog.send(new ListUserPoolsCommand({ MaxResults: 60, NextToken: nextToken }));
      for (const p of res.UserPools ?? []) {
        scanned += 1;
        if (p.Name && p.Id && targetNames.includes(p.Name)) {
          found.push({ name: p.Name, id: p.Id });
        }
      }
      nextToken = res.NextToken;
    } while (nextToken && found.length < targetNames.length);

    if (found.length === 0) {
      args.steps.push({
        name: 'cognito-pool-discovery',
        ok: false,
        detail: { targetNames, scanned, found: [] },
        fix:
          `No Cognito user pool matched the expected name patterns ${JSON.stringify(targetNames)} ` +
          `in this account/region after scanning ${scanned} pools. ` +
          `Confirm --environment matches the AWS account, or pass COGNITO_USER_POOL_IDS=<id1>,<id2> to override.`,
      });
      return { value: [], source: 'discovered' };
    }

    const missing = targetNames.filter(n => !found.some(f => f.name === n));
    args.steps.push({
      name: 'cognito-pool-discovery',
      ok: missing.length === 0,
      detail: { source: 'discovered', found, missing, scanned },
      fix:
        missing.length === 0
          ? undefined
          : `Found ${found.length} of ${targetNames.length} expected pools; missing ${JSON.stringify(missing)}. ` +
            `User-lookup will only succeed for users in the discovered pools.`,
    });
    return { value: found, source: 'discovered' };
  } catch (err) {
    const e = err as { name?: string; message?: string };
    const errName = e?.name ?? '';
    let fix: string;
    if (errName === 'AccessDeniedException') {
      fix =
        `Access denied calling cognito-idp:ListUserPools. ` +
        `Your SSO role lacks the permission. Ask Operations to grant cognito-idp:ListUserPools on the account.`;
    } else {
      fix = `cognito-idp:ListUserPools failed: ${e?.message ?? String(err)}`;
    }
    args.steps.push({
      name: 'cognito-pool-discovery',
      ok: false,
      detail: { error: errName },
      fix,
    });
    return { value: [], source: 'discovered' };
  }
}

interface ResolveCwArgs {
  ctx: DiscoveryContext;
  steps: DiscoveryStep[];
}

async function resolveCwLogGroups(args: ResolveCwArgs): Promise<ResolvedStringArray> {
  const overrideList = envListOverride('CW_LOG_GROUPS');
  if (overrideList) {
    args.steps.push({
      name: 'cloudwatch-log-group-discovery',
      ok: true,
      detail: { source: 'env-override', logGroups: overrideList },
    });
    return { value: overrideList, source: 'env-override' };
  }
  const prefix = cwLogGroupPrefix(args.ctx.environment);
  try {
    const cw = new CloudWatchLogsClient(awsClientConfig(args.ctx));
    const groups: string[] = [];
    let nextToken: string | undefined;
    do {
      const res = await cw.send(new DescribeLogGroupsCommand({
        logGroupNamePrefix: prefix,
        nextToken,
        limit: 50,
      }));
      for (const g of res.logGroups ?? []) {
        if (g.logGroupName) groups.push(g.logGroupName);
      }
      nextToken = res.nextToken;
    } while (nextToken && groups.length < 50);

    if (groups.length === 0) {
      args.steps.push({
        name: 'cloudwatch-log-group-discovery',
        ok: false,
        detail: { source: 'discovered', prefix, found: [] },
        fix:
          `No CloudWatch log groups found with prefix '${prefix}'. ` +
          `Confirm --environment matches the AWS account, or pass CW_LOG_GROUPS=<group1>,<group2> to override.`,
      });
      return { value: [], source: 'discovered' };
    }

    // CloudWatch Insights accepts up to 50 log groups per query; cap defensively.
    const capped = groups.slice(0, 50);
    args.steps.push({
      name: 'cloudwatch-log-group-discovery',
      ok: true,
      detail: { source: 'discovered', prefix, count: capped.length, logGroups: capped },
    });
    return { value: capped, source: 'discovered' };
  } catch (err) {
    const e = err as { name?: string; message?: string };
    const errName = e?.name ?? '';
    let fix: string;
    if (errName === 'AccessDeniedException') {
      fix =
        `Access denied calling logs:DescribeLogGroups. ` +
        `Your SSO role lacks the permission. Ask Operations to grant logs:DescribeLogGroups on the account.`;
    } else {
      fix = `logs:DescribeLogGroups failed for prefix '${prefix}': ${e?.message ?? String(err)}`;
    }
    args.steps.push({
      name: 'cloudwatch-log-group-discovery',
      ok: false,
      detail: { error: errName, prefix },
      fix,
    });
    return { value: [], source: 'discovered' };
  }
}
