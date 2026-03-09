import { useState } from "react"
import {
  useAutoLauncherStatus,
  useAutoLaunchSettings,
  useUpdateSettings,
  useLaunchQueue,
  useRemoveFromQueue,
  useBlacklist,
  useRemoveFromBlacklist,
  useTriggerAnalysis,
  useTriggerLaunch,
} from "@/hooks/useAutoLauncher"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { formatCurrency, formatDate } from "@/lib/utils"
import { Rocket, Play, Trash2, Unlock, Loader2 } from "lucide-react"

export default function AutoLauncherPage() {
  const { data: status } = useAutoLauncherStatus()
  const { data: settings } = useAutoLaunchSettings()
  const updateSettings = useUpdateSettings()
  const today = new Date().toISOString().slice(0, 10)
  const { data: queue } = useLaunchQueue({ launch_date: today })
  const removeFromQueue = useRemoveFromQueue()
  const { data: blacklist } = useBlacklist()
  const removeFromBlacklist = useRemoveFromBlacklist()
  const triggerAnalysis = useTriggerAnalysis()
  const triggerLaunch = useTriggerLaunch()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Rocket className="h-6 w-6" /> Auto-Launcher
        </h1>
        <Badge variant={status?.is_enabled ? "success" : "secondary"} className="text-sm">
          {status?.is_enabled ? "Enabled" : "Disabled"}
        </Badge>
      </div>

      {/* Status + Controls */}
      <StatusCard
        status={status}
        onToggle={() => updateSettings.mutate({ is_enabled: !status?.is_enabled })}
        onTriggerAnalysis={() => triggerAnalysis.mutate()}
        onTriggerLaunch={() => triggerLaunch.mutate()}
        isToggling={updateSettings.isPending}
        isAnalyzing={triggerAnalysis.isPending}
        isLaunching={triggerLaunch.isPending}
      />

      {/* Queue */}
      <QueueCard queue={queue} onRemove={(id) => removeFromQueue.mutate(id)} />

      {/* Blacklist */}
      <BlacklistCard blacklist={blacklist} onRemove={(id) => removeFromBlacklist.mutate(id)} />

      {/* Settings */}
      <SettingsCard settings={settings} onSave={(data) => updateSettings.mutate(data)} isSaving={updateSettings.isPending} />
    </div>
  )
}

