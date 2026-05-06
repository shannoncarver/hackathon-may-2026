import { DynamoDBClient, DescribeTableCommand } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, QueryCommand } from '@aws-sdk/lib-dynamodb';
import { RuntimeContext } from '../auth';
import { awsClientConfig } from '../aws-session';
import { DataSourceError } from '../errors';
import { AppClient, Lock, MultiFactorEnrollment, SuperAdminMFA } from '../types';

export class HaDebugDynamoDBClient {
  private readonly raw: DynamoDBClient;
  private readonly docClient: DynamoDBDocumentClient;
  private readonly accountsTable: string;
  private readonly superAdminMfaTable: string;
  private readonly appClientsTable: string;

  constructor(ctx: RuntimeContext) {
    this.raw = new DynamoDBClient(awsClientConfig(ctx));
    this.docClient = DynamoDBDocumentClient.from(this.raw, {
      marshallOptions: { removeUndefinedValues: true },
    });
    this.accountsTable = ctx.accountsTableName;
    this.superAdminMfaTable = ctx.superAdminMfaTableName;
    this.appClientsTable = ctx.appClientsTableName;
  }

  async describeTable(tableName: string): Promise<{ ok: true } | { ok: false; reason: string }> {
    try {
      await this.raw.send(new DescribeTableCommand({ TableName: tableName }));
      return { ok: true };
    } catch (err) {
      const e = err as { name?: string; message?: string };
      const name = e?.name ?? '';
      if (name === 'ResourceNotFoundException') {
        return { ok: false, reason: `Table '${tableName}' does not exist in this account/region.` };
      }
      if (name === 'AccessDeniedException') {
        return { ok: false, reason: `Access denied to '${tableName}'. The SSO role lacks dynamodb:DescribeTable.` };
      }
      return { ok: false, reason: e?.message ?? String(err) };
    }
  }

  get tableNames(): { accounts: string; superAdminMfa: string; appClients: string } {
    return {
      accounts: this.accountsTable,
      superAdminMfa: this.superAdminMfaTable,
      appClients: this.appClientsTable,
    };
  }

  async getLockRecord(userId: string): Promise<Lock | undefined> {
    try {
      const res = await this.docClient.send(new GetCommand({
        TableName: this.accountsTable,
        Key: { id: `lock-${userId}` },
      }));
      return res.Item as Lock | undefined;
    } catch (err) {
      throw new DataSourceError('dynamodb:lock', 'unknown', true, err, `Failed to get lock for ${userId}`);
    }
  }

  async getMfaEnrollment(userId: string): Promise<MultiFactorEnrollment | undefined> {
    try {
      const res = await this.docClient.send(new GetCommand({
        TableName: this.accountsTable,
        Key: { id: userId },
      }));
      return res.Item as MultiFactorEnrollment | undefined;
    } catch (err) {
      throw new DataSourceError('dynamodb:mfa-enrollment', 'unknown', true, err, `Failed to get MFA enrollment for ${userId}`);
    }
  }

  async getSuperAdminMfa(product: string): Promise<SuperAdminMFA | undefined> {
    try {
      const res = await this.docClient.send(new GetCommand({
        TableName: this.superAdminMfaTable,
        Key: { product },
      }));
      return res.Item as SuperAdminMFA | undefined;
    } catch (err) {
      throw new DataSourceError('dynamodb:super-admin-mfa', 'unknown', true, err, `Failed to get SuperAdminMFA for ${product}`);
    }
  }

  async getAppClient(clientId: string): Promise<AppClient | undefined> {
    try {
      const res = await this.docClient.send(new GetCommand({
        TableName: this.appClientsTable,
        Key: { id: clientId },
      }));
      if (!res.Item) return undefined;
      return this.blobToAppClient(res.Item as Record<string, unknown>);
    } catch (err) {
      throw new DataSourceError('dynamodb:app-client', 'unknown', true, err, `Failed to get app client: ${clientId}`);
    }
  }

  async getAppClientByHomeRealm(product: string, subdomain: string): Promise<AppClient | undefined> {
    try {
      const idRes = await this.docClient.send(new QueryCommand({
        TableName: this.appClientsTable,
        IndexName: 'SubdomainIndex',
        KeyConditionExpression: 'product = :product AND subdomain = :subdomain',
        ExpressionAttributeValues: { ':product': product, ':subdomain': subdomain },
        Limit: 1,
      }));
      if (!idRes.Items?.length) return undefined;
      return this.getAppClient(idRes.Items[0].id as string);
    } catch (err) {
      throw new DataSourceError('dynamodb:app-client-home-realm', 'unknown', true, err, `Failed to get app client for ${product}/${subdomain}`);
    }
  }

  async listAppClients(product: string, limit = 50): Promise<AppClient[]> {
    try {
      const res = await this.docClient.send(new QueryCommand({
        TableName: this.appClientsTable,
        IndexName: 'ProductIndex',
        KeyConditionExpression: 'product = :product',
        ExpressionAttributeValues: { ':product': product },
        Limit: limit,
      }));
      return (res.Items ?? []).map(item => this.blobToAppClient(item as Record<string, unknown>));
    } catch (err) {
      throw new DataSourceError('dynamodb:list-app-clients', 'unknown', true, err, `Failed to list app clients for product: ${product}`);
    }
  }

  private blobToAppClient(item: Record<string, unknown>): AppClient {
    return {
      id: item.id as string,
      name: item.name as string | undefined,
      product: item.product as string | undefined,
      subdomain: item.subdomain as string | undefined,
      status: ((item.status as string) ?? 'enabled') as AppClient['status'],
      auth0ClientId: (item.auth0Id ?? item.auth0ClientId) as string | undefined,
      clientType: item.clientType as string | undefined,
    };
  }

  async getUserEvents(userId: string, fromMs?: number, toMs?: number): Promise<Record<string, unknown>[]> {
    try {
      let keyCondition = 'userId = :userId';
      const values: Record<string, unknown> = { ':userId': userId };

      if (fromMs !== undefined && toMs !== undefined) {
        keyCondition += ' AND updatedAt BETWEEN :start AND :end';
        values[':start'] = fromMs;
        values[':end'] = toMs;
      } else if (fromMs !== undefined) {
        keyCondition += ' AND updatedAt >= :start';
        values[':start'] = fromMs;
      }

      const res = await this.docClient.send(new QueryCommand({
        TableName: this.accountsTable,
        IndexName: 'accountPartition',
        KeyConditionExpression: keyCondition,
        ExpressionAttributeValues: values,
        ScanIndexForward: false,
        Limit: 50,
      }));
      return (res.Items ?? []) as Record<string, unknown>[];
    } catch (err) {
      throw new DataSourceError('dynamodb:user-events', 'unknown', true, err, `Failed to get events for ${userId}`);
    }
  }
}
