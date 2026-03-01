import api from "./client"
import type { SchedulerStatus } from "@/types"

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  const { data } = await api.get("/scheduler/status")
  return data
}

export async function triggerCheck(): Promise<void> {
  await api.post("/scheduler/trigger")
}

export async function pauseScheduler(): Promise<void> {
  await api.post("/scheduler/pause")
}

export async function resumeScheduler(): Promise<void> {
  await api.post("/scheduler/resume")
}