function StatusCard({
  status,
  onToggle,
  onTriggerAnalysis,
  onTriggerLaunch,
  isToggling,
  isAnalyzing,
  isLaunching,
}: {
  status: ReturnType<typeof useAutoLauncherStatus>["data"]
  onToggle: () => void
  onTriggerAnalysis: () => void
  onTriggerLaunch: () => void
  isToggling: boolean
  isAnalyzing: boolean
  isLaunching: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs text-muted-foreground">Analysis</p>
            <p className="text-sm">
              {status?.schedule?.analysis_next_run
                ? formatDate(status.schedule.analysis_next_run)
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Launch</p>
            <p className="text-sm">
              {status?.schedule?.launch_next_run
                ? formatDate(status.schedule.launch_next_run)
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Today pending</p>
            <p className="text-sm font-medium">{status?.today_queue?.pending ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Today launched</p>
            <p className="text-sm font-medium">{status?.today_queue?.launched ?? 0}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant={status?.is_enabled ? "destructive" : "default"}
            size="sm"
            onClick={onToggle}
            disabled={isToggling}
          >
            {isToggling && <Loader2 className="h-4 w-4 animate-spin" />}
            {status?.is_enabled ? "Disable" : "Enable"}
          </Button>
          <Button variant="outline" size="sm" onClick={onTriggerAnalysis} disabled={isAnalyzing}>
            {isAnalyzing && <Loader2 className="h-4 w-4 animate-spin" />}
            <Play className="h-4 w-4" /> Run Analysis
          </Button>
          <Button variant="outline" size="sm" onClick={onTriggerLaunch} disabled={isLaunching}>
            {isLaunching && <Loader2 className="h-4 w-4 animate-spin" />}
            <Rocket className="h-4 w-4" /> Run Launch
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function QueueCard({
  queue,
  onRemove,
}: {
  queue: ReturnType<typeof useLaunchQueue>["data"]
  onRemove: (id: string) => void
}) {
  const statusVariant = (s: string) => {
    switch (s) {
      case "launched": return "success"
      case "pending": return "secondary"
      case "skipped": return "warning"
      case "failed": return "destructive"
      case "removed": return "outline"
      default: return "secondary"
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Today's Queue</CardTitle>
      </CardHeader>
      <CardContent>
        {!queue?.length ? (
          <p className="text-muted-foreground text-sm">No campaigns in queue</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Budget</TableHead>
                <TableHead>ROI 2d</TableHead>
                <TableHead>Leads 2d</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-[200px] truncate text-xs font-medium">
                    {item.fb_campaign_name}
                  </TableCell>
                  <TableCell>
                    <Badge variant={item.launch_type === "proven" ? "success" : "secondary"}>
                      {item.launch_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">{formatCurrency(item.target_budget)}</TableCell>
                  <TableCell className="text-xs">
                    {item.analysis_data?.roi_2d != null ? `${item.analysis_data.roi_2d.toFixed(0)}%` : "—"}
                  </TableCell>
                  <TableCell className="text-xs">{item.analysis_data?.leads_2d ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(item.status)} className="capitalize">
                      {item.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {item.status === "pending" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onRemove(item.id)}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function BlacklistCard({
  blacklist,
  onRemove,
}: {
  blacklist: ReturnType<typeof useBlacklist>["data"]
  onRemove: (campaignId: string) => void
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Blacklist</CardTitle>
      </CardHeader>
      <CardContent>
        {!blacklist?.length ? (
          <p className="text-muted-foreground text-sm">Blacklist is empty</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Added by</TableHead>
                <TableHead>Date</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {blacklist.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-[200px] truncate text-xs font-medium">
                    {item.fb_campaign_name || item.fb_campaign_id}
                  </TableCell>
                  <TableCell className="text-xs">{item.reason}</TableCell>
                  <TableCell>
                    <Badge variant={item.blacklisted_by === "system" ? "secondary" : "outline"}>
                      {item.blacklisted_by}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDate(item.blacklisted_at)}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRemove(item.campaign_id)}
                    >
                      <Unlock className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}

function SettingsCard({
  settings,
  onSave,
  isSaving,
}: {
  settings: ReturnType<typeof useAutoLaunchSettings>["data"]
  onSave: (data: Record<string, unknown>) => void
  isSaving: boolean
}) {
  const [form, setForm] = useState<Record<string, string>>({})

  const fields = [
    { key: "analysis_hour", label: "Analysis hour", type: "number" },
    { key: "analysis_minute", label: "Analysis minute", type: "number" },
    { key: "launch_hour", label: "Launch hour", type: "number" },
    { key: "launch_minute", label: "Launch minute", type: "number" },
    { key: "min_roi_threshold", label: "Min ROI %", type: "number" },
    { key: "starting_budget", label: "Starting budget $", type: "number" },
  ]

  const handleSave = () => {
    const data: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(form)) {
      if (v !== "") data[k] = Number(v)
    }
    if (Object.keys(data).length > 0) {
      onSave(data)
      setForm({})
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Settings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {fields.map(({ key, label, type }) => (
            <div key={key}>
              <label className="text-xs text-muted-foreground">{label}</label>
              <Input
                type={type}
                placeholder={String((settings as unknown as Record<string, unknown>)?.[key] ?? "")}
                value={form[key] ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                className="mt-1"
              />
            </div>
          ))}
        </div>
        <Button size="sm" onClick={handleSave} disabled={isSaving || Object.keys(form).length === 0}>
          {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Settings
        </Button>
      </CardContent>
    </Card>
  )
}
