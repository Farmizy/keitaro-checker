import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as generatorApi from "@/api/generator"
import type { AccountProfileCreate, CampaignFormEntry } from "@/types"

export function useOffers() {
  return useQuery({
    queryKey: ["generator-offers"],
    queryFn: generatorApi.getOffers,
    staleTime: 60_000,
  })
}

export function useDomains() {
  return useQuery({
    queryKey: ["generator-domains"],
    queryFn: generatorApi.getDomains,
    staleTime: 60_000,
  })
}

export function usePages(accountId: string | null) {
  return useQuery({
    queryKey: ["generator-pages", accountId],
    queryFn: () => generatorApi.getPages(accountId!),
    enabled: !!accountId,
    staleTime: 60_000,
  })
}

export function useProfiles() {
  return useQuery({
    queryKey: ["generator-profiles"],
    queryFn: generatorApi.getProfiles,
  })
}

export function useCreateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AccountProfileCreate) =>
      generatorApi.createProfile(data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["generator-profiles"] }),
  })
}

export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: Partial<AccountProfileCreate>
    }) => generatorApi.updateProfile(id, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["generator-profiles"] }),
  })
}

export function useGenerate() {
  return useMutation({
    mutationFn: (campaigns: CampaignFormEntry[]) =>
      generatorApi.generateCampaigns(campaigns),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      const today = new Date().toISOString().slice(0, 10)
      a.download = `campaigns_${today}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    },
  })
}
