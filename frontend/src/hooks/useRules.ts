import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as rulesApi from "@/api/rules"
import type { RuleStep } from "@/types"

export function useDefaultRuleSet() {
  return useQuery({
    queryKey: ["rules", "default"],
    queryFn: rulesApi.getDefaultRuleSet,
  })
}

export function useUpdateRuleStep() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<RuleStep> }) =>
      rulesApi.updateRuleStep(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules"] }),
  })
}
