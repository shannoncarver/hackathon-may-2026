#!/usr/bin/env node
import { Command } from 'commander';
import { EnvAuthProvider, Credentials } from './auth';
import { HaDebugAuth0Client } from './clients/auth0';
import { HaDebugCognitoClient } from './clients/cognito';
import { HaDebugDynamoDBClient } from './clients/dynamodb';
import { HaDebugCloudWatchClient } from './clients/cloudwatch';
import { assembleLoginFailureCase } from './assemblers/login-failure';
import { assembleMfaNotEnforcedCase } from './assemblers/mfa-not-enforced';
import { writeResolvedCase } from './assemblers/write-resolved';
import { DataSourceError } from './errors';

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

async function withClients<T>(fn: (c: {
  auth0: HaDebugAuth0Client;
  cognito: HaDebugCognitoClient;
  ddb: HaDebugDynamoDBClient;
  cw: HaDebugCloudWatchClient;
  creds: Credentials;
}) => Promise<T>): Promise<T> {
  const creds = await new EnvAuthProvider().getCredentials();
  return fn({
    auth0: new HaDebugAuth0Client(creds),
    cognito: new HaDebugCognitoClient(creds),
    ddb: new HaDebugDynamoDBClient(creds),
    cw: new HaDebugCloudWatchClient(creds),
    creds,
  });
}

const program = new Command();

program
  .name('ha-debug')
  .description('Harmony-Auth debugger for LINQ Tech Services')
  .version('0.1.0');

program
  .command('get-user')
  .description('Look up a user across Auth0 and Cognito')
  .requiredOption('--email <email>', 'User email address')
  .action(async (opts) => {
    try {
      const result = await withClients(async ({ auth0, cognito }) => {
        const [auth0User, cognitoUser] = await Promise.allSettled([
          auth0.getUserByEmail(opts.email),
          cognito.getUserByEmail(opts.email),
        ]);
        return {
          auth0: auth0User.status === 'fulfilled' ? auth0User.value : null,
          cognito: cognitoUser.status === 'fulfilled' ? cognitoUser.value : null,
          lookedUpAt: new Date().toISOString(),
        };
      });
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
  .action(async (opts) => {
    try {
      const windowMs = parseWindow(opts.window);
      const result = await withClients(({ auth0, cognito, ddb, cw }) =>
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
  .action(async (opts) => {
    try {
      const result = await withClients(({ auth0, cognito, ddb }) =>
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
  .action(async (opts) => {
    try {
      const result = await withClients(async ({ ddb }) => {
        const client = await ddb.getAppClient(opts.clientId);
        return { client: client ?? null, lookedUpAt: new Date().toISOString() };
      });
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
  .action(async (opts) => {
    try {
      const result = await withClients(async ({ ddb }) => {
        const client = await ddb.getAppClientByHomeRealm(opts.product, opts.subdomain);
        return { client: client ?? null, lookedUpAt: new Date().toISOString() };
      });
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
  .action(async (opts) => {
    try {
      const result = await withClients(async ({ ddb }) => {
        const clients = await ddb.listAppClients(opts.product, parseInt(opts.limit));
        return { product: opts.product, count: clients.length, clients };
      });
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('get-connection')
  .description('Get full Auth0 connection details including enabled clients and MFA policy')
  .requiredOption('--connection-id <connectionId>', 'Auth0 connection ID')
  .action(async (opts) => {
    try {
      const result = await withClients(async ({ auth0 }) => {
        const connection = await auth0.getConnectionDetails(opts.connectionId);
        return { connection: connection ?? null, lookedUpAt: new Date().toISOString() };
      });
      out(result);
    } catch (err) {
      fail(err);
    }
  });

program
  .command('list-connections')
  .description('List all Auth0 connections with MFA policy and enabled client counts')
  .action(async () => {
    try {
      const result = await withClients(async ({ auth0 }) => {
        const connections = await auth0.listConnections();
        return { count: connections.length, connections };
      });
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
  .description('Persist a resolved case to the knowledge wiki')
  .requiredOption('--case-json <json>', 'Case file JSON (pipe in from assembler output)')
  .requiredOption('--hypothesis <text>', 'Root cause hypothesis')
  .requiredOption('--resolution <text>', 'Resolution applied')
  .action(async (opts) => {
    try {
      const caseFile = JSON.parse(opts.caseJson);
      const creds = await new EnvAuthProvider().getCredentials();
      const filepath = writeResolvedCase({ caseFile, hypothesis: opts.hypothesis, resolution: opts.resolution }, creds);
      out({ written: filepath });
    } catch (err) {
      fail(err);
    }
  });

program.parseAsync(process.argv).catch(fail);
