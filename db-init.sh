#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create the restricted runtime user
    CREATE USER cyberdesk_app WITH PASSWORD '$APP_DB_PASS';

    -- Grant baseline schema access
    GRANT USAGE ON SCHEMA public TO cyberdesk_app;

    -- Ensure cyberdesk_app gets permissions on all FUTURE tables and sequences created by the owner
    ALTER DEFAULT PRIVILEGES FOR ROLE $POSTGRES_USER IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cyberdesk_app;

    ALTER DEFAULT PRIVILEGES FOR ROLE $POSTGRES_USER IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO cyberdesk_app;
EOSQL
