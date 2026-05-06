import { HaDebugAuth0Client } from '../clients/auth0';
import { HaDebugCognitoClient } from '../clients/cognito';
import { HaDebugDynamoDBClient } from '../clients/dynamodb';
import { resolveSubject, CanonicalSubject } from '../resolve-subject';

export interface MfaNotEnforcedCaseFile {
  identity: CanonicalSubject;
  mfaEnrollment: {
    found: boolean;
    requiresMfa?: boolean;
  };
  auth0Factors: Array<{
    type: string;
    confirmed: boolean;
  }>;
  cognitoMfaConfig: {
    mfaStatus: string;
    softwareTokenEnabled: boolean;
    smsMfaEnabled: boolean;
  };
  superAdminMfa: {
    found: boolean;
    product?: string;
    enabled?: boolean;
    tenantList?: string[];
    disabledAt?: string;
    expiresAt?: number;
    expiresInMs?: number;
  };
  appClient?: {
    found: boolean;
    id?: string;
    name?: string;
    product?: string;
    status?: string;
    clientType?: string;
  };
  connectionMfaPolicy?: {
    found: boolean;
    requiresMfa?: boolean;
  };
  assembledAt: string;
}

export async function assembleMfaNotEnforcedCase(
  emailOrUserId: string,
  product: string,
  auth0: HaDebugAuth0Client,
  cognito: HaDebugCognitoClient,
  ddb: HaDebugDynamoDBClient,
  opts: { clientId?: string; connectionId?: string } = {},
): Promise<MfaNotEnforcedCaseFile> {
  const identity = await resolveSubject(emailOrUserId, auth0, cognito);
  const lookupId = identity.auth0Id ?? emailOrUserId;

  const [enrollment, factors, cognitoMfa, superAdminMfa, appClient, connectionPolicy] = await Promise.allSettled([
    ddb.getMfaEnrollment(lookupId),
    identity.auth0Id ? auth0.getUserFactors(identity.auth0Id) : Promise.resolve([]),
    identity.cognitoPoolId
      ? cognito.getMfaConfig(identity.cognitoPoolId)
      : Promise.resolve({ mfaStatus: 'USER_NOT_IN_ANY_POOL', softwareTokenEnabled: false, smsMfaEnabled: false }),
    ddb.getSuperAdminMfa(product),
    opts.clientId ? ddb.getAppClient(opts.clientId) : Promise.resolve(undefined),
    opts.connectionId ? auth0.getConnectionMfaPolicy(opts.connectionId) : Promise.resolve(undefined),
  ]);

  const enrollmentData = enrollment.status === 'fulfilled' ? enrollment.value : undefined;
  const factorsData = factors.status === 'fulfilled' ? factors.value : [];
  const cognitoData = cognitoMfa.status === 'fulfilled'
    ? cognitoMfa.value
    : { mfaStatus: 'UNKNOWN', softwareTokenEnabled: false, smsMfaEnabled: false };
  const superAdminData = superAdminMfa.status === 'fulfilled' ? superAdminMfa.value : undefined;
  const appClientData = appClient.status === 'fulfilled' ? appClient.value : undefined;
  const connectionData = connectionPolicy.status === 'fulfilled' ? connectionPolicy.value : undefined;

  return {
    identity,
    mfaEnrollment: {
      found: !!enrollmentData,
      requiresMfa: enrollmentData?.requiresMfa,
    },
    auth0Factors: factorsData,
    cognitoMfaConfig: cognitoData,
    superAdminMfa: {
      found: !!superAdminData,
      product: superAdminData?.product,
      enabled: superAdminData?.enabled,
      tenantList: superAdminData?.tenantList,
      disabledAt: superAdminData?.disabledAt,
      expiresAt: superAdminData?.expiresAt,
      expiresInMs: superAdminData?.expiresAt != null
        ? superAdminData.expiresAt * 1000 - Date.now()
        : undefined,
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
    ...(opts.connectionId !== undefined && {
      connectionMfaPolicy: {
        found: connectionData !== undefined,
        requiresMfa: connectionData?.requiresMfa,
      },
    }),
    assembledAt: new Date().toISOString(),
  };
}
