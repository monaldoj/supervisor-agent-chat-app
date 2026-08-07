/**
 * Environment-agnostic database connection utilities
 * Can be used in both Next.js server components and Node.js contexts
 */

export interface DatabaseConfig {
  host: string;
  port: string;
  database: string;
  sslMode: string;
}

export interface DatabaseCredentials {
  username: string;
  password: string;
}

/**
 * Get the database schema name to use
 * Hardcoded to ai_chatbot for consistency with drizzle-kit generate
 */
export function getSchemaName(): string {
  const schemaName = 'ai_chatbot';
  console.log(`[getSchemaName] Using hardcoded schema: ${schemaName}`);
  return schemaName;
}

/**
 * Get database configuration from environment variables
 */
export function getDatabaseConfigFromEnv(): DatabaseConfig | null {
  const rawHost = process.env.PGHOST;
  const pgDatabase = process.env.PGDATABASE;
  const pgSSLMode = process.env.PGSSLMODE || 'require';

  // Sanitize PGHOST: values coming from `read_write_dns` (or a hand-edited .env)
  // may carry a protocol, a trailing slash, surrounding whitespace, or an
  // embedded port. Any of those would produce a connection string that
  // `postgres()` rejects with a bare "Invalid URL". Normalize to a bare host
  // and lift an embedded port out into PGPORT.
  let host = rawHost
    ?.trim()
    .replace(/^[a-z]+:\/\//i, '')
    .replace(/\/+$/, '');
  let embeddedPort: string | undefined;
  if (host?.includes(':')) {
    [host, embeddedPort] = host.split(':', 2);
  }

  const pgPort = process.env.PGPORT || embeddedPort || '5432';

  if (!host || !pgDatabase) {
    return null;
  }

  return {
    host,
    port: pgPort,
    database: pgDatabase,
    sslMode: pgSSLMode,
  };
}

/**
 * Check if database storage is available
 */
export function isDatabaseAvailable(): boolean {
  const isAvailable = !!(process.env.PGDATABASE || process.env.POSTGRES_URL);
  console.log(`[isDatabaseAvailable] Database available: ${isAvailable}`);
  return isAvailable;
}

/**
 * Build PostgreSQL connection URL from config and credentials
 */
export function buildConnectionUrl(
  config: DatabaseConfig,
  credentials: DatabaseCredentials,
): string {
  const encodedUser = encodeURIComponent(credentials.username);
  const encodedPassword = encodeURIComponent(credentials.password);

  return `postgresql://${encodedUser}:${encodedPassword}@${config.host}:${config.port}/${config.database}?sslmode=${config.sslMode}`;
}

/**
 * Get connection URL using POSTGRES_URL if available
 */
export function getPostgresUrlFromEnv(): string | null {
  return process.env.POSTGRES_URL || null;
}

/**
 * Validate that required database environment variables are set
 */
export function validateDatabaseConfig(): void {
  if (!isDatabaseAvailable()) {
    throw new Error('Either POSTGRES_URL or PGHOST and PGDATABASE must be set');
  }
}
