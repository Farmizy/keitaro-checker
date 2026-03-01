import api from "./client"
import type { DashboardStats } from "@/types"

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await api.get("/dashboard/stats")
  return data
}
