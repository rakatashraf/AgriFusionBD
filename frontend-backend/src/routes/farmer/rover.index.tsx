import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Bot, Battery, MapPin, Wrench, ShieldCheck, Leaf, Radar, Send, Clock } from 'lucide-react'
import { listDevices, listObservations, listFields, createCase, currentUser } from '#/lib/api'
import { ROVER_CHECKS } from '#/lib/advisory'
import { loadRoverRequests, saveRoverRequest, openRequestForField } from '#/lib/roverPaths'
import RoverCheckCard from '#/components/advisory/RoverCheckCard'
import { useLocale, t } from '#/lib/i18n'
import type { RoverDevice, RoverObservation, Field, RoverRequest } from '#/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { Progress } from '#/components/ui/progress'
import { Separator } from '#/components/ui/separator'
import { toast } from 'sonner'

const REQUEST_STATUS: Record<RoverRequest['status'], { en: string; bn: string; cls: string }> = {
  requested: { en: 'Requested', bn: 'অনুরোধ করা হয়েছে', cls: 'border-sky-300 bg-sky-100 text-sky-800' },
  path_assigned: { en: 'Path assigned', bn: 'পথ নির্ধারিত', cls: 'border-amber-300 bg-amber-100 text-amber-800' },
  completed: { en: 'Completed', bn: 'সম্পন্ন', cls: 'border-emerald-300 bg-emerald-100 text-emerald-800' },
}

