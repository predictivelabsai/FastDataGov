-- Governance authoring, accountability, products, workflow history and operations.

CREATE TABLE fast_datagov.data_products (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    domain_id BIGINT REFERENCES fast_datagov.domains(id) ON DELETE SET NULL,
    owner_email TEXT,
    steward_email TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'deprecated')),
    service_level TEXT NOT NULL DEFAULT '',
    access_guidance TEXT NOT NULL DEFAULT '',
    certification_status TEXT NOT NULL DEFAULT 'uncertified',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fast_datagov.product_assets (
    product_id BIGINT NOT NULL REFERENCES fast_datagov.data_products(id) ON DELETE CASCADE,
    asset_id BIGINT NOT NULL REFERENCES fast_datagov.assets(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL DEFAULT 'output' CHECK (relationship IN ('input', 'output', 'supporting')),
    PRIMARY KEY (product_id, asset_id)
);

CREATE TABLE fast_datagov.accountability_assignments (
    id BIGSERIAL PRIMARY KEY,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('domain', 'product', 'asset')),
    scope_id BIGINT NOT NULL,
    responsibility TEXT NOT NULL CHECK (responsibility IN ('owner', 'steward')),
    assignee_email TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at TIMESTAMPTZ,
    assigned_by TEXT NOT NULL,
    attested_at TIMESTAMPTZ,
    attestation_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope_type, scope_id, responsibility, assignee_email)
);
CREATE INDEX accountability_scope_idx ON fast_datagov.accountability_assignments(scope_type, scope_id, responsibility);

CREATE TABLE fast_datagov.asset_revisions (
    id BIGSERIAL PRIMARY KEY,
    asset_id BIGINT NOT NULL REFERENCES fast_datagov.assets(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    change_note TEXT NOT NULL DEFAULT '',
    changed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, version)
);

CREATE TABLE fast_datagov.glossary_term_revisions (
    id BIGSERIAL PRIMARY KEY,
    term_id BIGINT NOT NULL REFERENCES fast_datagov.glossary_terms(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    change_note TEXT NOT NULL DEFAULT '',
    changed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (term_id, version)
);

CREATE TABLE fast_datagov.quality_rule_revisions (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT NOT NULL REFERENCES fast_datagov.quality_rules(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    change_note TEXT NOT NULL DEFAULT '',
    changed_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (rule_id, version)
);

ALTER TABLE fast_datagov.quality_rules ADD COLUMN next_run_at TIMESTAMPTZ;
ALTER TABLE fast_datagov.quality_rules ADD COLUMN execution_engine TEXT NOT NULL DEFAULT 'platform_sql';
ALTER TABLE fast_datagov.lineage_edges ADD COLUMN created_by TEXT;
ALTER TABLE fast_datagov.lineage_edges ADD COLUMN reviewed_at TIMESTAMPTZ;
ALTER TABLE fast_datagov.lineage_edges ADD COLUMN reviewed_by TEXT;
ALTER TABLE fast_datagov.certifications ADD COLUMN renewal_of_id BIGINT REFERENCES fast_datagov.certifications(id) ON DELETE SET NULL;
ALTER TABLE fast_datagov.certifications ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'asset';

CREATE TABLE fast_datagov.work_item_comments (
    id BIGSERIAL PRIMARY KEY,
    work_item_id BIGINT NOT NULL REFERENCES fast_datagov.work_items(id) ON DELETE CASCADE,
    author_email TEXT NOT NULL,
    body TEXT NOT NULL CHECK (length(trim(body)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fast_datagov.work_item_events (
    id BIGSERIAL PRIMARY KEY,
    work_item_id BIGINT NOT NULL REFERENCES fast_datagov.work_items(id) ON DELETE CASCADE,
    actor_email TEXT NOT NULL,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX work_item_events_item_idx ON fast_datagov.work_item_events(work_item_id, created_at);

CREATE TABLE fast_datagov.workflow_definitions (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL UNIQUE CHECK (kind IN ('quality', 'certification', 'metadata', 'access', 'attestation')),
    display_name TEXT NOT NULL,
    default_assignee_role TEXT NOT NULL,
    due_days INTEGER NOT NULL DEFAULT 7 CHECK (due_days > 0),
    approval_role TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO fast_datagov.workflow_definitions (kind, display_name, default_assignee_role, due_days, approval_role)
VALUES
    ('quality', 'Quality remediation', 'steward', 3, 'owner'),
    ('certification', 'Asset certification', 'owner', 7, 'governance_lead'),
    ('metadata', 'Metadata enrichment', 'steward', 7, 'owner'),
    ('access', 'Data access request', 'owner', 3, 'owner'),
    ('attestation', 'Ownership attestation', 'owner', 14, 'governance_lead');

CREATE TABLE fast_datagov.notification_channels (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    channel_type TEXT NOT NULL CHECK (channel_type IN ('email', 'teams', 'slack', 'webhook')),
    endpoint_ref TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    events TEXT[] NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fast_datagov.notification_outbox (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT REFERENCES fast_datagov.notification_channels(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    recipient TEXT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sending', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX notification_outbox_claim_idx ON fast_datagov.notification_outbox(status, available_at, id);

CREATE TABLE fast_datagov.connection_health_checks (
    id BIGSERIAL PRIMARY KEY,
    connection_id BIGINT NOT NULL REFERENCES fast_datagov.connections(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    latency_ms INTEGER,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fast_datagov.pilot_metrics (
    id BIGSERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    unit TEXT NOT NULL,
    baseline NUMERIC,
    target NUMERIC,
    current_value NUMERIC,
    measured_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE fast_datagov.application_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO fast_datagov.pilot_metrics (key, label, unit, target, notes)
VALUES
    ('catalog_coverage', 'Catalog coverage', 'percent', 90, 'Priority assets discovered and searchable'),
    ('accountability_coverage', 'Owner and steward coverage', 'percent', 90, 'Priority assets with both roles'),
    ('quality_rule_coverage', 'Quality rule coverage', 'percent', 75, 'Critical assets with an active rule'),
    ('time_to_trusted_data', 'Time to trusted data', 'hours', 8, 'Median discovery-to-approved-use duration'),
    ('weekly_active_users', 'Weekly active users', 'users', 20, 'Unique catalog users over seven days');
