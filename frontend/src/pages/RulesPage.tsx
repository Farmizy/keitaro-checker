import { useDefaultRuleSet } from "@/hooks/useRules"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatCurrency } from "@/lib/utils"
import type { RuleStep } from "@/types"

const actionLabel: Record<string, string> = {
  campaign_stop: "STOP",
  budget_increase: "Budget Increase",
  manual_review_needed: "Manual Review",
}

const actionVariant: Record<string, "destructive" | "success" | "warning" | "secondary"> = {
  campaign_stop: "destructive",
  budget_increase: "success",
  manual_review_needed: "warning",
}

function formatCondition(step: RuleStep): string {
  const parts: string[] = []
  if (step.spend_threshold != null) parts.push(`Spend >= ${formatCurrency(step.spend_threshold)}`)
  if (step.leads_min != null && step.leads_max != null) {
    if (step.leads_min === step.leads_max) parts.push(`Leads = ${step.leads_min}`)
    else parts.push(`Leads ${step.leads_min}–${step.leads_max}`)
  } else if (step.leads_min != null) {
    parts.push(`Leads >= ${step.leads_min}`)
  } else if (step.leads_max != null) {
    parts.push(`Leads <= ${step.leads_max}`)
  }
  if (step.max_cpl != null) parts.push(`CPL > ${formatCurrency(step.max_cpl)}`)
  return parts.join(", ") || "—"
}

export default function RulesPage() {
  const { data: ruleSet, isLoading } = useDefaultRuleSet()

  if (isLoading) return <div className="text-muted-foreground">Loading...</div>
  if (!ruleSet) return <div className="text-muted-foreground">No rule set found</div>

  const steps = [...(ruleSet.rule_steps || [])].sort((a, b) => a.step_order - b.step_order)

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Rules</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{ruleSet.name}</CardTitle>
          {ruleSet.description && <CardDescription>{ruleSet.description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>Condition</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>New Budget</TableHead>
                <TableHead>Description</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {steps.map((step) => (
                <TableRow key={step.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{step.step_order}</TableCell>
                  <TableCell className="text-sm">{formatCondition(step)}</TableCell>
                  <TableCell>
                    <Badge variant={actionVariant[step.action] || "secondary"}>
                      {actionLabel[step.action] || step.action}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {step.new_budget != null ? formatCurrency(step.new_budget) : "—"}
                  </TableCell>
                  <TableCell className="max-w-[250px] truncate text-xs text-muted-foreground">
                    {step.description || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
