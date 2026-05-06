// Canonical DynamoDB schema types — sourced from Harmony-Auth src/orm/ and src/def/

export interface MultiFactorEnrollment {
  id: string;
  requiresMfa: boolean;
}

export interface SuperAdminMFA {
  product: string;
  enabled: boolean;
  tenantList: string[];
  createdAt: string;
  updatedAt: string;
  disabledAt?: string;
  expiresAt?: number;
}

export interface TokenCache {
  id: string;
  audience: string;
  clientId: string;
  clientSecret: string;
  token: string;
  expiresAt: number;
  ttl?: number;
}

export interface Lock {
  id: string;
  status: string;
  updatedAt: number;
}

export type ClientStatus = 'enabled' | 'disabled';

export interface AppClient {
  id: string;
  name?: string;
  product?: string;
  subdomain?: string;
  status: ClientStatus;
  auth0ClientId?: string;
  clientType?: string;
}
