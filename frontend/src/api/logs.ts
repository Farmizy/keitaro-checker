import api from "./client"
import type { ActionLog, CheckRun } from "@/types"

export async function getActionLogs(params?: {
  limit?: number
  offset?: number
  campaign_id?: string
}): Promise<ActionLog[]> {
  const { data } = await api.get("/logs/actions", { params })
  return data
}

export async function getCheckRuns(limit = 10): Promise<CheckRun[]> {
  const { data } = await api.get("/logs/check-runs", { params: { limit } })
  return data
}
