import { DynamoDBClient, DynamoDBClientConfig } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, GetCommand, QueryCommand } from '@aws-sdk/lib-dynamodb';
import { Credentials } from '../auth';
import { DataSourceError } from '../errors';
import { AppClient, Lock, MultiFactorEnrollment, SuperAdminMFA } from '../types';

export class HaDebugDynamoDBClient {
  private readonly docClient: DynamoDBDocumentClient;
  private readonly accountsTable: string;
  private readonly superAdminMfaTable: string;
  private readonly appClientsTable: string;

  constructor(creds: Credentials) {
    const config: DynamoDBClientConfig = { region: creds.awsRegion };
    if (creds.awsAccessKeyId && creds.awsSecretAccessKey) {
      config.credentials = {
        accessKeyId: creds.awsAccessKeyId,
        secretAccessKey: creds.awsSecretAccessKey,
        sessionToken: creds.awsSessionToken,
      };
    }
    this.docClient = DynamoDBDocumentClient.from(new DynamoDBClient(config), {
      marshallOptions: { removeUndefinedValues: true },
    });
    this.accountsTable = creds.accountsTableName;
    this.superAdminMfaTable = creds.superAdminMfaTableName;
    this.appClientsTable = creds.appClientsTableName;
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
