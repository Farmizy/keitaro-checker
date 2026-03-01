import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import * as schedulerApi from "@/api/scheduler"

export function useSchedulerStatus() {
  return useQuery({
    queryKey: ["scheduler-status"],
    queryFn: schedulerApi.getSchedulerStatus,
    refetchInterval: 10_000,
  })
}

export function useTriggerCheck() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: schedulerApi.triggerCheck,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scheduler-status"] })
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] })
    },
  })
}

export function usePauseScheduler() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: schedulerApi.pauseScheduler,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheduler-status"] }),
  })
}

export function useResumeScheduler() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: schedulerApi.resumeScheduler,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scheduler-status"] }),
  })
}
