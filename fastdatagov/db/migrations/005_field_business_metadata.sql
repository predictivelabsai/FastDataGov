ALTER TABLE fastdatagov.asset_fields ADD COLUMN business_description TEXT NOT NULL DEFAULT '';
ALTER TABLE fastdatagov.asset_fields ADD COLUMN business_updated_by TEXT;
ALTER TABLE fastdatagov.asset_fields ADD COLUMN business_updated_at TIMESTAMPTZ;
