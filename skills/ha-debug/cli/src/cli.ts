#!/usr/bin/env node
import { Command } from 'commander';
import {
  AwsAuthContext,
  Environment,
  RuntimeContext,
  WIKI_CASES_DIR,
  resolveAwsAuthContext,
} from './auth';
import { getCallerIdentity, printAuditBanner, classifyAwsCredError, CallerIdentity } from './audit';
import {
  discoverResources,
  inspectDiscovery,
  DiscoveredResources,
  DiscoveryStep,
} from './discovery';
import { HaDebugAuth0Client } from './clients/auth0';
import { HaDebugCognitoClient } from './clients/cognito';
import { HaDebugDynamoDBClient } from './clients/dynamodb';
import { HaDebugCloudWatchClient } from './clients/cloudwatch';
import { assembleLoginFailureCase } from './assemblers/login-failure';
import { assembleMfaNotEnforcedCase } from './assemblers/mfa-not-enforced';
import { writeResolvedCase } from './assemblers/write-resolved';
import { DataSourceError } from './errors';

interface GlobalOpts {
  environment: Environment;
  iUnderstandThisIsProd?: boolean;
  awsProfile?: string;
}

function parseWindow(raw: string): number {
  const m = raw.match(/^(\d+)(h|m|d)$/);
  if (!m) throw new Error(`Invalid --window "${raw}". Examples: 8h, 30m, 2d`);
  const n = parseInt(m[1]);
  const factor = m[2] === 'h' ? 3_600_000 : m[2] === 'm' ? 60_000 : 86_400_000;
  return n * factor;
}

function out(data: unknown): void {
  process.stdout.write(JSON.stringify(data, null, 2) + '\n');
}

function fail(err: unknown): never {
  if (err instanceof DataSourceError) {
    process.stderr.write(JSON.stringify({ error: err.kind, source: err.source, message: err.message, retryable: err.retryable }) + '\n');
  } else {
    process.stderr.write(JSON.stringify({ error: 'unknown', message: err instanceof Error ? err.message : String(err), retryable: false }) + '\n');
  }
  process.exit(1);
}

function getGlobalOpts(cmd: Command): GlobalOpts {
  let cur: Command | null = cmd;
  while (cur && cur.parent) cur = cur.parent;
  const opts = (cur ?? cmd).opts() as GlobalOpts;
  if (opts.environment !== 'dev' && opts.environment !== 'prod') {
    throw new Error(`Invalid --environment "${opts.environment}". Must be "dev" or "prod".`);
  }
  if (opts.environment === 'prod' && !opts.iUnderstandThisIsProd) {
    throw new Error(
      `Refusing prod run without --i-understand-this-is-prod. ` +
      `Add the flag explicitly to confirm prod intent. The flag has no shorter alias by design.`,
    );
  }
  return opts;
}

function buildRuntimeContext(aws: AwsAuthContext, discovered: DiscoveredResources): RuntimeContext {
  return {
    ...aws,
    accountsTableName: discovered.accountsTableName.value,
    appClientsTableName: discovered.appClientsTableName.value,
    superAdminMfaTableName: discovered.superAdminMfaTableName.value,
    auth0Domain: discovered.auth0Domain.value,
    auth0ClientId: discovered.auth0ClientId.value,
    auth0ClientSecret: discovered.auth0ClientSecret.value,
    cognitoUserPoolIds: discovered.cognitoUserPools.value.map(p => p.id),
    cwLogGroupNames: discovered.cwLogGroupNames.value,
  };
}

function awsContextFromGlobal(global: GlobalOpts): AwsAuthContext {
  return resolveAwsAuthContext({ environment: global.environment, awsProfileFlag: global.awsProfile });
}

interface Clients {
  auth0: HaDebugAuth0Client;
  cognito: HaDebugCognitoClient;
  ddb: HaDebugDynamoDBClient;
  cw: HaDebugCloudWatchClient;
  ctx: RuntimeContext;
  identity: CallerIdentity;
}

