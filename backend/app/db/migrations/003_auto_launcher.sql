-- auto_launch_settings (singleton)
CREATE TABLE IF NOT EXISTS auto_launch_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    is_enabled BOOLEAN DEFAULT true,
    analysis_hour INT DEFAULT 23,
    analysis_minute INT DEFAULT 0,
    launch_hour INT DEFAULT 4,
    launch_minute INT DEFAULT 0,
    min_roi_threshold NUMERIC(10,2) DEFAULT 0,
    starting_budget NUMERIC(10,2) DEFAULT 30.00,
    new_campaign_max_activity_days INT DEFAULT 1,
    proven_min_activity_days INT DEFAULT 2,
    blacklist_zero_leads_days INT DEFAULT 2,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO auto_launch_settings (id) VALUES (gen_random_uuid())
ON CONFLICT DO NOTHING;

-- auto_launch_queue
CREATE TABLE IF NOT EXISTS auto_launch_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    fb_campaign_id TEXT NOT NULL,
    panel_campaign_id INT,
    fb_campaign_name TEXT NOT NULL,
    fb_account_id UUID REFERENCES fb_accounts(id),
    launch_type TEXT NOT NULL CHECK (launch_type IN ('new', 'proven')),
    target_budget NUMERIC(10,2) NOT NULL DEFAULT 30.00,
    analysis_data JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'removed', 'launched', 'skipped', 'failed')),
    removal_reason TEXT,
    launch_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    launched_at TIMESTAMPTZ,
    error_message TEXT,
    UNIQUE(campaign_id, launch_date)
);

CREATE INDEX IF NOT EXISTS idx_alq_launch_date_status ON auto_launch_queue(launch_date, status);

-- auto_launch_blacklist
CREATE TABLE IF NOT EXISTS auto_launch_blacklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) UNIQUE,
    fb_campaign_id TEXT NOT NULL,
    fb_campaign_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    blacklisted_at TIMESTAMPTZ DEFAULT NOW(),
    blacklisted_by TEXT DEFAULT 'system' CHECK (blacklisted_by IN ('system', 'user'))
);

-- RLS
ALTER TABLE auto_launch_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE auto_launch_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE auto_launch_blacklist ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anon can select auto_launch_settings" ON auto_launch_settings FOR SELECT USING (true);
CREATE POLICY "Anon can insert auto_launch_settings" ON auto_launch_settings FOR INSERT WITH CHECK (true);
CREATE POLICY "Anon can update auto_launch_settings" ON auto_launch_settings FOR UPDATE USING (true);
CREATE POLICY "Anon can delete auto_launch_settings" ON auto_launch_settings FOR DELETE USING (true);

CREATE POLICY "Anon can select auto_launch_queue" ON auto_launch_queue FOR SELECT USING (true);
CREATE POLICY "Anon can insert auto_launch_queue" ON auto_launch_queue FOR INSERT WITH CHECK (true);
CREATE POLICY "Anon can update auto_launch_queue" ON auto_launch_queue FOR UPDATE USING (true);
CREATE POLICY "Anon can delete auto_launch_queue" ON auto_launch_queue FOR DELETE USING (true);

CREATE POLICY "Anon can select auto_launch_blacklist" ON auto_launch_blacklist FOR SELECT USING (true);
CREATE POLICY "Anon can insert auto_launch_blacklist" ON auto_launch_blacklist FOR INSERT WITH CHECK (true);
CREATE POLICY "Anon can update auto_launch_blacklist" ON auto_launch_blacklist FOR UPDATE USING (true);
CREATE POLICY "Anon can delete auto_launch_blacklist" ON auto_launch_blacklist FOR DELETE USING (true);
