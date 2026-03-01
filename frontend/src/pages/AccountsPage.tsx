import { useState } from "react"
import { useAccounts, useCreateAccount, useUpdateAccount, useDeleteAccount } from "@/hooks/useAccounts"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Plus, Pencil, Trash2 } from "lucide-react"
import type { AccountCreate } from "@/types"

const emptyForm: AccountCreate = {
  name: "",
  account_id: "",
  access_token: "",
  cookie: "",
  useragent: "",
  proxy_type: "socks5",
  proxy_host: "",
  proxy_port: 1080,
  proxy_login: "",
  proxy_password: "",
}

export default function AccountsPage() {
  const { data: accounts, isLoading } = useAccounts()
  const createMut = useCreateAccount()
  const updateMut = useUpdateAccount()
  const deleteMut = useDeleteAccount()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState<AccountCreate>(emptyForm)

  function openCreate() {
    setEditId(null)
    setForm(emptyForm)
    setDialogOpen(true)
  }

  function openEdit(id: string) {
    const acc = accounts?.find((a) => a.id === id)
    if (!acc) return
    setEditId(id)
    setForm({
      name: acc.name,
      account_id: acc.account_id,
      access_token: "",
      cookie: "",
      useragent: acc.useragent,
      proxy_type: acc.proxy_type,
      proxy_host: acc.proxy_host,
      proxy_port: acc.proxy_port,
      proxy_login: acc.proxy_login,
      proxy_password: "",
    })
    setDialogOpen(true)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (editId) {
      const payload = Object.fromEntries(
        Object.entries(form).filter(([, v]) => v !== "" && v !== 0),
      )
      await updateMut.mutateAsync({ id: editId, data: payload })
    } else {
      await createMut.mutateAsync(form)
    }
    setDialogOpen(false)
  }

  function set<K extends keyof AccountCreate>(key: K, value: AccountCreate[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Accounts</h1>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Add Account
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">FB Accounts</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : !accounts?.length ? (
            <p className="text-muted-foreground">No accounts yet</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Account ID</TableHead>
                  <TableHead>Proxy</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-24">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acc) => (
                  <TableRow key={acc.id}>
                    <TableCell className="font-medium">{acc.name}</TableCell>
                    <TableCell className="font-mono text-xs">{acc.account_id}</TableCell>
                    <TableCell className="text-xs">
                      {acc.proxy_type}://{acc.proxy_host}:{acc.proxy_port}
                    </TableCell>
                    <TableCell>
                      <Badge variant={acc.is_active ? "success" : "secondary"}>
                        {acc.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(acc.id)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            if (confirm("Delete this account?")) deleteMut.mutate(acc.id)
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
        <DialogHeader>
          <DialogTitle>{editId ? "Edit Account" : "New Account"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input placeholder="Name" value={form.name} onChange={(e) => set("name", e.target.value)} required />
          <Input placeholder="Account ID (act_xxx)" value={form.account_id} onChange={(e) => set("account_id", e.target.value)} required={!editId} />
          <Input placeholder="Access Token" value={form.access_token} onChange={(e) => set("access_token", e.target.value)} required={!editId} />
          <Input placeholder="Cookie" value={form.cookie} onChange={(e) => set("cookie", e.target.value)} required={!editId} />
          <Input placeholder="User Agent" value={form.useragent} onChange={(e) => set("useragent", e.target.value)} required={!editId} />
          <div className="grid grid-cols-3 gap-2">
            <Select value={form.proxy_type} onChange={(e) => set("proxy_type", e.target.value as AccountCreate["proxy_type"])}>
              <option value="socks5">SOCKS5</option>
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
            </Select>
            <Input placeholder="Proxy Host" value={form.proxy_host} onChange={(e) => set("proxy_host", e.target.value)} required={!editId} />
            <Input type="number" placeholder="Port" value={form.proxy_port || ""} onChange={(e) => set("proxy_port", Number(e.target.value))} required={!editId} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Proxy Login" value={form.proxy_login} onChange={(e) => set("proxy_login", e.target.value)} required={!editId} />
            <Input type="password" placeholder="Proxy Password" value={form.proxy_password} onChange={(e) => set("proxy_password", e.target.value)} required={!editId} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={createMut.isPending || updateMut.isPending}>
              {editId ? "Save" : "Create"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
