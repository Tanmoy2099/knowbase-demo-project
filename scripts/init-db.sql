-- init-db.sql — run once by postgres entrypoint on first container start.
-- Enables PostgreSQL extensions required by the knowbase platform.

-- uuid-ossp: provides uuid_generate_v4() for primary-key generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pgcrypto: provides gen_random_uuid(), crypt(), and digest() utilities
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
