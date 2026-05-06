import {
  CloudWatchLogsClient,
  StartQueryCommand,
  GetQueryResultsCommand,
  QueryStatus,
} from '@aws-sdk/client-cloudwatch-logs';
import { RuntimeContext } from '../auth';
import { awsClientConfig } from '../aws-session';
import { DataSourceError } from '../errors';

export interface CwLogEntry {
  timestamp: string;
  message: string;
  logStream?: string;
}

export class HaDebugCloudWatchClient {
  private readonly client: CloudWatchLogsClient;
  private readonly logGroupNames: string[];

  constructor(ctx: RuntimeContext) {
    this.client = new CloudWatchLogsClient(awsClientConfig(ctx));
    this.logGroupNames = ctx.cwLogGroupNames;
  }

  get groupNames(): string[] {
    return [...this.logGroupNames];
  }

  async queryAuthLogs(searchTerm: string, windowMs: number, limit = 50): Promise<CwLogEntry[]> {
    if (this.logGroupNames.length === 0) {
      return [];
    }
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
        logGroupNames: this.logGroupNames,
        startTime: Math.floor(startTime / 1000),
        endTime: Math.floor(endTime / 1000),
        queryString: query,
      }));
      queryId = res.queryId!;
    } catch (err) {
      const e = err as { name?: string };
      const kind = e?.name === 'ThrottlingException' ? 'throttled' : 'unknown';
      throw new DataSourceError('cloudwatch:start-query', kind, true, err, `Failed to start CloudWatch query for: ${searchTerm} across ${this.logGroupNames.length} log groups`);
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
