-- XX-01: read-only role for Ask Your Listening (ask.connect_readonly).
--
-- MANUAL migration: lives in migrations/manual/ so the hourly
-- db.init_db() (top-level migrations/*.sql only) never applies it.
-- Run it by hand as the same user dbt builds the marts with (Railway's
-- `postgres`), so the default privileges below cover rebuilt marts.
-- Idempotent: safe to re-run.
--
-- The role is created NOLOGIN and holds no password here. Afterwards,
-- once, in psql:  \password mccoy_ask   then  ALTER ROLE mccoy_ask LOGIN;
-- and set ASK_DATABASE_URL to log in as mccoy_ask (see BLOCKED.md).
--
-- Row cap: Postgres has no per-role row limit, so it stays app-side
-- (ask.ROW_LIMIT via fetchmany). The timeout mirrors
-- ask.STATEMENT_TIMEOUT_MS; ask also sets both per transaction.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mccoy_ask') THEN
        CREATE ROLE mccoy_ask NOLOGIN NOSUPERUSER NOCREATEDB
            NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END
$$;

ALTER ROLE mccoy_ask SET statement_timeout = '5s';
ALTER ROLE mccoy_ask SET default_transaction_read_only = on;

-- dbt creates marts on its first build; create it early if needed.
CREATE SCHEMA IF NOT EXISTS marts;

GRANT USAGE ON SCHEMA marts TO mccoy_ask;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO mccoy_ask;

-- dbt rebuilds each mart as a new table every hour; grant on those too.
ALTER DEFAULT PRIVILEGES IN SCHEMA marts
    GRANT SELECT ON TABLES TO mccoy_ask;
