import { useState } from "react"
import { useActionLogs, useCheckRuns } from "@/hooks/useLogs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatCurrency, formatDate } from "@/lib/utils"
import { ChevronLeft, ChevronRight } from "lucide-react"

const PAGE_SIZE = 30

export default function LogsPage() {
  const [offset, setOffset] = useState(0)
  const { data: logs, isLoading: logsLoading } = useActionLogs({ limit: PAGE_SIZE, offset })
  const { data: runs } = useCheckRuns(10)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Logs</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Action Logs</CardTitle>
        </CardHeader>
        <CardContent>
          {logsLoading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : !logs?.length ? (
            <p className="text-muted-foreground">No action logs yet</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Budget</TableHead>
                    <TableHead>Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {formatDate(log.created_at)}
                      </TableCell>
                      <TableCell className="font-mono text-xs">{log.action_type}</TableCell>
                      <TableCell>
                        <Badge variant={log.success ? "success" : "destructive"}>
                          {log.success ? "OK" : "FAIL"}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-xs">
                        {(log.details as Record<string, unknown>)?.reason as string || "—"}
                      </TableCell>
                      <TableCell className="text-xs">
                        {(log.details as Record<string, unknown>)?.target_budget != null
                          ? formatCurrency((log.details as Record<string, unknown>).target_budget as number)
                          : "—"}
                      </TableCell>
                      <TableCell className="max-w-[150px] truncate text-xs text-red-400">
                        {log.error_message || ""}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4 flex items-center justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                >
                  <ChevronLeft className="h-4 w-4" /> Prev
                </Button>
                <span className="text-xs text-muted-foreground">
                  Showing {offset + 1}–{offset + (logs?.length || 0)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  disabled={(logs?.length || 0) < PAGE_SIZE}
                >
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Check Runs</CardTitle>
        </CardHeader>
        <CardContent>
          {!runs?.length ? (
            <p className="text-muted-foreground">No check runs yet</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Checked</TableHead>
                  <TableHead>Actions</TableHead>
                  <TableHead>Errors</TableHead>
                  <TableHead>Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const duration =
                    run.completed_at && run.started_at
                      ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)
                      : null
                  return (
                    <TableRow key={run.id}>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {formatDate(run.started_at)}
                      </TableCell>
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
                        {duration != null ? `${duration}s` : "—"}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
