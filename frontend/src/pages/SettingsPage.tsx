import { useSchedulerStatus } from "@/hooks/useScheduler"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export default function SettingsPage() {
  const { data: scheduler } = useSchedulerStatus()

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Scheduler</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Status</span>
            {scheduler && (
              <Badge
                variant={scheduler.status === "running" ? "success" : scheduler.status === "paused" ? "warning" : "destructive"}
                className="capitalize"
              >
                {scheduler.status}
              </Badge>
            )}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Check Interval</span>
            <span className="text-sm">{scheduler?.interval_minutes ?? "—"} min</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Next Run</span>
            <span className="text-sm">
              {scheduler?.next_run
                ? new Date(scheduler.next_run).toLocaleString("ru-RU")
                : "—"}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Keitaro</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Keitaro is configured via backend environment variables (KEITARO_URL, KEITARO_LOGIN, KEITARO_PASSWORD).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Telegram Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Telegram notifications are configured via backend environment variables (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
