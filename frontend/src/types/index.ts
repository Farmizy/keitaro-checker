export interface Account {
  id: string
  name: string
  account_id: string
  panel_account_id: number | null
  useragent: string
  proxy_type: "socks5" | "http" | "https"
  proxy_host: string
  proxy_port: number
  proxy_login: string
  hide_comments: boolean
  is_active: boolean
  last_check_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface AccountCreate {
  name: string
  account_id: string
  panel_account_id?: number | null
  access_token: string
  cookie: string
  useragent: string
  proxy_type: "socks5" | "http" | "https"
  proxy_host: string
  proxy_port: number
  proxy_login: string
  proxy_password: string
}

export interface AccountUpdate {
  name?: string
  account_id?: string
  panel_account_id?: number | null
  access_token?: string
  cookie?: string
  useragent?: string
  proxy_type?: "socks5" | "http" | "https"
  proxy_host?: string
  proxy_port?: number
  proxy_login?: string
  proxy_password?: string
  is_active?: boolean
}

export interface Campaign {
  id: string
  fb_account_id: string
  fb_campaign_id: string
  panel_campaign_id: number | null
  fb_campaign_name: string
  fb_adset_id: string | null
  budget_level: "campaign" | "adset"
  status: "active" | "paused" | "stopped"
  current_budget: number
  total_spend: number
  leads_count: number
  cpl: number
  is_managed: boolean
  last_budget_change_at: string | null
  last_keitaro_sync: string | null
  last_fb_sync: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface RuleStep {
  id: string
  rule_set_id: string
  step_order: number
  spend_threshold: number | null
  leads_min: number | null
  leads_max: number | null
  max_cpl: number | null
  action: string
  new_budget: number | null
  next_spend_limit: number | null
  description: string | null
}

export interface RuleSet {
  id: string
  name: string
  description: string | null
  is_default: boolean
  rule_steps: RuleStep[]
}

export interface ActionLog {
  id: string
  campaign_id: string
  fb_account_id: string
  action_type: string
  rule_step_id: string | null
  details: Record<string, unknown>
  success: boolean
  error_message: string | null
  created_at: string
}

export interface CheckRun {
  id: string
  status: string
  started_at: string
  completed_at: string | null
  campaigns_checked: number
  actions_taken: number
  errors_count: number
  details: Record<string, unknown>
}

export interface DashboardStats {
  total_spend: number
  total_leads: number
  avg_cpl: number
  campaigns_active: number
  campaigns_paused: number
  campaigns_stopped: number
  campaigns_total: number
  accounts_total: number
  accounts_active: number
  recent_actions: ActionLog[]
  recent_runs: CheckRun[]
}

export interface SchedulerStatus {
  status: "running" | "paused" | "stopped"
  interval_minutes: number
  next_run: string | null
}
