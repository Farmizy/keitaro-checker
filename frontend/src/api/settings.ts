import api from "./client"

export interface UserSettings {
  keitaro_url: string
  keitaro_login: string
  keitaro_password: string
  fbtool_cookies: string
  fbtool_account_ids: number[]
  telegram_bot_token: string
  telegram_chat_id: string
  keitaro_configured: boolean
  fbtool_configured: boolean
  telegram_configured: boolean
}

export type UserSettingsUpdate = Partial<
  Omit<UserSettings, "keitaro_configured" | "fbtool_configured" | "telegram_configured">
>

export async function getSettings(): Promise<UserSettings> {
  const { data } = await api.get("/settings/")
  return data
}

export async function updateSettings(payload: UserSettingsUpdate): Promise<UserSettings> {
  const { data } = await api.put("/settings/", payload)
  return data
}

export async function testKeitaro(): Promise<{ status: string; message: string }> {
  const { data } = await api.post("/settings/test/keitaro")
  return data
}

export async function testFbtool(): Promise<{ status: string; message: string }> {
  const { data } = await api.post("/settings/test/fbtool")
  return data
}

export async function testTelegram(): Promise<{ status: string; message: string }> {
  const { data } = await api.post("/settings/test/telegram")
  return data
}
