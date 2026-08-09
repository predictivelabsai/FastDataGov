ALTER TABLE fast_datagov.asset_fields ADD COLUMN business_description TEXT NOT NULL DEFAULT '';
ALTER TABLE fast_datagov.asset_fields ADD COLUMN business_updated_by TEXT;
ALTER TABLE fast_datagov.asset_fields ADD COLUMN business_updated_at TIMESTAMPTZ;
