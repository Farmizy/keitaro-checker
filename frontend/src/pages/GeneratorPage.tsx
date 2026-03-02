import { useState } from "react"
import { useAccounts } from "@/hooks/useAccounts"
import {
  useOffers,
  useDomains,
  useProfiles,
  useCreateProfile,
  useUpdateProfile,
  useGenerate,
  usePages,
} from "@/hooks/useGenerator"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select } from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Plus, Trash2, Download, Settings, Loader2 } from "lucide-react"
import type { CampaignFormEntry, AccountProfileCreate } from "@/types"

const NICHES = ["Диабет", "Гипертония", "Паразиты", "Суставы", "Похудение"]

const GEO_LANGUAGES: Record<string, string> = {
  PL: "Polish",
  BG: "Bulgarian",
  RO: "Romanian",
  LT: "Lithuanian",
  HU: "Hungarian",
  CZ: "Czech",
  HR: "Croatian",
  SK: "Slovak",
  SI: "Slovenian",
  RS: "Serbian",
  GR: "Greek",
}

const BASE_LANGS = ["Albanian", "Chinese (Simplified)", "Georgian"]

function emptyEntry(): CampaignFormEntry {
  return {
    niche: "",
    geo: "",
    product_name: "",
    angle: "",
    domain: "",
    fb_account_id: "",
    offer_id: null,
    num_adsets: 2,
    daily_budget: 30,
    creative_version: "",
  }
}

function buildPreview(
  entry: CampaignFormEntry,
  index: number,
  accountName: string,
): string {
  const today = new Date()
  const dd = String(today.getDate()).padStart(2, "0")
  const mm = String(today.getMonth() + 1).padStart(2, "0")
  const short = accountName.slice(0, 3)
  const ver = entry.creative_version ? ` ${entry.creative_version}` : ""
  return `${dd}.${mm} v${index + 1} ${entry.niche}/${entry.geo}/${entry.product_name}/${entry.angle}${ver}[${short}]`
}

