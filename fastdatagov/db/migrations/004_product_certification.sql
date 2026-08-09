CREATE TABLE fastdatagov.product_certifications (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES fastdatagov.data_products(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('certified','verified','rejected','expired')),
    certified_by TEXT NOT NULL,
    certified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    notes TEXT NOT NULL DEFAULT '',
    renewal_of_id BIGINT REFERENCES fastdatagov.product_certifications(id) ON DELETE SET NULL
);
