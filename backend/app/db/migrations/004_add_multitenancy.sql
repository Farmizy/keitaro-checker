-- Migration: 004_add_multitenancy
-- Applied via Supabase MCP in 4 steps:
--   1. add_multitenancy_schema
--   2. migrate_existing_data_to_first_user
--   3. update_rls_policies_multitenancy
--   4. add_user_onboarding_trigger
--
-- This file is for reference / version control only.

-- =============================================
-- 1. Schema changes
-- =============================================

ALTER TABLE fb_accounts ADD COLUMN user_id UUID REFERENCES auth.users(id) NOT NULL;
ALTER TABLE rule_sets ADD COLUMN user_id UUID REFERENCES auth.users(id) NOT NULL;
ALTER TABLE auto_launch_settings ADD COLUMN user_id UUID REFERENCES auth.users(id);
ALTER TABLE check_runs ADD COLUMN user_id UUID REFERENCES auth.users(id);

CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) UNIQUE NOT NULL,
    keitaro_url TEXT DEFAULT '',
    keitaro_login TEXT DEFAULT '',
    keitaro_password TEXT DEFAULT '',
    panel_api_url TEXT DEFAULT 'https://fbm.adway.team/api',
    panel_jwt TEXT DEFAULT '',
    telegram_bot_token TEXT DEFAULT '',
    telegram_chat_id TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE fb_account_profiles ENABLE ROW LEVEL SECURITY;

ALTER TABLE fb_accounts DROP CONSTRAINT IF EXISTS fb_accounts_account_id_key;
ALTER TABLE fb_accounts ADD CONSTRAINT fb_accounts_account_id_user_id_key UNIQUE (account_id, user_id);

CREATE INDEX idx_fb_accounts_user_id ON fb_accounts(user_id);
CREATE INDEX idx_rule_sets_user_id ON rule_sets(user_id);
CREATE INDEX idx_auto_launch_settings_user_id ON auto_launch_settings(user_id);
CREATE INDEX idx_check_runs_user_id ON check_runs(user_id);
CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);

-- =============================================
-- 2. RLS policies: tenant-isolated (see migration steps 3 for full list)
-- Pattern: auth.uid() = user_id for root tables,
--          EXISTS join for child tables
-- =============================================

-- =============================================
-- 3. Onboarding trigger: auto-create defaults for new users
-- =============================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE new_rule_set_id UUID;
BEGIN
    INSERT INTO user_settings (user_id) VALUES (NEW.id);
    INSERT INTO rule_sets (user_id, name, description, is_default)
    VALUES (NEW.id, 'Default Ladder', 'Default budget management ladder', true)
    RETURNING id INTO new_rule_set_id;
    INSERT INTO rule_steps (rule_set_id, step_order, spend_threshold, leads_min, leads_max, max_cpl, action, new_budget, next_spend_limit, description) VALUES
        (new_rule_set_id, 1,  8,    NULL, 0,    NULL, 'campaign_stop',        NULL, NULL, 'STOP: spend >= $8, 0 leads'),
        (new_rule_set_id, 2,  16,   NULL, 1,    NULL, 'campaign_stop',        NULL, NULL, 'STOP: spend >= $16, <= 1 lead'),
        (new_rule_set_id, 3,  24,   NULL, 2,    NULL, 'campaign_stop',        NULL, NULL, 'STOP: spend >= $24, <= 2 leads'),
        (new_rule_set_id, 4,  32,   NULL, 3,    NULL, 'campaign_stop',        NULL, NULL, 'STOP: spend >= $32, <= 3 leads'),
        (new_rule_set_id, 5,  40,   NULL, 4,    NULL, 'campaign_stop',        NULL, NULL, 'STOP: spend >= $40, <= 4 leads'),
        (new_rule_set_id, 6,  48,   5,    NULL, 10,   'campaign_stop',        NULL, NULL, 'STOP: spend >= $48, 5+ leads, CPL > $10'),
        (new_rule_set_id, 7,  NULL, 7,    NULL, NULL, 'manual_review_needed', NULL, NULL, '7+ leads — manual review'),
        (new_rule_set_id, 10, NULL, 6,    NULL, NULL, 'budget_increase',      250,  NULL, '6+ leads → budget $250'),
        (new_rule_set_id, 11, NULL, 4,    NULL, NULL, 'budget_increase',      150,  NULL, '4+ leads → budget $150'),
        (new_rule_set_id, 12, NULL, 2,    NULL, NULL, 'budget_increase',      75,   NULL, '2+ leads → budget $75');
    INSERT INTO auto_launch_settings (user_id) VALUES (NEW.id);
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
