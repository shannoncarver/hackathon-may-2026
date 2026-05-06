import { STSClient, GetCallerIdentityCommand } from '@aws-sdk/client-sts';
import { AwsAuthContext, RuntimeContext } from './auth';
import { awsClientConfig } from './aws-session';
import { DataSourceError } from './errors';

export interface CallerIdentity {
  account: string;
  arn: string;
  userId: string;
}

export async function getCallerIdentity(
  creds: AwsAuthContext,
): Promise<CallerIdentity> {
  const sts = new STSClient(awsClientConfig(creds));
  try {
    const res = await sts.send(new GetCallerIdentityCommand({}));
    return {
      account: res.Account ?? '<unknown>',
      arn: res.Arn ?? '<unknown>',
      userId: res.UserId ?? '<unknown>',
    };
  } catch (err) {
    throw classifyAwsCredError(err, creds);
  }
}

export function classifyAwsCredError(
  err: unknown,
  creds: Pick<AwsAuthContext, 'awsProfile' | 'environment'>,
): DataSourceError {
  const e = err as { message?: string; name?: string };
  const msg = e?.message ?? String(err ?? '');
  const name = e?.name ?? '';
  const profile = creds.awsProfile ?? '<ambient>';

  if (
    /Profile .* (could not be found|not found|does not exist)/i.test(msg) ||
    /could not load profile/i.test(msg) ||
    /could not find named profile/i.test(msg) ||
    /Profile .* was not found/i.test(msg)
  ) {
    return new DataSourceError('aws:profile', 'auth', false, err, [
      `AWS profile '${profile}' not found in ~/.aws/config.`,
      ``,
      `If your local profile name differs from the canonical 'linq-platform-services-${creds.environment}',`,
      `pass --aws-profile <your-profile-name> or set LINQ_PLATFORM_SERVICES_AWS_PROFILE=<your-profile-name>.`,
      ``,
      `Otherwise, add this stanza to ~/.aws/config (replace placeholders with values from the LINQ AWS access portal):`,
      ``,
      `[sso-session linq]`,
      `sso_start_url = https://linq.awsapps.com/start`,
      `sso_region = us-east-1`,
      `sso_registration_scopes = sso:account:access`,
      ``,
      `[profile ${profile}]`,
      `sso_session = linq`,
      `sso_account_id = <ACCOUNT_ID>`,
      `sso_role_name = <ROLE_NAME>`,
      `region = us-east-1`,
      ``,
      `Original error: ${msg}`,
    ].join('\n'));
  }

  if (
    /expired/i.test(msg) ||
    /SSO session/i.test(msg) ||
    /token .* (invalid|expired|missing)/i.test(msg) ||
    name === 'ExpiredTokenException' ||
    name === 'TokenExpiredException' ||
    name === 'CredentialsProviderError' ||
    name === 'NoCredentialsError'
  ) {
    return new DataSourceError('aws:sts', 'auth', false, err, [
      `Could not resolve AWS identity for profile '${profile}'. SSO token likely expired or never issued.`,
      ``,
      `Run: aws sso login --sso-session linq`,
      ``,
      `That command warms every profile that references the 'linq' SSO session — including this one.`,
      `Original error: ${msg}`,
    ].join('\n'));
  }

  return new DataSourceError('aws:sts', 'unknown', false, err, `STS GetCallerIdentity failed: ${msg}`);
}

export function printAuditBanner(ctx: RuntimeContext, identity: CallerIdentity, resources: string[]): void {
  const lines = [
    `─── ha-debug audit banner ───`,
    `env=${ctx.environment}`,
    `profile=${ctx.awsProfile ?? '<ambient>'}`,
    `account=${identity.account}`,
    `arn=${identity.arn}`,
    `region=${ctx.awsRegion}`,
    `auth0Domain=${ctx.auth0Domain}`,
    `resources:`,
    ...resources.map(r => `  - ${r}`),
    `──────────────────────────────`,
  ];
  process.stderr.write(lines.join('\n') + '\n');
}