async function withClients<T>(
  global: GlobalOpts,
  resourceLabels: (ctx: RuntimeContext) => string[],
  fn: (c: Clients) => Promise<T>,
): Promise<T> {
  const aws = awsContextFromGlobal(global);
  const identity = await getCallerIdentity(aws);
  const discovered = await discoverResources(aws);
  const ctx = buildRuntimeContext(aws, discovered);
  printAuditBanner(ctx, identity, resourceLabels(ctx));
  return fn({
    auth0: new HaDebugAuth0Client(ctx),
    cognito: new HaDebugCognitoClient(ctx),
    ddb: new HaDebugDynamoDBClient(ctx),
    cw: new HaDebugCloudWatchClient(ctx),
    ctx,
    identity,
  });
}

const program = new Command();

program
  .name('ha-debug')
  .description('Harmony-Auth debugger for LINQ Tech Services')
  .version('0.3.0')
  .option('-e, --environment <env>', 'Target environment (dev or prod)', 'dev')
  .option('--i-understand-this-is-prod', 'Required acknowledgement when --environment prod')
  .option('--aws-profile <name>', 'Override the resolved AWS profile (pass empty string for ambient credential chain)');

// ---------- doctor ----------

interface DoctorCheck {
  name: string;
  ok: boolean;
  detail?: Record<string, unknown>;
  fix?: string;
}

program
  .command('doctor')
  .description('Run a setup health check: AWS profile, STS, SSM-discovered resources, Cognito pools, CloudWatch log groups, Auth0 token. Read-only.')
  .action(async (_opts, cmd) => {
    let global: GlobalOpts;
    try {
      global = getGlobalOpts(cmd);
    } catch (err) {
      out({
        ok: false,
        environment: '<unknown>',
        checks: [{ name: 'cli-args', ok: false, fix: err instanceof Error ? err.message : String(err) }],
        checkedAt: new Date().toISOString(),
      });
      process.exit(1);
    }
    const aws = awsContextFromGlobal(global);
    const checks: DoctorCheck[] = [];

    // 1. AWS SSO + STS GetCallerIdentity
    let identity: CallerIdentity | null = null;
    try {
      identity = await getCallerIdentity(aws);
      checks.push({
        name: 'aws-sso',
        ok: true,
        detail: {
          profile: aws.awsProfile ?? '<ambient>',
          account: identity.account,
          arn: identity.arn,
        },
      });
    } catch (err) {
      const dse = err instanceof DataSourceError ? err : classifyAwsCredError(err, aws);
      checks.push({
        name: 'aws-sso',
        ok: false,
        detail: { profile: aws.awsProfile ?? '<ambient>', source: dse.source },
        fix: dse.message,
      });
      // Cannot proceed with discovery without AWS
      out({
        environment: global.environment,
        ok: false,
        checks,
        checkedAt: new Date().toISOString(),
      });
      process.exit(1);
    }

    // 2. Resource discovery (each step independent, all reported)
    const report = await inspectDiscovery(aws);
    for (const step of report.steps) {
      checks.push({
        name: step.name,
        ok: step.ok,
        detail: step.detail,
        fix: step.fix,
      });
    }

    // 3. Verify discovered DynamoDB tables actually exist + are readable
    const ddbTables = [
      report.resources.accountsTableName?.value,
      report.resources.appClientsTableName?.value,
      report.resources.superAdminMfaTableName?.value,
    ].filter((t): t is string => !!t);

    if (ddbTables.length > 0) {
      const ddbCtx = partialRuntime(aws, report.resources);
      const ddb = new HaDebugDynamoDBClient(ddbCtx);
      for (const tableName of ddbTables) {
        const res = await ddb.describeTable(tableName);
        checks.push({
          name: `dynamodb-readable-${tableName}`,
          ok: res.ok,
          detail: { table: tableName },
          fix: res.ok ? undefined : res.reason,
        });
      }
    }

    // 4. Auth0 token mint
    const auth0Domain = report.resources.auth0Domain?.value;
    const auth0ClientId = report.resources.auth0ClientId?.value;
    const auth0ClientSecret = report.resources.auth0ClientSecret?.value;
    if (auth0Domain && auth0ClientId && auth0ClientSecret) {
      const ctx = partialRuntime(aws, report.resources);
      const auth0 = new HaDebugAuth0Client(ctx);
      const res = await auth0.verifyToken();
      checks.push({
        name: 'auth0-token-mintable',
        ok: res.ok,
        detail: res.ok
          ? { domain: auth0Domain, expiresInSec: res.expiresInSec }
          : { domain: auth0Domain },
        fix: res.ok ? undefined : res.reason,
      });
    } else {
      checks.push({
        name: 'auth0-token-mintable',
        ok: false,
        fix: `Skipped — Auth0 credentials not resolved (see ssm-auth0-* checks above).`,
      });
    }

    const allOk = checks.every(c => c.ok);
    out({
      environment: global.environment,
      ok: allOk,
      checks,
      checkedAt: new Date().toISOString(),
    });
    process.exit(allOk ? 0 : 1);
  });

