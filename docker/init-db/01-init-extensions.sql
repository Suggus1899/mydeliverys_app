-- MyDeliveryS Database Initialization Script
-- This runs automatically when PostgreSQL container starts for the first time

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Create additional schemas if needed
-- CREATE SCHEMA IF NOT EXISTS audit;
-- CREATE SCHEMA IF NOT EXISTS financial;

-- Set default timezone
SET timezone = 'America/Caracas';

-- Configure PostgreSQL for better performance with PgBouncer
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '1.5GB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET max_worker_processes = 8;
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;

-- Reload configuration
SELECT pg_reload_conf();

-- Create a read-only role for reporting (optional)
-- CREATE ROLE mydeliverys_readonly;
-- GRANT USAGE ON SCHEMA public TO mydeliverys_readonly;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO mydeliverys_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mydeliverys_readonly;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'MyDeliveryS database initialized with PostGIS %', postgis_version();
END $$;