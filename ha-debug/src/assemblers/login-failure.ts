import { HaDebugAuth0Client } from '../clients/auth0';
import { HaDebugCognitoClient } from '../clients/cognito';
import { HaDebugDynamoDBClient } from '../clients/dynamodb';
import { HaDebugCloudWatchClient } from '../clients/cloudwatch';
import { resolveSubject, CanonicalSubject } from '../resolve-subject';

export interface LoginFailureCaseFile {
  identity: CanonicalSubject;
  lockState: {
    locked: boolean;
    lockedSinceMs?: number;
  };
  appClient?: {
    found: boolean;
    id?: string;
    name?: string;
    product?: string;
    status?: string;
    clientType?: string;
  };
  cloudwatchLogs: Array<{
    timestamp: string;
    message: string;
  }>;
  windowMs: number;
  assembledAt: string;
}

export async function assembleLoginFailureCase(
  emailOrUserId: string,
  windowMs: number,
  auth0: HaDebugAuth0Client,
  cognito: HaDebugCognitoClient,
  ddb: HaDebugDynamoDBClient,
  cw: HaDebugCloudWatchClient,
  opts: { clientId?: string } = {},
): Promise<LoginFailureCaseFile> {
  const identity = await resolveSubject(emailOrUserId, auth0, cognito);
  const lookupId = identity.auth0Id ?? emailOrUserId;

  const [lock, cwLogs, appClient] = await Promise.allSettled([
    ddb.getLockRecord(lookupId),
    cw.queryAuthLogs(identity.email ?? emailOrUserId, windowMs, 50).catch(() => []),
    opts.clientId ? ddb.getAppClient(opts.clientId) : Promise.resolve(undefined),
  ]);

  const lockData = lock.status === 'fulfilled' ? lock.value : undefined;
  const cwData = cwLogs.status === 'fulfilled' ? cwLogs.value : [];
  const appClientData = appClient.status === 'fulfilled' ? appClient.value : undefined;

  return {
    identity,
    lockState: {
      locked: lockData?.status === 'locked',
      lockedSinceMs: lockData?.updatedAt,
    },
    ...(opts.clientId !== undefined && {
      appClient: {
        found: !!appClientData,
        id: appClientData?.id,
        name: appClientData?.name,
        product: appClientData?.product,
        status: appClientData?.status,
        clientType: appClientData?.clientType,
      },
    }),
    cloudwatchLogs: cwData.slice(0, 20).map(l => ({
      timestamp: l.timestamp,
      message: l.message,
    })),
    windowMs,
    assembledAt: new Date().toISOString(),
  };
}
