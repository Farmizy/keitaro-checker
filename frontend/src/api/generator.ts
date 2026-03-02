import api from "./client"
import type {
  AccountProfile,
  AccountProfileCreate,
  KeitaroOffer,
  KeitaroDomain,
  CampaignFormEntry,
} from "@/types"

export async function getOffers(): Promise<KeitaroOffer[]> {
  const { data } = await api.get("/generator/offers")
  return data
}

export async function getDomains(): Promise<KeitaroDomain[]> {
  const { data } = await api.get("/generator/domains")
  return data
}

export async function getPages(
  accountId: string,
): Promise<{ id: string; name: string }[]> {
  const { data } = await api.get(`/generator/pages/${accountId}`)
  return data
}

export async function getProfiles(): Promise<AccountProfile[]> {
  const { data } = await api.get("/generator/account-profiles")
  return data
}

export async function createProfile(
  payload: AccountProfileCreate,
): Promise<AccountProfile> {
  const { data } = await api.post("/generator/account-profiles", payload)
  return data
}

export async function updateProfile(
  id: string,
  payload: Partial<AccountProfileCreate>,
): Promise<AccountProfile> {
  const { data } = await api.put(`/generator/account-profiles/${id}`, payload)
  return data
}

export async function generateCampaigns(
  campaigns: CampaignFormEntry[],
): Promise<Blob> {
  const { data } = await api.post(
    "/generator/generate",
    { campaigns },
    { responseType: "blob" },
  )
  return data
}
