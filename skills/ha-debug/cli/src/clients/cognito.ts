import {
  CognitoIdentityProviderClient,
  AdminGetUserCommand,
  DescribeUserPoolCommand,
  GetUserPoolMfaConfigCommand,
} from '@aws-sdk/client-cognito-identity-provider';
import { RuntimeContext } from '../auth';
import { awsClientConfig } from '../aws-session';
import { DataSourceError } from '../errors';

export interface CognitoUser {
  username: string;
  userStatus: string;
  enabled: boolean;
  userCreateDate?: Date;
  userLastModifiedDate?: Date;
  attributes: Record<string, string>;
  poolId: string;
}

export interface CognitoMfaConfig {
  mfaStatus: string;
  softwareTokenEnabled: boolean;
  smsMfaEnabled: boolean;
  poolId?: string;
}

export class HaDebugCognitoClient {
  private readonly client: CognitoIdentityProviderClient;
  private readonly poolIds: string[];

  constructor(ctx: RuntimeContext) {
    this.client = new CognitoIdentityProviderClient(awsClientConfig(ctx));
    this.poolIds = ctx.cognitoUserPoolIds;
  }

  get pools(): string[] {
    return [...this.poolIds];
  }

  async describeUserPool(poolId: string): Promise<{ ok: true } | { ok: false; reason: string }> {
    try {
      await this.client.send(new DescribeUserPoolCommand({ UserPoolId: poolId }));
      return { ok: true };
    } catch (err) {
      const e = err as { name?: string; message?: string };
      const name = e?.name ?? '';
      if (name === 'ResourceNotFoundException') {
        return { ok: false, reason: `Cognito user pool '${poolId}' not found in this account/region.` };
      }
      if (name === 'AccessDeniedException' || name === 'NotAuthorizedException') {
        return { ok: false, reason: `Access denied to user pool '${poolId}'. The SSO role lacks cognito-idp:DescribeUserPool.` };
      }
      return { ok: false, reason: e?.message ?? String(err) };
    }
  }

  async getUserByEmail(email: string): Promise<CognitoUser | undefined> {
    if (this.poolIds.length === 0) return undefined;
    let lastError: unknown;
    for (const poolId of this.poolIds) {
      try {
        const res = await this.client.send(new AdminGetUserCommand({
          UserPoolId: poolId,
          Username: email,
        }));
        const attributes: Record<string, string> = {};
        for (const attr of res.UserAttributes ?? []) {
          if (attr.Name && attr.Value !== undefined) attributes[attr.Name] = attr.Value;
        }
        return {
          username: res.Username ?? email,
          userStatus: res.UserStatus ?? 'UNKNOWN',
          enabled: res.Enabled ?? false,
          userCreateDate: res.UserCreateDate,
          userLastModifiedDate: res.UserLastModifiedDate,
          attributes,
          poolId,
        };
      } catch (err: unknown) {
        const e = err as { name?: string };
        if (e?.name === 'UserNotFoundException') continue;
        if (e?.name === 'TooManyRequestsException') {
          throw new DataSourceError('cognito:admin-get-user', 'throttled', true, err, `Cognito throttled looking up ${email} in pool ${poolId}`);
        }
        lastError = err;
      }
    }
    if (lastError) {
      throw new DataSourceError('cognito:admin-get-user', 'unknown', true, lastError, `Failed to get Cognito user: ${email}`);
    }
    return undefined;
  }

  async getMfaConfig(poolId: string): Promise<CognitoMfaConfig> {
    try {
      const res = await this.client.send(new GetUserPoolMfaConfigCommand({
        UserPoolId: poolId,
      }));
      return {
        mfaStatus: res.MfaConfiguration ?? 'OFF',
        softwareTokenEnabled: res.SoftwareTokenMfaConfiguration?.Enabled ?? false,
        smsMfaEnabled: (res.SmsMfaConfiguration?.SmsAuthenticationMessage?.length ?? 0) > 0,
        poolId,
      };
    } catch (err) {
      throw new DataSourceError('cognito:mfa-config', 'unknown', false, err, `Failed to get Cognito MFA config for pool ${poolId}`);
    }
  }
}
