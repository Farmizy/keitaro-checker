import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as autoLauncherApi from "@/api/autoLauncher"

const KEYS = {
  status: ["auto-launcher-status"],
  settings: ["auto-launcher-settings"],
  queue: ["auto-launcher-queue"],
  blacklist: ["auto-launcher-blacklist"],
}

export function useAutoLauncherStatus() {
  return useQuery({
    queryKey: KEYS.status,
    queryFn: autoLauncherApi.getStatus,
    refetchInterval: 15_000,
  })
}

export function useAutoLaunchSettings() {
  return useQuery({
    queryKey: KEYS.settings,
    queryFn: autoLauncherApi.getSettings,
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: autoLauncherApi.updateSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.settings })
      qc.invalidateQueries({ queryKey: KEYS.status })
    },
  })
}

export function useLaunchQueue(params?: { launch_date?: string; status?: string }) {
  return useQuery({
    queryKey: [...KEYS.queue, params],
    queryFn: () => autoLauncherApi.getQueue(params),
    refetchInterval: 15_000,
  })
}

export function useRemoveFromQueue() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: autoLauncherApi.removeFromQueue,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.queue })
      qc.invalidateQueries({ queryKey: KEYS.status })
    },
  })
}

export function useBlacklist() {
  return useQuery({
    queryKey: KEYS.blacklist,
    queryFn: autoLauncherApi.getBlacklist,
  })
}

export function useAddToBlacklist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: autoLauncherApi.addToBlacklist,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.blacklist }),
  })
}

export function useRemoveFromBlacklist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: autoLauncherApi.removeFromBlacklist,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.blacklist }),
  })
}

export function useTriggerAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: autoLauncherApi.triggerAnalysis,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.status })
      qc.invalidateQueries({ queryKey: KEYS.queue })
    },
  })
}

export function useTriggerLaunch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: autoLauncherApi.triggerLaunch,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.status })
      qc.invalidateQueries({ queryKey: KEYS.queue })
    },
  })
}
