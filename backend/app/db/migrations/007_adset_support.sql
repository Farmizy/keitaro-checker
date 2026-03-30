-- Adset budget control support (ABO campaigns)
-- Adsets are stored as rows in campaigns table with budget_level='adset'

-- Unique constraint for adset upsert (fb_account_id + fb_adset_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_campaigns_adset_unique
ON campaigns (fb_account_id, fb_adset_id)
WHERE fb_adset_id IS NOT NULL;

-- Default for budget_level
ALTER TABLE campaigns
ALTER COLUMN budget_level SET DEFAULT 'campaign';