const DEVICE_STATUS: Record<string, { en: string; bn: string; cls: string }> = {
  idle: { en: 'Idle', bn: 'অলস', cls: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200' },
  on_mission: { en: 'On mission', bn: 'মিশনে', cls: 'border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-200' },
  service_due: { en: 'Service due', bn: 'সেবা প্রয়োজন', cls: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200' },
  offline: { en: 'Offline', bn: 'অফলাইন', cls: 'border-zinc-300 bg-zinc-100 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400' },
}

export const Route = createFileRoute('/farmer/rover/')({ component: RoverPage })

function RoverPage() {
  const lang = useLocale()
  const [devices, setDevices] = useState<RoverDevice[]>([])
  const [obs, setObs] = useState<RoverObservation[]>([])
  const [fields, setFields] = useState<Field[]>([])
  const [requests, setRequests] = useState<RoverRequest[]>([])
  const [requestFieldId, setRequestFieldId] = useState('')
  const [requestNote, setRequestNote] = useState('')

  useEffect(() => {
    listDevices().then(setDevices).catch(() => setDevices([]))
    listObservations().then(setObs).catch(() => setObs([]))
    listFields().then(setFields).catch(() => setFields([]))
    setRequests(loadRoverRequests())
  }, [])

  const fieldLabel = (id: string) => fields.find((f) => f.id === id)?.name ?? id

  /** Ask for rover analysis on any registered field. A professional then
   *  sets the rover path for it. */
  function requestRoverAnalysis(fieldId: string, note?: string) {
    const field = fields.find((f) => f.id === fieldId)
    if (!field) return
    const existing = openRequestForField(fieldId)
    if (existing) {
      toast.error(lang === 'bn' ? 'এই জমির জন্য ইতিমধ্যে একটি অনুরোধ আছে।' : 'There is already an open request for this field.')
      return
    }
    const user = currentUser()
    const req: RoverRequest = {
      id: `req-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`,
      fieldId: field.id,
      fieldName: field.name,
      farmerId: user?.id ?? 'farmer',
      farmerName: user?.name ?? 'Farmer',
      note: note?.trim() || undefined,
      status: 'requested',
      createdAt: new Date().toISOString(),
    }
    setRequests(saveRoverRequest(req))
    setRequestFieldId('')
    setRequestNote('')
    toast.success(lang === 'bn' ? 'রোভার বিশ্লেষণের অনুরোধ পাঠানো হয়েছে।' : 'Rover analysis requested.')
  }

  async function requestInspection(fieldId: string) {
    try {
      const c = await createCase({
        fieldId,
        subject: lang === 'bn' ? 'রোভার পরিদর্শন অনুরোধ' : 'Rover inspection request',
        body: lang === 'bn' ? 'দুইপাশে মাটির আর্দ্রতা পরীক্ষার জন্য রোভার দরকার।' : 'Requesting a rover visit for soil moisture checks.',
      })
      toast.success(lang === 'bn' ? `কেস খোলা হয়েছে: ${c.id}` : `Case opened: ${c.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">{t('rover', lang)}</h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'সম্প্রদায় সেবা প্রবাহ: কৃষক অনুরোধ → অফিসার অনুমোদন → রোভার সংগ্রহ → পুনরায় তুলনা।'
            : 'Community service workflow: farmer request → officer approval → rover collection → refreshed comparison.'}
        </p>
      </header>

      {/* Request rover analysis — any registered field can be requested.
          The professional then sets the rover path for it. */}
      <Card className="mb-4 border-primary/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Send className="size-4 text-primary" />
            {lang === 'bn' ? 'রোভার বিশ্লেষণের অনুরোধ করুন' : 'Request rover analysis'}
          </CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'আপনার যেকোনো নিবন্ধিত জমির জন্য রোভার চান — পেশাজীবী সেই জমির জন্য রোভার পথ নির্ধারণ করবেন।'
              : 'Ask for the rover on any of your registered fields — a professional will set the rover path for it.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-col gap-3 sm:flex-row">
            <select
              value={requestFieldId}
              onChange={(e) => setRequestFieldId(e.target.value)}
              className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none"
              aria-label={lang === 'bn' ? 'জমি বেছে নিন' : 'Choose a field'}
            >
              <option value="">{lang === 'bn' ? 'জমি বেছে নিন' : 'Choose a field'}</option>
              {fields.map((f) => {
                const open = openRequestForField(f.id)
                return (
                  <option key={f.id} value={f.id} disabled={!!open}>
                    {f.name} · {f.areaHa} ha{open ? ` — ${REQUEST_STATUS[open.status][lang]}` : ''}
                  </option>
                )
              })}
            </select>
            <Input
              value={requestNote}
              onChange={(e) => setRequestNote(e.target.value)}
              placeholder={lang === 'bn' ? 'কী পরীক্ষা করাতে চান? (ঐচ্ছিক)' : 'What should the rover check? (optional)'}
              className="flex-1"
            />
            <Button
              onClick={() => requestFieldId && requestRoverAnalysis(requestFieldId, requestNote)}
              disabled={!requestFieldId}
            >
              <Send className="size-4" /> {lang === 'bn' ? 'অনুরোধ পাঠান' : 'Send request'}
            </Button>
          </div>
          {requests.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'আমার অনুরোধ' : 'My requests'}
              </p>
              {requests.map((r) => {
                const st = REQUEST_STATUS[r.status]
                return (
                  <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2.5">
                    <div className="flex items-center gap-2 text-sm">
                      <Bot className="size-4 shrink-0 text-primary" />
                      <span className="font-medium text-foreground">{r.fieldName}</span>
                      {r.note && <span className="text-muted-foreground">— {r.note}</span>}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1"><Clock className="size-3" /> {new Date(r.createdAt).toISOString().slice(0, 10)}</span>
                      <Badge variant="outline" className={st.cls}>{st[lang]}</Badge>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        {devices.map((d) => {
          const st = DEVICE_STATUS[d.status]
          return (
            <Card key={d.id}>
              <CardHeader className="flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex size-11 items-center justify-center rounded-lg bg-accent">
                    <Bot className="size-6 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-base">{d.name}</CardTitle>
                    <CardDescription>{d.model}</CardDescription>
                  </div>
                </div>
                <Badge variant="outline" className={st.cls}>{st[lang]}</Badge>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Battery className="size-3" /> Battery</span>
                    <span>{d.batteryPct}%</span>
                  </div>
                  <Progress value={d.batteryPct} className={d.batteryPct < 30 ? '[&>div]:bg-amber-500' : ''} />
                </div>
                <Separator />
                <div className="flex flex-col gap-1 text-sm">
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><MapPin className="size-3" /> Fields</span>
                    <span className="text-foreground">{d.fieldIds.map(fieldLabel).join(', ') || '—'}</span>
                  </div>
                  <div className="flex items-center justify-between text-muted-foreground">
                    <span>Grant expires</span>
                    <span className="text-foreground">{d.grantExpiresAt ?? '—'}</span>
                  </div>
                </div>
                <Separator />
                <div className="flex flex-col gap-2">
                  {d.fieldIds.map((fid) => (
                    <Button key={fid} variant="outline" size="sm" onClick={() => requestInspection(fid)}>
                      <Wrench className="size-4" />
                      {lang === 'bn' ? 'পরিদর্শন চান' : 'Request inspection'} · {fieldLabel(fid)}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Field checks — what the rover actually measured in each field:
          nutrition (N/P/K), soil moisture, temperature, crop health through
          the camera, harmful insects and crop diseases. */}
      <div className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <Radar className="size-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground">
            {lang === 'bn' ? 'জমি পরীক্ষার ফলাফল' : 'Field check results'}
          </h2>
        </div>
        <p className="mb-4 text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'রোভার প্রতিটি জমিতে গিয়ে পুষ্টি, আর্দ্রতা, তাপমাত্রা, ক্যামেরায় ফসলের স্বাস্থ্য, ক্ষতিকর পোকা ও রোগ পরীক্ষা করে।'
            : 'The rover visits each field and checks nutrition, soil moisture, temperature, crop health through its camera, harmful insects and crop diseases.'}
        </p>
        <div className="grid gap-4 lg:grid-cols-2">
          {ROVER_CHECKS.map((c) => (
            <RoverCheckCard key={c.id} check={c} />
          ))}
        </div>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Leaf className="size-4" /> {t('observations', lang)}</CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'প্রতিটি পঠনে পরিমাপ-সময়, গভীরতা, একক, ক্যালিব্রেশন ও মান।'
              : 'Each reading includes measurement time, depth, units, calibration and quality.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {obs.map((o) => (
            <div key={o.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2.5">
              <div className="flex items-center gap-3">
                <Badge variant="outline" className="capitalize">{o.sensor}</Badge>
                <span className="text-sm font-medium text-foreground">{o.value} {o.unit}</span>
                <span className="text-xs text-muted-foreground">@ {o.depthCm} cm · {fieldLabel(o.fieldId)}</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>meas {o.measuredAt ? new Date(o.measuredAt).toISOString().slice(0, 16).replace('T', ' ') : '—'}</span>
                <span>· {devices.find((d) => d.id === o.deviceId)?.name}</span>
                <Badge
                  variant="outline"
                  className={
                    o.quality === 'ok'
                      ? 'border-emerald-300 text-emerald-700'
                      : o.quality === 'flagged'
                        ? 'border-amber-300 text-amber-700'
                        : 'border-rose-300 text-rose-700'
                  }
                >
                  {o.quality}
                </Badge>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="mt-4">
        <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" />
          <div>
            <p className="font-medium text-foreground">
              {lang === 'bn' ? 'নিরাপত্তা সীমানা' : 'Control boundary'}
            </p>
            <p className="mt-1">
              {lang === 'bn'
                ? 'রোভার-চালনা কমান্ডের জন্য পৃথক অনুমোদন, শেষ-টু-এন্ড লেটেন্সি বাজেট ও স্থানীয় উপস্থিতি প্রয়োজন। MVP-তে দূরবর্তী চালনা নেই — পর্যবেক্ষণ আপলোড ও নিরাপদ মিশন মাত্র।'
                : 'Remote driving requires separate authorization, an end-to-end latency budget and local supervision. The MVP ships observation upload and safe missions only — no remote driving.'}
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
