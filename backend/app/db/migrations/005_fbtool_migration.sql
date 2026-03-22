-- Migration: 2KK Panel → fbtool.pro
-- Rename panel_ columns to fbtool_, add new fbtool fields

-- 1. fb_accounts: panel_account_id → fbtool_account_id
ALTER TABLE fb_accounts RENAME COLUMN panel_account_id TO fbtool_account_id;

-- 2. campaigns: drop panel_campaign_id (fbtool uses fb_campaign_id directly)
ALTER TABLE campaigns DROP COLUMN IF EXISTS panel_campaign_id;

-- 3. auto_launch_queue: drop panel_campaign_id, add fbtool_account_id
ALTER TABLE auto_launch_queue DROP COLUMN IF EXISTS panel_campaign_id;
ALTER TABLE auto_launch_queue ADD COLUMN IF NOT EXISTS fbtool_account_id INT;

-- 4. user_settings: replace panel fields with fbtool fields
ALTER TABLE user_settings DROP COLUMN IF EXISTS panel_api_url;
ALTER TABLE user_settings DROP COLUMN IF EXISTS panel_jwt;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS fbtool_cookies TEXT DEFAULT '';
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS fbtool_account_ids JSONB DEFAULT '[]'::jsonb;
