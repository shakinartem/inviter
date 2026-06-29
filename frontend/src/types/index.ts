// ==================== Account types ====================
export type AccountStatus =
  | "active" | "idle" | "limited" | "cooldown" | "banned" | "inactive" | "error";

export interface ProxyShort {
  id: string;
  title: string;
  scheme: string;
  host: string;
  port: number;
  is_active: boolean;
}

export interface AccountListItem {
  id: string;
  label: string;
  phone: string | null;
  username: string | null;
  status: AccountStatus;
  is_active: boolean;
  is_premium: boolean;
  proxy_id: string | null;
  last_used_at: string | null;
  last_checked_at: string | null;
  daily_invite_count: number;
  total_invites: number;
  success_rate: number;
  created_at: string;
}

export interface AccountResponse {
  id: string;
  owner_id: string;
  label: string;
  phone: string | null;
  session_name: string;
  api_id: number | null;
  api_hash: string | null;
  proxy_id: string | null;
  proxy: ProxyShort | null;
  telegram_user_id: number | null;
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  is_premium: boolean;
  is_bot: boolean;
  status: AccountStatus;
  status_message: string | null;
  is_active: boolean;
  last_seen_at: string | null;
  last_used_at: string | null;
  last_checked_at: string | null;
  cooldown_until: string | null;
  banned_until: string | null;
  daily_invite_count: number;
  daily_invite_reset_at: string | null;
  total_invites: number;
  total_invite_errors: number;
  total_floodwaits: number;
  success_rate: number;
  metadata: Record<string, any> | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  fingerprint: string | null;
}

export interface AccountCreatePayload {
  label: string;
  phone?: string | null;
  api_id?: number | null;
  api_hash?: string | null;
  proxy_id?: string | null;
  session_name?: string | null;
  notes?: string | null;
  metadata?: Record<string, any> | null;
}

export interface AccountStats {
  total: number;
  active: number;
  banned: number;
  limited: number;
  cooldown: number;
  inactive: number;
  in_cooldown_now: number;
  premium_count: number;
  total_invites_today: number;
  avg_success_rate: number;
}

export interface AccountListFilter {
  status?: AccountStatus;
  is_active?: boolean;
  proxy_id?: string;
  is_premium?: boolean;
  search?: string;
  created_after?: string;
  created_before?: string;
}

// ==================== Proxy types ====================
export type ProxyScheme = "http" | "socks5" | "mtproto";

export interface ProxyListItem {
  id: string;
  title: string;
  scheme: string;
  host: string;
  port: number;
  country: string | null;
  is_active: boolean;
  is_working: boolean | null;
  ping_ms: number | null;
  last_checked_at: string | null;
  in_use_count: number;
  created_at: string;
}

