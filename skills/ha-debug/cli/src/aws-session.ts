import { fromIni } from '@aws-sdk/credential-providers';
import type { AwsCredentialIdentityProvider } from '@aws-sdk/types';
import { AwsAuthContext } from './auth';

export interface AwsBaseConfig {
  region: string;
  credentials?: AwsCredentialIdentityProvider;
}

export function awsClientConfig(ctx: Pick<AwsAuthContext, 'awsRegion' | 'awsProfile'>): AwsBaseConfig {
  if (ctx.awsProfile === null) return { region: ctx.awsRegion };
  return { region: ctx.awsRegion, credentials: fromIni({ profile: ctx.awsProfile }) };
}
