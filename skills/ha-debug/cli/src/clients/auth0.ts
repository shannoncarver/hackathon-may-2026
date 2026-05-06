import { ManagementClient } from 'auth0';
import { RuntimeContext } from '../auth';
import { DataSourceError } from '../errors';

export interface Auth0UserSummary {
  userId: string;
  email?: string;
  emailVerified?: boolean;
  name?: string;
  blocked?: boolean;
  lastLogin?: string;
  loginsCount?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface Auth0LogEntry {
  type: string;
  date: string;
  description?: string;
  ip?: string;
  connection?: string;
  clientId?: string;
}

export interface Auth0Factor {
  type: string;
  confirmed: boolean;
}

export interface Auth0ConnectionDetails {
  id: string;
  name: string;
  strategy: string;
  enabledClients: string[];
  mfaActive: boolean;
}

export class HaDebugAuth0Client {
  private readonly mgmt: ManagementClient;
  private readonly domain: string;
  private readonly clientId: string;
  private readonly clientSecret: string;

  constructor(ctx: RuntimeContext) {
    this.domain = ctx.auth0Domain;
    this.clientId = ctx.auth0ClientId;
    this.clientSecret = ctx.auth0ClientSecret;
    this.mgmt = new ManagementClient({
      domain: ctx.auth0Domain,
      clientId: ctx.auth0ClientId,
      clientSecret: ctx.auth0ClientSecret,
    });
  }

  async verifyToken(): Promise<{ ok: true; expiresInSec: number } | { ok: false; reason: string }> {
    try {
      const res = await fetch(`https://${this.domain}/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          grant_type: 'client_credentials',
          client_id: this.clientId,
          client_secret: this.clientSecret,
          audience: `https://${this.domain}/api/v2/`,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        let detail = body;
        try {
          const parsed = JSON.parse(body) as { error?: string; error_description?: string };
          detail = parsed.error_description ?? parsed.error ?? body;
        } catch {
          // fall through
        }
        return {
          ok: false,
          reason: `Auth0 M2M token mint failed (HTTP ${res.status}): ${detail}. ` +
            `Check AUTH0_DOMAIN_*, AUTH0_CLIENT_ID_*, AUTH0_CLIENT_SECRET_* in ha-debug/.env. ` +
            `The M2M app must have read:users, read:logs, read:authentication_methods scopes against the Management API.`,
        };
      }
      const json = (await res.json()) as { expires_in?: number };
      return { ok: true, expiresInSec: json.expires_in ?? 0 };
    } catch (err) {
      const e = err as { message?: string };
      return { ok: false, reason: `Auth0 token mint threw: ${e?.message ?? String(err)}` };
    }
  }

  async getUserByEmail(email: string): Promise<Auth0UserSummary | undefined> {
    try {
      const res = await this.mgmt.users.getAll({
        q: `email:"${email}"`,
        search_engine: 'v3',
      });
      const users = res.data;
      if (!users?.length) return undefined;
      const u = users[0];
      return {
        userId: u.user_id!,
        email: u.email,
        emailVerified: u.email_verified,
        name: u.name,
        blocked: u.blocked,
        lastLogin: u.last_login?.toString(),
        loginsCount: u.logins_count,
        createdAt: u.created_at?.toString(),
        updatedAt: u.updated_at?.toString(),
      };
    } catch (err: any) {
      const kind = err?.statusCode === 429 ? 'throttled' : 'unknown';
      throw new DataSourceError('auth0:get-user', kind, true, err, `Failed to get Auth0 user: ${email}`);
    }
  }

  async getUserLogs(auth0UserId: string, limit = 25): Promise<Auth0LogEntry[]> {
    try {
      const res = await this.mgmt.users.getLogs({
        id: auth0UserId,
        per_page: limit,
        sort: 'date:-1',
      });
      return (res.data ?? []).map((log: any) => ({
        type: log.type,
        date: log.date,
        description: log.description,
        ip: log.ip,
        connection: log.connection,
        clientId: log.client_id,
      }));
    } catch (err: any) {
      const kind = err?.statusCode === 429 ? 'throttled' : 'unknown';
      throw new DataSourceError('auth0:user-logs', kind, true, err, `Failed to get Auth0 logs for: ${auth0UserId}`);
    }
  }

  async getUserFactors(auth0UserId: string): Promise<Auth0Factor[]> {
    try {
      const res = await this.mgmt.users.getAuthenticationMethods({ id: auth0UserId });
      return (res.data ?? []).map((f: any) => ({
        type: f.type,
        confirmed: f.confirmed ?? false,
      }));
    } catch (err: any) {
      throw new DataSourceError('auth0:user-factors', 'unknown', false, err, `Failed to get Auth0 factors for: ${auth0UserId}`);
    }
  }

  async getConnectionMfaPolicy(connectionId: string): Promise<{ requiresMfa: boolean; options: unknown } | undefined> {
    try {
      const res = await this.mgmt.connections.get({ id: connectionId });
      const options = (res.data as any)?.options ?? {};
      return { requiresMfa: options.mfa?.active ?? false, options: options.mfa };
    } catch (err: any) {
      if (err?.statusCode === 404) return undefined;
      throw new DataSourceError('auth0:connection', 'unknown', false, err, `Failed to get connection: ${connectionId}`);
    }
  }

  async getConnectionDetails(connectionId: string): Promise<Auth0ConnectionDetails | undefined> {
    try {
      const res = await this.mgmt.connections.get({ id: connectionId });
      const d = res.data as any;
      if (!d) return undefined;
      return {
        id: d.id,
        name: d.name,
        strategy: d.strategy,
        enabledClients: d.enabled_clients ?? [],
        mfaActive: d.options?.mfa?.active ?? false,
      };
    } catch (err: any) {
      if (err?.statusCode === 404) return undefined;
      throw new DataSourceError('auth0:connection-details', 'unknown', false, err, `Failed to get connection details: ${connectionId}`);
    }
  }

  async listConnections(): Promise<Auth0ConnectionDetails[]> {
    try {
      const res = await this.mgmt.connections.getAll();
      return (res.data ?? []).map((d: any) => ({
        id: d.id,
        name: d.name,
        strategy: d.strategy,
        enabledClients: d.enabled_clients ?? [],
        mfaActive: d.options?.mfa?.active ?? false,
      }));
    } catch (err: any) {
      const kind = err?.statusCode === 429 ? 'throttled' : 'unknown';
      throw new DataSourceError('auth0:list-connections', kind, true, err, 'Failed to list Auth0 connections');
    }
  }
}
