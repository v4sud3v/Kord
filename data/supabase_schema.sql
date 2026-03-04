-- ============================================================
-- Kord Scholarship Tables — Run this in Supabase SQL Editor
-- ============================================================

-- 1. Scholarships table
CREATE TABLE IF NOT EXISTS scholarships (
    id                     BIGSERIAL PRIMARY KEY,
    source                 TEXT NOT NULL,
    name                   TEXT NOT NULL,
    description            TEXT DEFAULT '',
    eligibility_grade      TEXT,
    eligibility_caste      TEXT,
    eligibility_income_max INTEGER,
    benefits               TEXT DEFAULT '',
    url                    TEXT DEFAULT '',
    tags                   JSONB DEFAULT '[]',
    last_updated           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for fast filtering
CREATE INDEX IF NOT EXISTS idx_scholarships_source
    ON scholarships(source);

CREATE INDEX IF NOT EXISTS idx_scholarships_caste
    ON scholarships(eligibility_caste);

CREATE INDEX IF NOT EXISTS idx_scholarships_grade
    ON scholarships(eligibility_grade);


-- 2. Scrape metadata table (tracks when each source was last scraped)
CREATE TABLE IF NOT EXISTS scrape_meta (
    source          TEXT PRIMARY KEY,
    last_scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    record_count    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'ok'
);


-- 3. Enable Row Level Security (RLS) but allow all operations
--    via service role key (which Kord uses server-side)
ALTER TABLE scholarships ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_meta  ENABLE ROW LEVEL SECURITY;

-- Allow the service role to do everything
CREATE POLICY "service_role_all_scholarships" ON scholarships
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_scrape_meta" ON scrape_meta
    FOR ALL USING (true) WITH CHECK (true);
