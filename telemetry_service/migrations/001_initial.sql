-- PostgreSQL baseline for the Alpha Horizon installation telemetry service.
-- SQLAlchemy uses the equivalent schema in development; production deployment
-- records this migration in the platform's governed migration runner.

CREATE TABLE IF NOT EXISTS telemetry_installations (
    installation_key VARCHAR(64) PRIMARY KEY,
    instance_nonce_key VARCHAR(64) NOT NULL,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(24) NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ,
    last_version VARCHAR(32) NOT NULL,
    build_id VARCHAR(64) NOT NULL,
    release_channel VARCHAR(24) NOT NULL,
    distribution_channel VARCHAR(40) NOT NULL,
    platform_family VARCHAR(16) NOT NULL,
    architecture VARCHAR(24) NOT NULL,
    install_type VARCHAR(24) NOT NULL,
    operation_mode VARCHAR(24) NOT NULL,
    consent_notice_version VARCHAR(16) NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id VARCHAR(36) PRIMARY KEY,
    installation_key VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    shogun_version VARCHAR(32) NOT NULL,
    build_id VARCHAR(64) NOT NULL,
    release_channel VARCHAR(24) NOT NULL,
    distribution_channel VARCHAR(40) NOT NULL,
    platform_family VARCHAR(16) NOT NULL,
    architecture VARCHAR(24) NOT NULL,
    install_type VARCHAR(24) NOT NULL,
    operation_mode VARCHAR(24) NOT NULL,
    schema_version INTEGER NOT NULL,
    counted BOOLEAN NOT NULL,
    CONSTRAINT uq_event_installation UNIQUE (event_id, installation_key)
);

CREATE INDEX IF NOT EXISTS ix_telemetry_events_installation_key
    ON telemetry_events (installation_key);
CREATE INDEX IF NOT EXISTS ix_telemetry_events_type
    ON telemetry_events (event_type);

CREATE TABLE IF NOT EXISTS telemetry_consent_history (
    id BIGSERIAL PRIMARY KEY,
    installation_key VARCHAR(64),
    action VARCHAR(32) NOT NULL,
    notice_version VARCHAR(16) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_admin_audit (
    id BIGSERIAL PRIMARY KEY,
    actor VARCHAR(255) NOT NULL,
    action VARCHAR(80) NOT NULL,
    detail TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL
);
