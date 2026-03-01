import api from "./client"
import type { RuleSet, RuleStep } from "@/types"

export async function getRuleSets(): Promise<RuleSet[]> {
  const { data } = await api.get("/rules/")
  return data
}

export async function getDefaultRuleSet(): Promise<RuleSet> {
  const { data } = await api.get("/rules/default")
  return data
}

export async function updateRuleStep(
  stepId: string,
  payload: Partial<RuleStep>,
): Promise<RuleStep> {
  const { data } = await api.put(`/rules/steps/${stepId}`, payload)
  return data
}
