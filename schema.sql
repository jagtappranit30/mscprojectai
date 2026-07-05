-- =============================================================
-- SME Productivity Assessment Platform — Supabase Schema
-- Run this entire file in your Supabase SQL Editor once.
-- =============================================================

-- Enable pgvector extension (required for embedding column)
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================
-- TABLE: sectors
-- =============================================================
CREATE TABLE IF NOT EXISTS sectors (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

-- =============================================================
-- TABLE: benchmark_metrics
-- Stores sector-specific p25/p50/p75 percentile values.
-- NOTE: Values below are DUMMY placeholders derived loosely from
-- ONS IDBR / OECD SME and Entrepreneurship Outlook data.
-- TODO: Replace with real, citable ONS/OECD figures before
-- submission. Update the 'updated_at' timestamp when you do.
-- =============================================================
CREATE TABLE IF NOT EXISTS benchmark_metrics (
    id          SERIAL PRIMARY KEY,
    sector_id   INTEGER NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
    metric_name TEXT    NOT NULL,
    p25         NUMERIC NOT NULL,
    p50         NUMERIC NOT NULL,
    p75         NUMERIC NOT NULL,
    unit        TEXT    NOT NULL DEFAULT '',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sector_id, metric_name)
);

-- =============================================================
-- TABLE: ingestion_runs
-- One row per /assess call (may cover multiple uploaded files).
-- =============================================================
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sector_id    INTEGER REFERENCES sectors(id),
    sector       TEXT,           -- denormalised for quick lookup
    company_name TEXT,
    document_type TEXT,
    file_count   INTEGER NOT NULL DEFAULT 1,
    status       TEXT    NOT NULL DEFAULT 'processing',  -- processing | complete | failed
    error_message TEXT,
    confidence_score NUMERIC
);

-- =============================================================
-- TABLE: document_chunks
-- One row per text chunk; embedding stored as pgvector VECTOR.
-- =============================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_run_id UUID REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    run_id          UUID,  -- also stored flat for join-free RPC lookups
    content         TEXT   NOT NULL,
    embedding       VECTOR(384),   -- bge-small-en-v1.5 produces 384-dim vectors
    source_filename TEXT,
    chunk_index     INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW index for cosine similarity (best performance at Render free tier RAM)
CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- =============================================================
-- TABLE: extracted_metrics
-- Per-metric extraction results with source passage traceability.
-- =============================================================
CREATE TABLE IF NOT EXISTS extracted_metrics (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id       UUID NOT NULL,
    metric_name  TEXT NOT NULL,
    metric_value NUMERIC,
    metric_unit  TEXT,
    confidence   NUMERIC DEFAULT 0,
    source_text  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- TABLE: assessment_results
-- Final scored output per ingestion run.
-- =============================================================
CREATE TABLE IF NOT EXISTS assessment_results (
    result_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  UUID NOT NULL,
    user_id                 UUID,   -- nullable; set if user saves assessment
    labour_efficiency_score NUMERIC,
    financial_health_score  NUMERIC,
    productivity_index      NUMERIC,
    digital_maturity_score  NUMERIC,
    confidence_overall      NUMERIC,
    recommendations         TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- TABLE: users  (preserved from existing prototype — out of spec scope)
-- =============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email        TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    company_name TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================
-- FUNCTION: match_documents
-- Returns top-k chunks by cosine similarity for a given run.
-- Called by rag.py retrieve_context via Supabase RPC.
-- =============================================================
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(384),
    match_count     INTEGER DEFAULT 5,
    p_run_id        UUID    DEFAULT NULL
)
RETURNS TABLE (
    id              UUID,
    chunk_text      TEXT,
    source_filename TEXT,
    similarity      FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.content          AS chunk_text,
        dc.source_filename,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE (p_run_id IS NULL OR dc.run_id = p_run_id)
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================
-- SEED DATA — Sectors
-- =============================================================
INSERT INTO sectors (name, description) VALUES
    ('Retail',         'Retail trade, consumer-facing SMEs'),
    ('Services',       'Professional, business, and personal service SMEs'),
    ('Manufacturing',  'Manufacturing and production SMEs')
ON CONFLICT (name) DO NOTHING;

-- =============================================================
-- SEED DATA — Benchmark Metrics
-- TODO: Replace ALL values below with verified ONS IDBR / OECD
-- percentile data before MSc submission. These are illustrative
-- placeholders calibrated loosely against published SME surveys.
-- Source placeholder: ONS Annual Business Survey 2022 guidance.
-- =============================================================

-- Manufacturing benchmarks
INSERT INTO benchmark_metrics (sector_id, metric_name, p25, p50, p75, unit) VALUES
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'revenue_per_employee',   120000, 175000, 240000, '£'),
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'output_per_payroll',          3.5,    4.2,    5.1, 'ratio'),
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'headcount_efficiency_ratio', 22000,  28000,  36000, '£/employee'),
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'gross_margin',                  25,     35,     45, '%'),
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'operating_margin',               5,     12,     20, '%'),
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'current_ratio',                1.2,    1.8,    2.5, 'ratio'),
    ((SELECT id FROM sectors WHERE name='Manufacturing'), 'quick_ratio',                  0.8,    1.2,    1.8, 'ratio')
ON CONFLICT (sector_id, metric_name) DO NOTHING;

-- Services benchmarks
INSERT INTO benchmark_metrics (sector_id, metric_name, p25, p50, p75, unit) VALUES
    ((SELECT id FROM sectors WHERE name='Services'), 'revenue_per_employee',   100000, 145000, 210000, '£'),
    ((SELECT id FROM sectors WHERE name='Services'), 'output_per_payroll',          2.8,    3.8,    4.9, 'ratio'),
    ((SELECT id FROM sectors WHERE name='Services'), 'headcount_efficiency_ratio', 18000,  24000,  32000, '£/employee'),
    ((SELECT id FROM sectors WHERE name='Services'), 'gross_margin',                  40,     55,     70, '%'),
    ((SELECT id FROM sectors WHERE name='Services'), 'operating_margin',               8,     18,     28, '%'),
    ((SELECT id FROM sectors WHERE name='Services'), 'current_ratio',                1.1,    1.6,    2.3, 'ratio'),
    ((SELECT id FROM sectors WHERE name='Services'), 'quick_ratio',                  0.9,    1.4,    2.0, 'ratio')
ON CONFLICT (sector_id, metric_name) DO NOTHING;

-- Retail benchmarks
INSERT INTO benchmark_metrics (sector_id, metric_name, p25, p50, p75, unit) VALUES
    ((SELECT id FROM sectors WHERE name='Retail'), 'revenue_per_employee',   150000, 190000, 250000, '£'),
    ((SELECT id FROM sectors WHERE name='Retail'), 'output_per_payroll',          4.2,    5.3,    6.5, 'ratio'),
    ((SELECT id FROM sectors WHERE name='Retail'), 'headcount_efficiency_ratio', 25000,  32000,  42000, '£/employee'),
    ((SELECT id FROM sectors WHERE name='Retail'), 'gross_margin',                  20,     28,     38, '%'),
    ((SELECT id FROM sectors WHERE name='Retail'), 'operating_margin',               2,      6,     12, '%'),
    ((SELECT id FROM sectors WHERE name='Retail'), 'current_ratio',                0.9,    1.3,    1.9, 'ratio'),
    ((SELECT id FROM sectors WHERE name='Retail'), 'quick_ratio',                  0.4,    0.7,    1.1, 'ratio')
ON CONFLICT (sector_id, metric_name) DO NOTHING;
