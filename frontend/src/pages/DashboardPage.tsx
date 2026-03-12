import { DollarSign, Users, Megaphone, TrendingUp, AlertTriangle, Pause, Info, AlertCircle, Settings } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDashboardStats } from "@/hooks/useDashboard"
import { formatCurrency, formatDate } from "@/lib/utils"
import { useNavigate } from "react-router-dom"
import type { DashboardAlert } from "@/types"

const alertStyles: Record<DashboardAlert["type"], { bg: string; border: string; icon: typeof AlertCircle }> = {
  error: { bg: "bg-red-50 dark:bg-red-950/30", border: "border-red-200 dark:border-red-800", icon: AlertCircle },
  warning: { bg: "bg-yellow-50 dark:bg-yellow-950/30", border: "border-yellow-200 dark:border-yellow-800", icon: AlertTriangle },
  info: { bg: "bg-blue-50 dark:bg-blue-950/30", border: "border-blue-200 dark:border-blue-800", icon: Info },
}

export default function DashboardPage() {
  const { data: stats, isLoading } = useDashboardStats()
  const navigate = useNavigate()

  if (isLoading || !stats) {
    return <div className="text-muted-foreground">Loading...</div>
  }

  const cards = [
    { label: "Total Spend", value: formatCurrency(stats.total_spend), icon: DollarSign },
    { label: "Total Leads", value: stats.total_leads.toString(), icon: TrendingUp },
    { label: "Avg CPL", value: formatCurrency(stats.avg_cpl), icon: DollarSign },
    { label: "Active", value: stats.campaigns_active.toString(), icon: Megaphone },
    { label: "Paused", value: stats.campaigns_paused.toString(), icon: Pause },
    { label: "Stopped", value: stats.campaigns_stopped.toString(), icon: AlertTriangle },
    { label: "Campaigns", value: stats.campaigns_total.toString(), icon: Megaphone },
    { label: "Accounts", value: `${stats.accounts_active}/${stats.accounts_total}`, icon: Users },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {stats.alerts?.length > 0 && (
        <div className="space-y-2">
          {stats.alerts.map((alert) => {
            const style = alertStyles[alert.type]
            const Icon = style.icon
            const isSettingsAlert = alert.key.includes("configured") || alert.key === "jwt_expired"
            return (
              <div
                key={alert.key}
                className={`flex items-center gap-3 rounded-lg border p-3 ${style.bg} ${style.border} ${isSettingsAlert ? "cursor-pointer hover:opacity-80" : ""}`}
                onClick={isSettingsAlert ? () => navigate("/settings") : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="text-sm">{alert.message}</span>
                {isSettingsAlert && <Settings className="ml-auto h-3.5 w-3.5 shrink-0 opacity-50" />}
              </div>
            )
          })}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Actions</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.recent_actions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No actions yet</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stats.recent_actions.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="font-mono text-xs">{log.action_type}</TableCell>
                      <TableCell>
                        <Badge variant={log.success ? "success" : "destructive"}>
                          {log.success ? "OK" : "FAIL"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDate(log.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Check Runs</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.recent_runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No check runs yet</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Checked</TableHead>
                    <TableHead>Actions</TableHead>
                    <TableHead>Errors</TableHead>
                    <TableHead>Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stats.recent_runs.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell>
                        <Badge
                          variant={
                            run.status === "completed" ? "success" : run.status === "failed" ? "destructive" : "secondary"
                          }
                        >
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{run.campaigns_checked}</TableCell>
                      <TableCell>{run.actions_taken}</TableCell>
                      <TableCell>{run.errors_count}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDate(run.started_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
