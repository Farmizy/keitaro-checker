import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as accountsApi from "@/api/accounts"
import type { AccountCreate, AccountUpdate } from "@/types"

export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: accountsApi.getAccounts,
    refetchInterval: 30_000,
  })
}

export function useCreateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AccountCreate) => accountsApi.createAccount(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  })
}

export function useUpdateAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AccountUpdate }) =>
      accountsApi.updateAccount(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  })
}

export function useDeleteAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => accountsApi.deleteAccount(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  })
}
