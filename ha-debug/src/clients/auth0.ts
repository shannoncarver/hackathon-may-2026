import { ManagementClient } from 'auth0';
import { Credentials } from '../auth';
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

  constructor(creds: Credentials) {
    this.mgmt = new ManagementClient({
      domain: creds.auth0Domain,
      clientId: creds.auth0ClientId,
      clientSecret: creds.auth0ClientSecret,
    });
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
