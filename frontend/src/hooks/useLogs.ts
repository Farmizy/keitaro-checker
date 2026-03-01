import { useQuery } from "@tanstack/react-query"
import * as logsApi from "@/api/logs"

export function useActionLogs(params?: {
  limit?: number
  offset?: number
  campaign_id?: string
}) {
  return useQuery({
    queryKey: ["action-logs", params],
    queryFn: () => logsApi.getActionLogs(params),
    refetchInterval: 30_000,
  })
}

export function useCheckRuns(limit = 10) {
  return useQuery({
    queryKey: ["check-runs", limit],
    queryFn: () => logsApi.getCheckRuns(limit),
    refetchInterval: 30_000,
  })
}
