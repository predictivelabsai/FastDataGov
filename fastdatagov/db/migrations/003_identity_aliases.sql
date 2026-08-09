-- Explicit mapping from corporate identities/groups to source-platform principals.

CREATE TABLE fastdatagov.principal_aliases (
    id BIGSERIAL PRIMARY KEY,
    identity_principal_type TEXT NOT NULL CHECK (identity_principal_type IN ('user', 'group')),
    identity_key TEXT NOT NULL,
    platform_key TEXT NOT NULL,
    source_principal_key TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (identity_principal_type, identity_key, platform_key, source_principal_key)
);
CREATE INDEX principal_alias_identity_idx ON fastdatagov.principal_aliases(identity_principal_type, identity_key);