export interface ProxyResponse {
  id: string;
  owner_id: string;
  title: string;
  scheme: string;
  host: string;
  port: number;
  username: string | null;
  password: string | null;
  secret: string | null;
  country: string | null;
  city: string | null;
  ping_ms: number | null;
  last_checked_at: string | null;
  is_active: boolean;
  is_working: boolean | null;
  status_message: string | null;
  extra_data: Record<string, any> | null;
  notes: string | null;
  in_use_count: number;
  active_accounts_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProxyCreatePayload {
  title: string;
  scheme?: ProxyScheme;
  host: string;
  port: number;
  username?: string | null;
  password?: string | null;
  secret?: string | null;
  country?: string | null;
  city?: string | null;
  notes?: string | null;
  extra_data?: Record<string, any> | null;
}

export interface ProxyTestResult {
  proxy_id?: string | null;
  host: string;
  port: number;
  scheme: string;
  is_working: boolean;
  ping_ms: number | null;
  error_message: string | null;
  tested_at: string;
}

export interface ProxyStats {
  total: number;
  active: number;
  working: number;
  failing: number;
  unchecked: number;
  http_count: number;
  socks5_count: number;
  mtproto_count: number;
  avg_ping_ms: number | null;
  in_use_total: number;
}

export interface ProxyListFilter {
  scheme?: ProxyScheme;
  is_active?: boolean;
  is_working?: boolean;
  country?: string;
  search?: string;
  created_after?: string;
  created_before?: string;
}

// ==================== Parser types ====================
export type ParserSource = "tgstat" | "telegram" | "telemetr";

export interface ParsedChatListItem {
  id: string;
  chat_id: number;
  title: string | null;
  username: string | null;
  chat_type: string | null;
  participants_count: number | null;
  category: string | null;
  niche: string | null;
  language: string | null;
  source: string;
  is_active: boolean;
  is_public: boolean;
  last_parsed_at: string | null;
  created_at: string;
}

export interface ParsedChatResponse {
  id: string;
  owner_id: string;
  chat_id: number;
  username: string | null;
  title: string | null;
  description: string | null;
  access_hash: string | null;
  chat_type: string | null;
  participants_count: number | null;
  active_participants: number | null;
  category: string | null;
  niche: string | null;
  tags: string[] | null;
  language: string | null;
  country: string | null;
  is_public: boolean;
  is_active: boolean;
  is_restricted: boolean;
  source: string;
  last_parsed_at: string | null;
  parse_count: number;
  avg_posts_per_day: number | null;
  avg_reach_per_post: number | null;
  engagement_rate: number | null;
  extra_data: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface ParserSearchPayload {
  query: string;
  source?: ParserSource;
  min_participants?: number;
  max_participants?: number;
  language?: string | null;
  country?: string | null;
  chat_type?: string | null;
  is_public?: boolean;
  limit?: number;
  offset?: number;
}

export interface ParserStats {
  total_chats: number;
  active_chats: number;
  total_users: number;
  by_source: Record<string, number>;
  by_category: Record<string, number>;
  by_language: Record<string, number>;
  total_parses: number;
  avg_participants: number | null;
}

export interface ParsedUserResponse {
  id: string;
  owner_id: string;
  chat_id: string;
  user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  status: string | null;
  is_bot: boolean;
  is_verified: boolean;
  is_scam: boolean;
  is_fake: boolean;
  last_seen: string | null;
  was_online_at: string | null;
  msg_count: number | null;
  created_at: string;
  updated_at: string;
}

// ==================== Campaign types ====================
export type CampaignStatus = "draft" | "active" | "paused" | "completed" | "failed";
export type TaskStatus = "pending" | "processing" | "success" | "failed" | "floodwait" | "paused";

export interface InviteCampaignListItem {
  id: string;
  title: string;
  status: CampaignStatus;
  target_chat_title: string | null;
  target_chat_username: string | null;
  tasks_count: number;
  completed_tasks_count: number;
  success_rate: number;
  created_at: string;
  updated_at: string;
}

export interface InviteCampaignResponse {
  id: string;
  owner_id: string;
  title: string;
  status: CampaignStatus;
  source_chat_id: number | null;
  source_chat_title: string | null;
  source_type: "chat" | "parsed_list" | "uploaded_list";
  source_parsed_chat_id: string | null;
  target_chat_id: number;
  target_chat_title: string | null;
  target_chat_username: string | null;
  daily_limit_per_account: number;
  invite_delay_min: number;
  invite_delay_max: number;
  pause_after_every: number;
  pause_duration_min: number;
  pause_duration_max: number;
  warmup_enabled: boolean;
  warmup_days: number;
  warmup_limit_factor: number;
  only_add_contacts: boolean;
  add_to_contacts_first: boolean;
  blacklist_usernames: string[];
  blacklist_user_ids: number[];
  notes: string | null;
  created_at: string;
  updated_at: string;
  tasks_count: number | null;
  completed_tasks_count: number | null;
  failed_tasks_count: number | null;
  floodwait_tasks_count: number | null;
  success_rate: number | null;
}

export interface CampaignCreatePayload {
  title: string;
  target_chat_id: number;
  target_chat_title?: string | null;
  target_chat_username?: string | null;
  source_chat_id?: number | null;
  source_chat_title?: string | null;
  source_type?: "chat" | "parsed_list" | "uploaded_list";
  source_parsed_chat_id?: string | null;
  notes?: string | null;
  settings?: InviteSettingsPayload;
}

export interface InviteSettingsPayload {
  daily_limit_per_account?: number;
  invite_delay_min?: number;
  invite_delay_max?: number;
  pause_after_every?: number;
  pause_duration_min?: number;
  pause_duration_max?: number;
  warmup_enabled?: boolean;
  warmup_days?: number;
  warmup_limit_factor?: number;
  only_add_contacts?: boolean;
  add_to_contacts_first?: boolean;
  blacklist_usernames?: string[];
  blacklist_user_ids?: number[];
}

export interface InviteTaskResponse {
  id: string;
  campaign_id: string;
  account_id: string;
  proxy_id: string | null;
  target_user_id: number;
  target_username: string | null;
  status: TaskStatus;
  attempts: number;
  max_attempts: number;
  next_attempt_at: string | null;
  error_code: string | null;
  error_message: string | null;
  invited_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignStats {
  campaign_id: string;
  title: string;
  status: CampaignStatus;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  floodwait_tasks: number;
  success_rate: number;
  started_at: string | null;
  finished_at: string | null;
  invites_today: number;
  active_accounts: number;
}

export interface InviteLogResponse {
  id: string;
  invite_task_id: string;
  action: string;
  success: boolean;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
}

// ==================== Common ====================
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export interface DashboardStats {
  accounts: AccountStats;
  proxies: ProxyStats;
  parser: ParserStats;
  campaigns: {
    total: number;
    active: number;
    completed: number;
    failed: number;
  };
}
