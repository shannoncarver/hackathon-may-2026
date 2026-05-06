export type Environment = 'dev' | 'prod';

export const WIKI_CASES_DIR = 'knowledge/wiki/cases';

export interface AwsAuthContext {
  environment: Environment;
  awsRegion: string;
  awsProfile: string | null;
}

export interface RuntimeContext extends AwsAuthContext {
  accountsTableName: string;
  appClientsTableName: string;
  superAdminMfaTableName: string;
  auth0Domain: string;
  auth0ClientId: string;
  auth0ClientSecret: string;
  cognitoUserPoolIds: string[];
  cwLogGroupNames: string[];
}

export interface ResolveOptions {
  environment: Environment;
  awsProfileFlag?: string;
}

const PRODUCT_PROFILE_ENV = 'LINQ_PLATFORM_SERVICES_AWS_PROFILE';
const AMBIENT_FLAG_ENV = 'LINQ_AWS_USE_AMBIENT_CHAIN';

export function resolveAwsProfile(opts: ResolveOptions): string | null {
  if (opts.awsProfileFlag !== undefined) {
    return opts.awsProfileFlag === '' ? null : opts.awsProfileFlag;
  }
  const explicit = process.env[PRODUCT_PROFILE_ENV];
  if (explicit && explicit.trim() !== '') return explicit.trim();
  if (process.env[AMBIENT_FLAG_ENV] === '1') return null;
  return `linq-platform-services-${opts.environment}`;
}

export function resolveAwsAuthContext(opts: ResolveOptions): AwsAuthContext {
  return {
    environment: opts.environment,
    awsRegion: process.env.AWS_REGION ?? 'us-east-1',
    awsProfile: resolveAwsProfile(opts),
  };
}
