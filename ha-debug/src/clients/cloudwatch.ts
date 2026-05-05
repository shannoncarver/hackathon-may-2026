import {
  CloudWatchLogsClient,
  CloudWatchLogsClientConfig,
  StartQueryCommand,
  GetQueryResultsCommand,
  QueryStatus,
} from '@aws-sdk/client-cloudwatch-logs';
import { Credentials } from '../auth';
import { DataSourceError } from '../errors';

export interface CwLogEntry {
  timestamp: string;
  message: string;
  logStream?: string;
}

export class HaDebugCloudWatchClient {
  private readonly client: CloudWatchLogsClient;
  private readonly logGroupName: string;

  constructor(creds: Credentials) {
    const config: CloudWatchLogsClientConfig = { region: creds.awsRegion };
    if (creds.awsAccessKeyId && creds.awsSecretAccessKey) {
      config.credentials = {
        accessKeyId: creds.awsAccessKeyId,
        secretAccessKey: creds.awsSecretAccessKey,
        sessionToken: creds.awsSessionToken,
      };
    }
    this.client = new CloudWatchLogsClient(config);
    this.logGroupName = creds.cwLogGroupName;
  }

  async queryAuthLogs(searchTerm: string, windowMs: number, limit = 50): Promise<CwLogEntry[]> {
    const endTime = Date.now();
    const startTime = endTime - windowMs;
    const query = [
      'fields @timestamp, @message, @logStream',
      `| filter @message like /${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/`,
      '| sort @timestamp desc',
      `| limit ${limit}`,
    ].join('\n');

    let queryId: string;
    try {
      const res = await this.client.send(new StartQueryCommand({
        logGroupName: this.logGroupName,
        startTime: Math.floor(startTime / 1000),
        endTime: Math.floor(endTime / 1000),
        queryString: query,
      }));
      queryId = res.queryId!;
    } catch (err: any) {
      const kind = err?.name === 'ThrottlingException' ? 'throttled' : 'unknown';
      throw new DataSourceError('cloudwatch:start-query', kind, true, err, `Failed to start CloudWatch query for: ${searchTerm}`);
    }

    return this.poll(queryId);
  }

  private async poll(queryId: string, maxWaitMs = 30_000): Promise<CwLogEntry[]> {
    const deadline = Date.now() + maxWaitMs;
    while (Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 1_000));
      const res = await this.client.send(new GetQueryResultsCommand({ queryId }));
      const status = res.status as QueryStatus;

      if (status === QueryStatus.Complete) {
        return (res.results ?? []).map(row => {
          const fields: Record<string, string> = {};
          for (const f of row) {
            if (f.field && f.value !== undefined) fields[f.field] = f.value;
          }
          return {
            timestamp: fields['@timestamp'] ?? '',
            message: fields['@message'] ?? '',
            logStream: fields['@logStream'],
          };
        });
      }

      if (status === QueryStatus.Failed || status === QueryStatus.Cancelled) {
        throw new DataSourceError('cloudwatch:poll', 'unknown', true, { queryId, status }, `CloudWatch query ${status}`);
      }
    }
    throw new DataSourceError('cloudwatch:poll', 'timeout', true, { queryId }, 'CloudWatch query timed out after 30s');
  }
}
