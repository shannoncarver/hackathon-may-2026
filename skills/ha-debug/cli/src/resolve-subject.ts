import { HaDebugAuth0Client } from './clients/auth0';
import { HaDebugCognitoClient } from './clients/cognito';

export interface CanonicalSubject {
  email?: string;
  auth0Id?: string;
  cognitoSub?: string;
  cognitoUsername?: string;
  cognitoStatus?: string;
  cognitoEnabled?: boolean;
  cognitoPoolId?: string;
  auth0Blocked?: boolean;
  resolvedVia: 'auth0' | 'cognito' | 'both' | 'unresolved';
}

export async function resolveSubject(
  emailOrUserId: string,
  auth0: HaDebugAuth0Client,
  cognito: HaDebugCognitoClient,
): Promise<CanonicalSubject> {
  const isAuth0Id = /^(auth0|samlp|waad|google-oauth2)\|/.test(emailOrUserId);
  const isEmail = emailOrUserId.includes('@');

  let auth0Id: string | undefined;
  let email: string | undefined;
  let auth0Blocked: boolean | undefined;

  if (isAuth0Id) {
    auth0Id = emailOrUserId;
  } else if (isEmail) {
    email = emailOrUserId;
    const user = await auth0.getUserByEmail(email).catch(() => undefined);
    auth0Id = user?.userId;
    auth0Blocked = user?.blocked;
  }

  const cognitoUser = email
    ? await cognito.getUserByEmail(email).catch(() => undefined)
    : undefined;

  const resolvedVia =
    auth0Id && cognitoUser ? 'both'
    : auth0Id ? 'auth0'
    : cognitoUser ? 'cognito'
    : 'unresolved';

  return {
    email: email ?? cognitoUser?.attributes['email'],
    auth0Id,
    cognitoSub: cognitoUser?.attributes['sub'],
    cognitoUsername: cognitoUser?.username,
    cognitoStatus: cognitoUser?.userStatus,
    cognitoEnabled: cognitoUser?.enabled,
    cognitoPoolId: cognitoUser?.poolId,
    auth0Blocked,
    resolvedVia,
  };
}
