import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as campaignsApi from "@/api/campaigns"

export function useCampaigns(params?: { account_id?: string; status?: string }) {
  return useQuery({
    queryKey: ["campaigns", params],
    queryFn: () => campaignsApi.getCampaigns(params),
    refetchInterval: 30_000,
  })
}

export function useUpdateCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string
      data: { is_managed?: boolean; status?: string; notes?: string }
    }) => campaignsApi.updateCampaign(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  })
}
