import * as fs from 'fs';
import * as path from 'path';
import * as dotenv from 'dotenv';

export interface Credentials {
  awsRegion: string;
  awsAccessKeyId?: string;
  awsSecretAccessKey?: string;
  awsSessionToken?: string;
  auth0Domain: string;
  auth0ClientId: string;
  auth0ClientSecret: string;
  accountsTableName: string;
  superAdminMfaTableName: string;
  appClientsTableName: string;
  cognitoUserPoolId: string;
  cwLogGroupName: string;
  wikiCasesDir: string;
}

export interface AuthProvider {
  getCredentials(): Promise<Credentials>;
}

export class EnvAuthProvider implements AuthProvider {
  private readonly envFile: string;

  constructor(envFile = '.env') {
    this.envFile = path.resolve(process.cwd(), envFile);
  }

  async getCredentials(): Promise<Credentials> {
    if (fs.existsSync(this.envFile)) {
      dotenv.config({ path: this.envFile });
    }

    const required = (key: string): string => {
      const val = process.env[key];
      if (!val) throw new Error(`Missing required env var: ${key}. See ha-debug/.env.example`);
      return val;
    };

    return {
      awsRegion: process.env.AWS_REGION ?? 'us-east-1',
      awsAccessKeyId: process.env.AWS_ACCESS_KEY_ID,
      awsSecretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      awsSessionToken: process.env.AWS_SESSION_TOKEN,
      auth0Domain: required('AUTH0_DOMAIN'),
      auth0ClientId: required('AUTH0_CLIENT_ID'),
      auth0ClientSecret: required('AUTH0_CLIENT_SECRET'),
      accountsTableName: required('ACCOUNTS_TABLE_NAME'),
      superAdminMfaTableName: required('SUPER_ADMIN_MFA_TABLE_NAME'),
      appClientsTableName: required('APP_CLIENTS_TABLE_NAME'),
      cognitoUserPoolId: required('COGNITO_USER_POOL_ID'),
      cwLogGroupName: process.env.CW_LOG_GROUP_NAME ?? '/aws/lambda/harmony-auth',
      wikiCasesDir: process.env.WIKI_CASES_DIR ?? 'knowledge/wiki/cases',
    };
  }
}
