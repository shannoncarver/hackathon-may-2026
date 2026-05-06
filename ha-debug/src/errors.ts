export type ErrorKind = 'missing' | 'throttled' | 'timeout' | 'auth' | 'unknown';

export class DataSourceError extends Error {
  constructor(
    public readonly source: string,
    public readonly kind: ErrorKind,
    public readonly retryable: boolean,
    public readonly raw: unknown,
    message: string,
  ) {
    super(message);
    this.name = 'DataSourceError';
  }
}
