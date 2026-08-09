CREATE INDEX tags_search_idx ON fastdatagov.tags USING GIN (to_tsvector('english',coalesce(label,'')||' '||coalesce(key,'')));
CREATE INDEX glossary_search_idx ON fastdatagov.glossary_terms USING GIN (to_tsvector('english',coalesce(name,'')||' '||coalesce(definition,'')));
CREATE INDEX fields_search_idx ON fastdatagov.asset_fields USING GIN (to_tsvector('english',coalesce(name,'')||' '||coalesce(description,'')||' '||coalesce(business_description,'')||' '||coalesce(classification,'')));
CREATE INDEX assets_owner_idx ON fastdatagov.assets(owner_email) WHERE deleted_at IS NULL;
CREATE INDEX assets_sensitivity_idx ON fastdatagov.assets(sensitivity) WHERE deleted_at IS NULL;
CREATE INDEX assets_refreshed_idx ON fastdatagov.assets(refreshed_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX certifications_expiry_idx ON fastdatagov.certifications(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX product_certifications_expiry_idx ON fastdatagov.product_certifications(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX accountability_expiry_idx ON fastdatagov.accountability_assignments(attestation_expires_at) WHERE attestation_expires_at IS NOT NULL;
