import {
  CognitoIdentityProviderClient,
  CognitoIdentityProviderClientConfig,
  AdminGetUserCommand,
  GetUserPoolMfaConfigCommand,
} from '@aws-sdk/client-cognito-identity-provider';
import { Credentials } from '../auth';
import { DataSourceError } from '../errors';

export interface CognitoUser {
  username: string;
  userStatus: string;
  enabled: boolean;
  userCreateDate?: Date;
  userLastModifiedDate?: Date;
  attributes: Record<string, string>;
}

export interface CognitoMfaConfig {
  mfaStatus: string;
  softwareTokenEnabled: boolean;
  smsMfaEnabled: boolean;
}

export class HaDebugCognitoClient {
  private readonly client: CognitoIdentityProviderClient;
  private readonly userPoolId: string;

  constructor(creds: Credentials) {
    const config: CognitoIdentityProviderClientConfig = { region: creds.awsRegion };
    if (creds.awsAccessKeyId && creds.awsSecretAccessKey) {
      config.credentials = {
        accessKeyId: creds.awsAccessKeyId,
        secretAccessKey: creds.awsSecretAccessKey,
        sessionToken: creds.awsSessionToken,
      };
    }
    this.client = new CognitoIdentityProviderClient(config);
    this.userPoolId = creds.cognitoUserPoolId;
  }

  async getUserByEmail(email: string): Promise<CognitoUser | undefined> {
    try {
      const res = await this.client.send(new AdminGetUserCommand({
        UserPoolId: this.userPoolId,
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
      };
    } catch (err: any) {
      if (err?.name === 'UserNotFoundException') return undefined;
      const kind = err?.name === 'TooManyRequestsException' ? 'throttled' : 'unknown';
      throw new DataSourceError('cognito:admin-get-user', kind, true, err, `Failed to get Cognito user: ${email}`);
    }
  }

  async getMfaConfig(): Promise<CognitoMfaConfig> {
    try {
      const res = await this.client.send(new GetUserPoolMfaConfigCommand({
        UserPoolId: this.userPoolId,
      }));
      return {
        mfaStatus: res.MfaConfiguration ?? 'OFF',
        softwareTokenEnabled: res.SoftwareTokenMfaConfiguration?.Enabled ?? false,
        smsMfaEnabled: (res.SmsMfaConfiguration?.SmsAuthenticationMessage?.length ?? 0) > 0,
      };
    } catch (err) {
      throw new DataSourceError('cognito:mfa-config', 'unknown', false, err, 'Failed to get Cognito MFA config');
    }
  }
}