export default function GeneratorPage() {
  const { data: accounts } = useAccounts()
  const { data: offers, isLoading: offersLoading } = useOffers()
  const { data: domains } = useDomains()
  const { data: profiles } = useProfiles()
  const createProfile = useCreateProfile()
  const updateProfile = useUpdateProfile()
  const generate = useGenerate()
  const { data: pages, isLoading: pagesLoading } = usePages(
    profileForm.fb_account_id || null,
  )

  const [entries, setEntries] = useState<CampaignFormEntry[]>([emptyEntry()])
  const [profileDialogOpen, setProfileDialogOpen] = useState(false)
  const [profileForm, setProfileForm] = useState<AccountProfileCreate & { id?: string }>({
    fb_account_id: "",
    page_id: "",
    pixel_id: "",
    instagram_id: "",
    default_geo: "",
    default_budget: 30,
    custom_audiences: "",
  })

  function addEntry() {
    setEntries((prev) => [...prev, emptyEntry()])
  }

  function removeEntry(index: number) {
    setEntries((prev) => prev.filter((_, i) => i !== index))
  }

  function updateEntry(index: number, field: keyof CampaignFormEntry, value: string | number | null) {
    setEntries((prev) =>
      prev.map((e, i) => (i === index ? { ...e, [field]: value } : e)),
    )
  }

  function getAccountName(id: string): string {
    return accounts?.find((a) => a.id === id)?.name ?? ""
  }

  function hasProfile(accountId: string): boolean {
    return profiles?.some((p) => p.fb_account_id === accountId) ?? false
  }

  async function handleGenerate() {
    // Validate all entries have profiles
    for (const entry of entries) {
      if (!entry.fb_account_id) {
        alert("Выберите аккаунт для всех кампаний")
        return
      }
      if (!hasProfile(entry.fb_account_id)) {
        const name = getAccountName(entry.fb_account_id)
        alert(`Настройте профиль (Page ID / Pixel ID) для аккаунта "${name}"`)
        return
      }
      if (!entry.niche || !entry.geo || !entry.product_name || !entry.angle || !entry.domain) {
        alert("Заполните все обязательные поля")
        return
      }
    }
    generate.mutate(entries)
  }

  function openProfileDialog(accountId?: string) {
    const existing = profiles?.find((p) => p.fb_account_id === accountId)
    if (existing) {
      setProfileForm({
        id: existing.id,
        fb_account_id: existing.fb_account_id,
        page_id: existing.page_id,
        pixel_id: existing.pixel_id,
        instagram_id: existing.instagram_id,
        default_geo: existing.default_geo,
        default_budget: existing.default_budget,
        custom_audiences: existing.custom_audiences,
      })
    } else {
      setProfileForm({
        fb_account_id: accountId ?? "",
        page_id: "",
        pixel_id: "",
        instagram_id: "",
        default_geo: "",
        default_budget: 30,
        custom_audiences: "",
      })
    }
    setProfileDialogOpen(true)
  }

  async function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault()
    const { id, ...data } = profileForm
    if (id) {
      await updateProfile.mutateAsync({ id, data })
    } else {
      await createProfile.mutateAsync(data)
    }
    setProfileDialogOpen(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Campaign Generator</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => openProfileDialog()}>
            <Settings className="h-4 w-4" /> Profiles
          </Button>
          <Button onClick={handleGenerate} disabled={generate.isPending}>
            {generate.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Generate
          </Button>
        </div>
      </div>

      {generate.isError && (
        <div className="rounded-lg border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          Ошибка: {(generate.error as Error).message}
        </div>
      )}

      {generate.isSuccess && (
        <div className="rounded-lg border border-green-500 bg-green-500/10 p-3 text-sm text-green-700 dark:text-green-400">
          Excel сгенерирован и скачан!
        </div>
      )}

      <div className="space-y-4">
        {entries.map((entry, idx) => (
          <Card key={idx}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium">
                  Кампания #{idx + 1}
                </CardTitle>
                {entries.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeEntry(idx)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Row 1: Account + Niche + Geo */}
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Аккаунт
                  </label>
                  <div className="flex gap-1">
                    <Select
                      className="flex-1"
                      value={entry.fb_account_id}
                      onChange={(e) =>
                        updateEntry(idx, "fb_account_id", e.target.value)
                      }
                    >
                      <option value="">—</option>
                      {accounts?.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                    </Select>
                    {entry.fb_account_id && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        onClick={() => openProfileDialog(entry.fb_account_id)}
                        title={
                          hasProfile(entry.fb_account_id)
                            ? "Edit profile"
                            : "Set up profile"
                        }
                      >
                        <Settings className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                  {entry.fb_account_id && !hasProfile(entry.fb_account_id) && (
                    <p className="mt-1 text-xs text-destructive">
                      Нет профиля — настройте Page/Pixel ID
                    </p>
                  )}
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Ниша
                  </label>
                  <Select
                    value={entry.niche}
                    onChange={(e) => updateEntry(idx, "niche", e.target.value)}
                  >
                    <option value="">—</option>
                    {NICHES.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Гео
                  </label>
                  <Input
                    placeholder="PL, BG..."
                    value={entry.geo}
                    onChange={(e) =>
                      updateEntry(idx, "geo", e.target.value.toUpperCase())
                    }
                  />
                </div>
              </div>

              {/* Row 2: Product + Angle */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Продукт
                  </label>
                  <Input
                    placeholder="DiabetOver(LP)"
                    value={entry.product_name}
                    onChange={(e) =>
                      updateEntry(idx, "product_name", e.target.value)
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Угол (описание креатива)
                  </label>
                  <Input
                    placeholder="Ewa Dąbrowska: Если уровень глюкозы"
                    value={entry.angle}
                    onChange={(e) =>
                      updateEntry(idx, "angle", e.target.value)
                    }
                  />
                </div>
              </div>

              {/* Row 3: Domain + Offer */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Домен
                  </label>
                  <Select
                    value={entry.domain}
                    onChange={(e) =>
                      updateEntry(idx, "domain", e.target.value)
                    }
                  >
                    <option value="">—</option>
                    {domains?.map((d) => (
                      <option key={d.id} value={d.name}>
                        {d.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Оффер Keitaro
                  </label>
                  <Select
                    value={entry.offer_id?.toString() ?? ""}
                    onChange={(e) =>
                      updateEntry(
                        idx,
                        "offer_id",
                        e.target.value ? Number(e.target.value) : null,
                      )
                    }
                  >
                    <option value="">— без оффера —</option>
                    {offersLoading ? (
                      <option disabled>Загрузка...</option>
                    ) : (
                      offers?.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name} [{o.id}]
                        </option>
                      ))
                    )}
                  </Select>
                </div>
              </div>

              {/* Row 4: Adsets + Budget + Creative version */}
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Адсетов
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={5}
                    value={entry.num_adsets}
                    onChange={(e) =>
                      updateEntry(idx, "num_adsets", Number(e.target.value))
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Бюджет ($)
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={entry.daily_budget}
                    onChange={(e) =>
                      updateEntry(idx, "daily_budget", Number(e.target.value))
                    }
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-muted-foreground">
                    Версия крео
                  </label>
                  <Input
                    placeholder="v6"
                    value={entry.creative_version}
                    onChange={(e) =>
                      updateEntry(idx, "creative_version", e.target.value)
                    }
                  />
                </div>
              </div>

              {/* Preview */}
              {entry.niche && entry.geo && entry.product_name && entry.angle && (
                <div className="rounded-md bg-muted/50 px-3 py-2">
                  <p className="text-xs text-muted-foreground">FB Name:</p>
                  <p className="text-xs font-mono">
                    {buildPreview(entry, idx, getAccountName(entry.fb_account_id))}
                  </p>
                  {entry.geo && GEO_LANGUAGES[entry.geo] && (
                    <>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Languages:
                      </p>
                      <p className="text-xs">
                        Arabic (default), {[...BASE_LANGS, GEO_LANGUAGES[entry.geo]].join(", ")}
                      </p>
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Button variant="outline" className="w-full" onClick={addEntry}>
        <Plus className="h-4 w-4" /> Добавить кампанию
      </Button>

      {/* Profile dialog */}
      <Dialog open={profileDialogOpen} onClose={() => setProfileDialogOpen(false)}>
        <DialogHeader>
          <DialogTitle>
            {profileForm.id ? "Редактировать профиль" : "Новый профиль"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleProfileSubmit} className="space-y-3">
          {!profileForm.id && (
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">
                Аккаунт
              </label>
              <Select
                value={profileForm.fb_account_id}
                onChange={(e) =>
                  setProfileForm((f) => ({
                    ...f,
                    fb_account_id: e.target.value,
                  }))
                }
                required
              >
                <option value="">—</option>
                {accounts
                  ?.filter((a) => !profiles?.some((p) => p.fb_account_id === a.id))
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </Select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">
                Page ID
              </label>
              {pages && pages.length > 0 ? (
                <Select
                  value={profileForm.page_id}
                  onChange={(e) =>
                    setProfileForm((f) => ({ ...f, page_id: e.target.value }))
                  }
                  required
                >
                  <option value="">—</option>
                  {pages.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.id})
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  placeholder={pagesLoading ? "Загрузка..." : "108126015392349"}
                  value={profileForm.page_id}
                  onChange={(e) =>
                    setProfileForm((f) => ({ ...f, page_id: e.target.value }))
                  }
                  required
                />
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">
                Pixel ID
              </label>
              <Input
                placeholder="878309118145658"
                value={profileForm.pixel_id}
                onChange={(e) =>
                  setProfileForm((f) => ({ ...f, pixel_id: e.target.value }))
                }
                required
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">
              Instagram Account ID
            </label>
            <Input
              placeholder="24862920880050484"
              value={profileForm.instagram_id}
              onChange={(e) =>
                setProfileForm((f) => ({ ...f, instagram_id: e.target.value }))
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">
                Гео по умолчанию
              </label>
              <Input
                placeholder="BG"
                value={profileForm.default_geo}
                onChange={(e) =>
                  setProfileForm((f) => ({ ...f, default_geo: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">
                Бюджет по умолчанию ($)
              </label>
              <Input
                type="number"
                value={profileForm.default_budget}
                onChange={(e) =>
                  setProfileForm((f) => ({
                    ...f,
                    default_budget: Number(e.target.value),
                  }))
                }
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">
              Custom Audiences
            </label>
            <Input
              placeholder="giperop"
              value={profileForm.custom_audiences}
              onChange={(e) =>
                setProfileForm((f) => ({
                  ...f,
                  custom_audiences: e.target.value,
                }))
              }
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setProfileDialogOpen(false)}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={createProfile.isPending || updateProfile.isPending}
            >
              {profileForm.id ? "Сохранить" : "Создать"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  )
}