function partialRuntime(aws: AwsAuthContext, resources: Partial<DiscoveredResources>): RuntimeContext {
  return {
    ...aws,
    accountsTableName: resources.accountsTableName?.value ?? '',
    appClientsTableName: resources.appClientsTableName?.value ?? '',
    superAdminMfaTableName: resources.superAdminMfaTableName?.value ?? '',
    auth0Domain: resources.auth0Domain?.value ?? '',
    auth0ClientId: resources.auth0ClientId?.value ?? '',
    auth0ClientSecret: resources.auth0ClientSecret?.value ?? '',
    cognitoUserPoolIds: resources.cognitoUserPools?.value.map(p => p.id) ?? [],
    cwLogGroupNames: resources.cwLogGroupNames?.value ?? [],
  };
}

// ---------- subcommands ----------

program
  .command('get-user')
  .description('Look up a user across Auth0 and all discovered Cognito user pools')
  .requiredOption('--email <email>', 'User email address')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [`auth0:${c.auth0Domain}`, `cognito-pools:${c.cognitoUserPoolIds.length}`],
        async ({ auth0, cognito }) => {
          const [auth0User, cognitoUser] = await Promise.allSettled([
            auth0.getUserByEmail(opts.email),
            cognito.getUserByEmail(opts.email),
          ]);
          return {
            auth0: auth0User.status === 'fulfilled' ? auth0User.value : null,
            cognito: cognitoUser.status === 'fulfilled' ? cognitoUser.value : null,
            lookedUpAt: new Date().toISOString(),
          };
        },
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('assemble-login-failure-case')
  .description('Assemble a case file for a user login failure')
  .requiredOption('--email <email>', 'User email address')
  .option('--window <window>', 'Time window to search (e.g. 8h, 30m, 2d)', '24h')
  .option('--client-id <clientId>', 'App client ID to include status in output')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const windowMs = parseWindow(opts.window);
      const result = await withClients(
        global,
        c => [
          `dynamodb:${c.accountsTableName}`,
          `dynamodb:${c.appClientsTableName}`,
          `cognito-pools:${c.cognitoUserPoolIds.length}`,
          `cloudwatch-groups:${c.cwLogGroupNames.length}`,
          `auth0:${c.auth0Domain}`,
        ],
        ({ auth0, cognito, ddb, cw }) =>
          assembleLoginFailureCase(opts.email, windowMs, auth0, cognito, ddb, cw, {
            clientId: opts.clientId,
          }),
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('assemble-mfa-not-enforced-case')
  .description('Assemble a case file for a user not being prompted for MFA')
  .requiredOption('--email <email>', 'User email address')
  .option('--product <product>', 'Product key (e.g. ERP_V4, TITAN, LINQCONNECT)', 'ERP_V4')
  .option('--client-id <clientId>', 'App client ID to include status in output')
  .option('--connection-id <connectionId>', 'Auth0 connection ID to include MFA policy in output')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [
          `dynamodb:${c.accountsTableName}`,
          `dynamodb:${c.superAdminMfaTableName}`,
          `dynamodb:${c.appClientsTableName}`,
          `cognito-pools:${c.cognitoUserPoolIds.length}`,
          `auth0:${c.auth0Domain}`,
        ],
        ({ auth0, cognito, ddb }) =>
          assembleMfaNotEnforcedCase(opts.email, opts.product, auth0, cognito, ddb, {
            clientId: opts.clientId,
            connectionId: opts.connectionId,
          }),
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('get-app-client')
  .description('Look up an app client record from DynamoDB')
  .requiredOption('--client-id <clientId>', 'App client ID')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [`dynamodb:${c.appClientsTableName}`],
        async ({ ddb }) => {
          const client = await ddb.getAppClient(opts.clientId);
          return { client: client ?? null, lookedUpAt: new Date().toISOString() };
        },
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('get-client-by-home-realm')
  .description('Look up an app client by product + subdomain (mirrors the auth flow lookup)')
  .requiredOption('--product <product>', 'Product key (e.g. ERP_V4, TITAN)')
  .requiredOption('--subdomain <subdomain>', 'School subdomain (e.g. myschool)')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [`dynamodb:${c.appClientsTableName}`],
        async ({ ddb }) => {
          const client = await ddb.getAppClientByHomeRealm(opts.product, opts.subdomain);
          return { client: client ?? null, lookedUpAt: new Date().toISOString() };
        },
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('list-clients')
  .description('List app clients for a product from DynamoDB')
  .requiredOption('--product <product>', 'Product key (e.g. ERP_V4, TITAN)')
  .option('--limit <n>', 'Max results', '50')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [`dynamodb:${c.appClientsTableName}`],
        async ({ ddb }) => {
          const clients = await ddb.listAppClients(opts.product, parseInt(opts.limit));
          return { product: opts.product, count: clients.length, clients };
        },
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('get-connection')
  .description('Get full Auth0 connection details including enabled clients and MFA policy')
  .requiredOption('--connection-id <connectionId>', 'Auth0 connection ID')
  .action(async (opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [`auth0:${c.auth0Domain}`],
        async ({ auth0 }) => {
          const connection = await auth0.getConnectionDetails(opts.connectionId);
          return { connection: connection ?? null, lookedUpAt: new Date().toISOString() };
        },
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('list-connections')
  .description('List all Auth0 connections with MFA policy and enabled client counts')
  .action(async (_opts, cmd) => {
    try {
      const global = getGlobalOpts(cmd);
      const result = await withClients(
        global,
        c => [`auth0:${c.auth0Domain}`],
        async ({ auth0 }) => {
          const connections = await auth0.listConnections();
          return { count: connections.length, connections };
        },
      );
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('decode-token')
  .description('Decode a JWT locally (no network) — inspect claims, issuer, expiry')
  .requiredOption('--token <jwt>', 'JWT to decode')
  .action((opts) => {
    try {
      const parts = opts.token.split('.');
      if (parts.length !== 3) throw new Error('Not a valid JWT — expected 3 dot-separated parts');
      const decode = (s: string) => JSON.parse(Buffer.from(s, 'base64url').toString('utf8'));
      const header = decode(parts[0]);
      const payload = decode(parts[1]);
      const now = Math.floor(Date.now() / 1000);
      const expired = payload.exp != null ? payload.exp < now : null;
      const expiresInSec = payload.exp != null ? payload.exp - now : null;
      out({ header, payload, expired, expiresInSec, decodedAt: new Date().toISOString() });
    } catch (err) {
      fail(err);
    }
  });

program
  .command('write-resolved-case')
  .description('Persist a resolved case to the knowledge wiki (writes locally — no AWS / Auth0 needed)')
  .requiredOption('--case-json <json>', 'Case file JSON (pipe in from assembler output)')
  .requiredOption('--hypothesis <text>', 'Root cause hypothesis')
  .requiredOption('--resolution <text>', 'Resolution applied')
  .action(async (opts) => {
    try {
      const caseFile = JSON.parse(opts.caseJson);
      const filepath = writeResolvedCase(
        { caseFile, hypothesis: opts.hypothesis, resolution: opts.resolution },
        WIKI_CASES_DIR,
      );
      out({ written: filepath });
    } catch (err) {
      fail(err);
    }
  });

program.parseAsync(process.argv).catch(fail);
