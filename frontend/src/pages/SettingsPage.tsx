import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useSchedulerStatus } from "@/hooks/useScheduler"
import { getSettings, updateSettings, type UserSettingsUpdate } from "@/api/settings"

function StatusBadge({ configured }: { configured: boolean }) {
  return configured ? (
    <Badge variant="success" className="text-xs">Подключено</Badge>
  ) : (
    <span className="text-xs text-muted-foreground">Не настроено</span>
  )
}

interface FieldProps {
  label: string
  description: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
}

function SettingsField({ label, description, value, onChange, placeholder, type = "text" }: FieldProps) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">{label}</label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  )
}

export default function SettingsPage() {
  const { data: scheduler } = useSchedulerStatus()
  const queryClient = useQueryClient()

  const { data: settings, isLoading } = useQuery({
    queryKey: ["user-settings"],
    queryFn: getSettings,
  })

  const [form, setForm] = useState<UserSettingsUpdate>({})

  useEffect(() => {
    if (settings) {
      setForm({
        keitaro_url: settings.keitaro_url,
        keitaro_login: settings.keitaro_login,
        keitaro_password: settings.keitaro_password,
        panel_api_url: settings.panel_api_url,
        panel_jwt: settings.panel_jwt,
        telegram_bot_token: settings.telegram_bot_token,
        telegram_chat_id: settings.telegram_chat_id,
      })
    }
  }, [settings])

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-settings"] })
    },
  })

  const handleSave = () => {
    mutation.mutate(form)
  }

  const set = (field: keyof UserSettingsUpdate) => (value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Загрузка...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Настройки</h1>
        <Button onClick={handleSave} disabled={mutation.isPending}>
          {mutation.isPending ? "Сохранение..." : "Сохранить"}
        </Button>
      </div>

      {mutation.isSuccess && (
        <div className="rounded-md bg-green-500/10 border border-green-500/20 px-4 py-2 text-sm text-green-600">
          Настройки сохранены
        </div>
      )}

      {mutation.isError && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-2 text-sm text-destructive">
          Ошибка сохранения: {(mutation.error as Error).message}
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Keitaro</CardTitle>
          <StatusBadge configured={settings?.keitaro_configured ?? false} />
        </CardHeader>
        <CardContent className="space-y-4">
          <SettingsField
            label="URL"
            description="URL вашего Keitaro трекера"
            value={form.keitaro_url ?? ""}
            onChange={set("keitaro_url")}
            placeholder="https://pro1.trk.dev"
          />
          <SettingsField
            label="Логин"
            description="Логин для входа в панель Keitaro"
            value={form.keitaro_login ?? ""}
            onChange={set("keitaro_login")}
            placeholder="admin"
          />
          <SettingsField
            label="Пароль"
            description="Пароль для входа в панель Keitaro"
            value={form.keitaro_password ?? ""}
            onChange={set("keitaro_password")}
            type="password"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Panel API (2KK)</CardTitle>
          <StatusBadge configured={settings?.panel_configured ?? false} />
        </CardHeader>
        <CardContent className="space-y-4">
          <SettingsField
            label="API URL"
            description="URL API вашей панели"
            value={form.panel_api_url ?? ""}
            onChange={set("panel_api_url")}
            placeholder="https://fbm.adway.team/api"
          />
          <SettingsField
            label="JWT Token"
            description="JWT токен из панели (Профиль → API Token)"
            value={form.panel_jwt ?? ""}
            onChange={set("panel_jwt")}
            type="password"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Telegram</CardTitle>
          <StatusBadge configured={settings?.telegram_configured ?? false} />
        </CardHeader>
        <CardContent className="space-y-4">
          <SettingsField
            label="Bot Token"
            description="Токен бота от @BotFather в Telegram"
            value={form.telegram_bot_token ?? ""}
            onChange={set("telegram_bot_token")}
          />
          <SettingsField
            label="Chat ID"
            description="ID чата для уведомлений (узнать через @userinfobot)"
            value={form.telegram_chat_id ?? ""}
            onChange={set("telegram_chat_id")}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Планировщик</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Статус</span>
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
            <span className="text-sm text-muted-foreground">Интервал проверки</span>
            <span className="text-sm">{scheduler?.interval_minutes ?? "\u2014"} мин</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Следующий запуск</span>
            <span className="text-sm">
              {scheduler?.next_run
                ? new Date(scheduler.next_run).toLocaleString("ru-RU")
                : "\u2014"}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
