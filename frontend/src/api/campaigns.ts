import api from "./client"
import type { Campaign } from "@/types"

export async function getCampaigns(params?: {
  account_id?: string
  status?: string
}): Promise<Campaign[]> {
  const { data } = await api.get("/campaigns/", { params })
  return data
}

export async function getCampaign(id: string): Promise<Campaign> {
  const { data } = await api.get(`/campaigns/${id}`)
  return data
}

export async function updateCampaign(
  id: string,
  payload: { is_managed?: boolean; status?: string; notes?: string },
): Promise<Campaign> {
  const { data } = await api.patch(`/campaigns/${id}`, payload)
  return data
}
