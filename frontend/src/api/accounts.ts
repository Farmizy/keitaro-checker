import api from "./client"
import type { Account, AccountCreate, AccountUpdate } from "@/types"

export async function getAccounts(): Promise<Account[]> {
  const { data } = await api.get("/accounts/")
  return data
}

export async function getAccount(id: string): Promise<Account> {
  const { data } = await api.get(`/accounts/${id}`)
  return data
}

export async function createAccount(payload: AccountCreate): Promise<Account> {
  const { data } = await api.post("/accounts/", payload)
  return data
}

export async function updateAccount(id: string, payload: AccountUpdate): Promise<Account> {
  const { data } = await api.put(`/accounts/${id}`, payload)
  return data
}

export async function deleteAccount(id: string): Promise<void> {
  await api.delete(`/accounts/${id}`)
}
