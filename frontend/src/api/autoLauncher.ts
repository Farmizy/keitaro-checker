import api from "./client"
import type {
  AutoLaunchSettings,
  LaunchQueueItem,
  BlacklistItem,
  AutoLauncherStatus,
} from "@/types"

// --- Settings ---

export async function getSettings(): Promise<AutoLaunchSettings> {
  const { data } = await api.get("/auto-launcher/settings")
  return data
}

export async function updateSettings(
  body: Partial<AutoLaunchSettings>,
): Promise<AutoLaunchSettings> {
  const { data } = await api.patch("/auto-launcher/settings", body)
  return data
}

// --- Queue ---

export async function getQueue(params?: {
  launch_date?: string
  status?: string
}): Promise<LaunchQueueItem[]> {
  const { data } = await api.get("/auto-launcher/queue", { params })
  return data
}

export async function removeFromQueue(itemId: string): Promise<void> {
  await api.delete(`/auto-launcher/queue/${itemId}`)
}

// --- Blacklist ---

export async function getBlacklist(): Promise<BlacklistItem[]> {
  const { data } = await api.get("/auto-launcher/blacklist")
  return data
}

export async function addToBlacklist(body: {
  campaign_id: string
  fb_campaign_id?: string
  fb_campaign_name?: string
}): Promise<BlacklistItem> {
  const { data } = await api.post("/auto-launcher/blacklist", body)
  return data
}

export async function removeFromBlacklist(campaignId: string): Promise<void> {
  await api.delete(`/auto-launcher/blacklist/${campaignId}`)
}

// --- Triggers ---

export async function triggerAnalysis(): Promise<void> {
  await api.post("/auto-launcher/trigger-analysis")
}

export async function triggerLaunch(): Promise<void> {
  await api.post("/auto-launcher/trigger-launch")
}

// --- Status ---

export async function getStatus(): Promise<AutoLauncherStatus> {
  const { data } = await api.get("/auto-launcher/status")
  return data
}
