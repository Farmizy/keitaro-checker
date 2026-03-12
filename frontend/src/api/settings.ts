import api from "./client"

export interface UserSettings {
  keitaro_url: string
  keitaro_login: string
  keitaro_password: string
  panel_api_url: string
  panel_jwt: string
  telegram_bot_token: string
  telegram_chat_id: string
  keitaro_configured: boolean
  panel_configured: boolean
  telegram_configured: boolean
}

export type UserSettingsUpdate = Partial<
  Omit<UserSettings, "keitaro_configured" | "panel_configured" | "telegram_configured">
>

export async function getSettings(): Promise<UserSettings> {
  const { data } = await api.get("/settings/")
  return data
}

export async function updateSettings(payload: UserSettingsUpdate): Promise<UserSettings> {
  const { data } = await api.put("/settings/", payload)
  return data
}
