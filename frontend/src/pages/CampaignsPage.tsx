import { useState } from "react"
import { useCampaigns, useUpdateCampaign } from "@/hooks/useCampaigns"
import { useAccounts } from "@/hooks/useAccounts"
import { useActionLogs } from "@/hooks/useLogs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { formatCurrency, formatDate } from "@/lib/utils"
import { Play, Square, Eye, EyeOff, History } from "lucide-react"

const statusVariant = {
  active: "success" as const,
  paused: "warning" as const,
  stopped: "destructive" as const,
}

function CampaignHistory({ campaignId }: { campaignId: string }) {
  const { data: logs, isLoading } = useActionLogs({ campaign_id: campaignId, limit: 20 })

  if (isLoading) return <p className="py-2 text-xs text-muted-foreground">Loading...</p>
  if (!logs?.length) return <p className="py-2 text-xs text-muted-foreground">No actions recorded</p>

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Action</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Details</TableHead>
          <TableHead>Time</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log) => (
          <TableRow key={log.id}>
            <TableCell className="font-mono text-xs">{log.action_type}</TableCell>
            <TableCell>
              <Badge variant={log.success ? "success" : "destructive"}>
                {log.success ? "OK" : "FAIL"}
              </Badge>
            </TableCell>
            <TableCell className="max-w-[300px] truncate text-xs text-muted-foreground">
              {log.error_message || formatDetails(log.details)}
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">{formatDate(log.created_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function formatDetails(details: Record<string, unknown>): string {
  if (!details || Object.keys(details).length === 0) return ""
  const parts: string[] = []
  if (details.reason) parts.push(String(details.reason))
  if (details.old_budget != null && details.new_budget != null) {
    parts.push(`$${details.old_budget} → $${details.new_budget}`)
  }
  if (details.target_budget != null) parts.push(`budget → $${details.target_budget}`)
  return parts.join(" | ") || JSON.stringify(details).slice(0, 100)
}

export default function CampaignsPage() {
  const [accountFilter, setAccountFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: accounts } = useAccounts()
  const { data: campaigns, isLoading } = useCampaigns({
    account_id: accountFilter || undefined,
    status: statusFilter || undefined,
  })
  const updateMut = useUpdateCampaign()

  function toggleManaged(id: string, current: boolean) {
    updateMut.mutate({ id, data: { is_managed: !current } })
  }

  function setCampaignStatus(id: string, status: string) {
    updateMut.mutate({ id, data: { status } })
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Campaigns</h1>

      <div className="flex flex-wrap gap-3">
        <Select value={accountFilter} onChange={(e) => setAccountFilter(e.target.value)} className="w-48">
          <option value="">All Accounts</option>
          {accounts?.map((acc) => (
            <option key={acc.id} value={acc.id}>{acc.name}</option>
          ))}
        </Select>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-36">
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="stopped">Stopped</option>
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Campaigns {campaigns ? `(${campaigns.length})` : ""}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : !campaigns?.length ? (
            <p className="text-muted-foreground">No campaigns found</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Budget</TableHead>
                  <TableHead>Spend</TableHead>
                  <TableHead>Leads</TableHead>
                  <TableHead>CPL</TableHead>
                  <TableHead>Managed</TableHead>
                  <TableHead>Last Sync</TableHead>
                  <TableHead className="w-28">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.map((c) => (
                  <>
                    <TableRow key={c.id}>
                      <TableCell>
                        <div className="max-w-[200px] truncate font-medium" title={c.fb_campaign_name}>
                          {c.fb_campaign_name}
                        </div>
                        <div className="text-xs text-muted-foreground">{c.fb_campaign_id}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusVariant[c.status]}>{c.status}</Badge>
                      </TableCell>
                      <TableCell>{formatCurrency(c.current_budget)}</TableCell>
                      <TableCell>{formatCurrency(c.total_spend)}</TableCell>
                      <TableCell>{c.leads_count}</TableCell>
                      <TableCell>{c.leads_count > 0 ? formatCurrency(c.total_spend / c.leads_count) : "—"}</TableCell>
                      <TableCell>
                        <button
                          onClick={() => toggleManaged(c.id, c.is_managed)}
                          className="cursor-pointer text-muted-foreground hover:text-foreground"
                          title={c.is_managed ? "Managed — click to exclude" : "Excluded — click to manage"}
                        >
                          {c.is_managed ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                        </button>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatDate(c.last_fb_sync)}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            title="History"
                            onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                          >
                            <History className={`h-3.5 w-3.5 ${expandedId === c.id ? "text-primary" : ""}`} />
                          </Button>
                          {c.status === "stopped" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Resume"
                              onClick={() => setCampaignStatus(c.id, "active")}
                            >
                              <Play className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          {c.status === "active" && (
                            <Button
                              variant="ghost"
                              size="icon"
                              title="Stop"
                              onClick={() => setCampaignStatus(c.id, "stopped")}
                            >
                              <Square className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                    {expandedId === c.id && (
                      <TableRow key={`${c.id}-history`}>
                        <TableCell colSpan={9} className="bg-muted/30 p-4">
                          <div className="text-sm font-medium mb-2">Action History</div>
                          <CampaignHistory campaignId={c.id} />
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
