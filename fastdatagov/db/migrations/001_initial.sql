-- FastDataGov initial schema. All application SQL must qualify this schema.

CREATE TABLE IF NOT EXISTS fastdatagov.users (
    id BIGSERIAL PRIMARY KEY,
    subject TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS fastdatagov.role_bindings (
    id BIGSERIAL PRIMARY KEY,
    principal_type TEXT NOT NULL CHECK (principal_type IN ('user', 'group')),
    principal_key TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('consumer', 'steward', 'owner', 'engineer', 'governance_lead', 'admin')),
    scope_type TEXT NOT NULL DEFAULT 'global' CHECK (scope_type IN ('global', 'domain', 'asset')),
    scope_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (principal_type, principal_key, role, scope_type, scope_key)
);

CREATE TABLE IF NOT EXISTS fastdatagov.domains (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    parent_id BIGINT REFERENCES fastdatagov.domains(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastdatagov.platforms (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastdatagov.connections (
    id BIGSERIAL PRIMARY KEY,
    platform_id BIGINT NOT NULL REFERENCES fastdatagov.platforms(id),
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    credential_ref TEXT,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'not_configured',
    last_sync_at TIMESTAMPTZ,
    last_error TEXT,
    sync_cursor JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastdatagov.assets (
    id BIGSERIAL PRIMARY KEY,
    connection_id BIGINT NOT NULL REFERENCES fastdatagov.connections(id),
    external_id TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    platform_key TEXT NOT NULL,
    domain_id BIGINT REFERENCES fastdatagov.domains(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    business_description TEXT NOT NULL DEFAULT '',
    owner_email TEXT,
    steward_email TEXT,
    sensitivity TEXT NOT NULL DEFAULT 'internal',
    certification_status TEXT NOT NULL DEFAULT 'uncertified',
    quality_score NUMERIC(5,2),
    trust_score NUMERIC(5,2),
    access_guidance TEXT NOT NULL DEFAULT '',
    source_url TEXT,
    native_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    refreshed_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (connection_id, external_id)
);
CREATE INDEX IF NOT EXISTS assets_platform_idx ON fastdatagov.assets(platform_key, asset_type);
CREATE INDEX IF NOT EXISTS assets_domain_idx ON fastdatagov.assets(domain_id);
CREATE INDEX IF NOT EXISTS assets_quality_idx ON fastdatagov.assets(quality_score);
CREATE INDEX IF NOT EXISTS assets_search_idx ON fastdatagov.assets USING GIN (
    to_tsvector('english', coalesce(name, '') || ' ' || coalesce(qualified_name, '') || ' ' ||
        coalesce(description, '') || ' ' || coalesce(business_description, ''))
);

CREATE TABLE IF NOT EXISTS fastdatagov.asset_fields (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    ordinal INTEGER,
    data_type TEXT,
    nullable BOOLEAN,
    description TEXT NOT NULL DEFAULT '',
    classification TEXT,
    native_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (asset_id, external_id)
);
CREATE INDEX IF NOT EXISTS asset_fields_asset_idx ON fastdatagov.asset_fields(asset_id, ordinal);

CREATE TABLE IF NOT EXISTS fastdatagov.tags (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'business',
    colour TEXT NOT NULL DEFAULT '#475569'
);

CREATE TABLE IF NOT EXISTS fastdatagov.asset_tags (
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES fastdatagov.tags(id) ON DELETE CASCADE,
    source TEXT NOT NULL DEFAULT 'fastdatagov',
    PRIMARY KEY (asset_id, tag_id)
);

CREATE TABLE IF NOT EXISTS fastdatagov.glossary_terms (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    definition TEXT NOT NULL,
    domain_id BIGINT REFERENCES fastdatagov.domains(id) ON DELETE SET NULL,
    owner_email TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastdatagov.asset_terms (
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    term_id BIGINT NOT NULL REFERENCES fastdatagov.glossary_terms(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL DEFAULT 'describes',
    PRIMARY KEY (asset_id, term_id)
);

CREATE TABLE IF NOT EXISTS fastdatagov.lineage_edges (
    id BIGSERIAL PRIMARY KEY,
    source_asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    target_asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    source_field_id BIGINT REFERENCES fastdatagov.asset_fields(id) ON DELETE CASCADE,
    target_field_id BIGINT REFERENCES fastdatagov.asset_fields(id) ON DELETE CASCADE,
    operation TEXT NOT NULL DEFAULT 'transforms',
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('native', 'query_history', 'inferred', 'manual')),
    confidence NUMERIC(4,3) NOT NULL DEFAULT 1.0,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (source_asset_id, target_asset_id, source_field_id, target_field_id, operation)
);
CREATE INDEX IF NOT EXISTS lineage_source_idx ON fastdatagov.lineage_edges(source_asset_id);
CREATE INDEX IF NOT EXISTS lineage_target_idx ON fastdatagov.lineage_edges(target_asset_id);

CREATE TABLE IF NOT EXISTS fastdatagov.quality_rules (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    expression TEXT NOT NULL,
    threshold NUMERIC(10,4),
    severity TEXT NOT NULL DEFAULT 'medium',
    enabled BOOLEAN NOT NULL DEFAULT true,
    schedule TEXT NOT NULL DEFAULT 'daily',
    version INTEGER NOT NULL DEFAULT 1,
    owner_email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fastdatagov.quality_runs (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT NOT NULL REFERENCES fastdatagov.quality_rules(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'passed', 'failed', 'error')),
    score NUMERIC(5,2),
    observed_value NUMERIC(18,6),
    rows_evaluated BIGINT,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS quality_runs_rule_idx ON fastdatagov.quality_runs(rule_id, started_at DESC);

CREATE TABLE IF NOT EXISTS fastdatagov.work_items (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('quality', 'certification', 'metadata', 'access', 'attestation')),
    asset_id BIGINT REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'waiting', 'approved', 'resolved', 'rejected')),
    priority TEXT NOT NULL DEFAULT 'medium',
    assignee_email TEXT,
    requester_email TEXT,
    due_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS work_items_queue_idx ON fastdatagov.work_items(status, kind, assignee_email);

CREATE TABLE IF NOT EXISTS fastdatagov.certifications (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    certified_by TEXT NOT NULL,
    certified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS fastdatagov.usage_rollups (
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    usage_date DATE NOT NULL,
    query_count BIGINT NOT NULL DEFAULT 0,
    distinct_users BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (asset_id, usage_date)
);

CREATE TABLE IF NOT EXISTS fastdatagov.sync_runs (
    id BIGSERIAL PRIMARY KEY,
    connection_id BIGINT NOT NULL REFERENCES fastdatagov.connections(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'partial', 'failed')),
    cursor_before JSONB NOT NULL DEFAULT '{}'::jsonb,
    cursor_after JSONB NOT NULL DEFAULT '{}'::jsonb,
    assets_seen INTEGER NOT NULL DEFAULT 0,
    fields_seen INTEGER NOT NULL DEFAULT 0,
    lineage_edges_seen INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS fastdatagov.jobs (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS jobs_claim_idx ON fastdatagov.jobs(status, run_after, id);

CREATE TABLE IF NOT EXISTS fastdatagov.audit_events (
    id BIGSERIAL PRIMARY KEY,
    actor_subject TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    before_data JSONB,
    after_data JSONB,
    request_id TEXT,
    source_ip INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_entity_idx ON fastdatagov.audit_events(entity_type, entity_key, created_at DESC);

CREATE TABLE IF NOT EXISTS fastdatagov.asset_visibility (
    asset_id BIGINT NOT NULL REFERENCES fastdatagov.assets(id) ON DELETE CASCADE,
    principal_type TEXT NOT NULL CHECK (principal_type IN ('user', 'group', 'public')),
    principal_key TEXT NOT NULL,
    privilege TEXT NOT NULL DEFAULT 'discover',
    source TEXT NOT NULL DEFAULT 'platform_grant',
    PRIMARY KEY (asset_id, principal_type, principal_key, privilege)
);
