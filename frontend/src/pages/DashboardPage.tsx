import { DollarSign, Users, Megaphone, TrendingUp, AlertTriangle, Pause, Info, AlertCircle, Settings } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDashboardStats } from "@/hooks/useDashboard"
import { formatCurrency, formatDate } from "@/lib/utils"
import { useNavigate } from "react-router-dom"
import type { DashboardAlert } from "@/types"

const alertStyles: Record<DashboardAlert["type"], { bg: string; border: string; icon: typeof AlertCircle }> = {
  error: { bg: "bg-rose-500/8", border: "border-rose-500/20", icon: AlertCircle },
  warning: { bg: "bg-amber-500/8", border: "border-amber-500/20", icon: AlertTriangle },
  info: { bg: "bg-blue-500/8", border: "border-blue-500/20", icon: Info },
}

const cardAccents = [
  { gradient: "from-violet-500/20 to-transparent", iconBg: "bg-violet-500/15", iconColor: "text-violet-400" },
  { gradient: "from-emerald-500/20 to-transparent", iconBg: "bg-emerald-500/15", iconColor: "text-emerald-400" },
  { gradient: "from-cyan-500/20 to-transparent", iconBg: "bg-cyan-500/15", iconColor: "text-cyan-400" },
  { gradient: "from-blue-500/20 to-transparent", iconBg: "bg-blue-500/15", iconColor: "text-blue-400" },
  { gradient: "from-amber-500/20 to-transparent", iconBg: "bg-amber-500/15", iconColor: "text-amber-400" },
  { gradient: "from-rose-500/20 to-transparent", iconBg: "bg-rose-500/15", iconColor: "text-rose-400" },
  { gradient: "from-indigo-500/20 to-transparent", iconBg: "bg-indigo-500/15", iconColor: "text-indigo-400" },
  { gradient: "from-teal-500/20 to-transparent", iconBg: "bg-teal-500/15", iconColor: "text-teal-400" },
]

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-40 skeleton" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border p-6 space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-4 w-20 skeleton" />
              <div className="h-8 w-8 rounded-lg skeleton" />
            </div>
            <div className="h-8 w-24 skeleton" />
          </div>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-border p-6 space-y-4">
            <div className="h-5 w-32 skeleton" />
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} className="h-10 w-full skeleton" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { data: stats, isLoading } = useDashboardStats()
  const navigate = useNavigate()

  if (isLoading || !stats) {
    return <DashboardSkeleton />
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
      <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>

      {stats.alerts?.length > 0 && (
        <div className="space-y-2 animate-fade-in">
          {stats.alerts.map((alert) => {
            const style = alertStyles[alert.type]
            const Icon = style.icon
            const isSettingsAlert = alert.key.includes("configured") || alert.key === "jwt_expired"
            return (
              <div
                key={alert.key}
                className={`flex items-center gap-3 rounded-lg border p-3 transition-colors ${style.bg} ${style.border} ${isSettingsAlert ? "cursor-pointer hover:opacity-80" : ""}`}
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 stagger-children">
        {cards.map(({ label, value, icon: Icon }, i) => {
          const accent = cardAccents[i]
          return (
            <Card key={label} className="relative overflow-hidden">
              <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${accent.gradient} opacity-50`} />
              <CardHeader className="relative flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${accent.iconBg}`}>
                  <Icon className={`h-4 w-4 ${accent.iconColor}`} />
                </div>
              </CardHeader>
              <CardContent className="relative">
                <div className="text-2xl font-bold tracking-tight">{value}</div>
              </CardContent>
            </Card>
          )
        })}
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
