import { Play, Pause, RefreshCw } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  useSchedulerStatus,
  useTriggerCheck,
  usePauseScheduler,
  useResumeScheduler,
} from "@/hooks/useScheduler"

export function SchedulerBar() {
  const { data: scheduler } = useSchedulerStatus()
  const trigger = useTriggerCheck()
  const pause = usePauseScheduler()
  const resume = useResumeScheduler()

  if (!scheduler) return null

  const statusVariant =
    scheduler.status === "running" ? "success" : scheduler.status === "paused" ? "warning" : "destructive"

  return (
    <div className="ml-auto flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div
          className={`h-2 w-2 rounded-full ${
            scheduler.status === "running"
              ? "bg-emerald-400 animate-pulse"
              : scheduler.status === "paused"
                ? "bg-amber-400"
                : "bg-rose-400"
          }`}
        />
        <Badge variant={statusVariant} className="capitalize">
          {scheduler.status}
        </Badge>
      </div>

      {scheduler.next_run && (
        <span className="hidden text-xs text-muted-foreground sm:inline">
          Next: {new Date(scheduler.next_run).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}
        </span>
      )}

      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => trigger.mutate()}
          disabled={trigger.isPending}
          title="Run check now"
        >
          <RefreshCw className={`h-4 w-4 ${trigger.isPending ? "animate-spin" : ""}`} />
        </Button>

        {scheduler.status === "running" ? (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => pause.mutate()}
            disabled={pause.isPending}
            title="Pause scheduler"
          >
            <Pause className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => resume.mutate()}
            disabled={resume.isPending}
            title="Resume scheduler"
          >
            <Play className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
