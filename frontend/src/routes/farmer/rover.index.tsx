import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Bot, Battery, MapPin, Wrench, ShieldCheck, Leaf } from 'lucide-react'
import { listDevices, listObservations, listFields, createCase } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { RoverDevice, RoverObservation, Field } from '#/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Progress } from '#/components/ui/progress'
import { Separator } from '#/components/ui/separator'
import { toast } from 'sonner'

const DEVICE_STATUS: Record<string, { en: string; bn: string; cls: string }> = {
  idle: { en: 'Idle', bn: 'অলস', cls: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200' },
  on_mission: { en: 'On mission', bn: 'মিশনে', cls: 'border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-200' },
  service_due: { en: 'Service due', bn: 'সেবা প্রয়োজন', cls: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200' },
  offline: { en: 'Offline', bn: 'অফলাইন', cls: 'border-zinc-300 bg-zinc-100 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400' },
}

export const Route = createFileRoute('/farmer/rover/')({ component: RoverPage })

export default function RoverPage() {
  const lang = useLocale()
  const [devices, setDevices] = useState<RoverDevice[]>([])
  const [obs, setObs] = useState<RoverObservation[]>([])
  const [fields, setFields] = useState<Field[]>([])

  useEffect(() => {
    listDevices().then(setDevices)
    listObservations().then(setObs)
    listFields().then(setFields)
  }, [])

  const fieldLabel = (id: string) => fields.find((f) => f.id === id)?.name ?? id

  async function requestInspection(fieldId: string) {
    const c = await createCase({
      fieldId,
      subject: lang === 'bn' ? 'রোভার পরিদর্শন অনুরোধ' : 'Rover inspection request',
      body: lang === 'bn' ? 'দুইপাশে মাটির আর্দ্রতা পরীক্ষার জন্য রোভার দরকার।' : 'Requesting a rover visit for soil moisture checks.',
    })
    toast.success(lang === 'bn' ? `কেস খোলা হয়েছে: ${c.id}` : `Case opened: ${c.id}`)
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
                <span>meas {new Date(o.measuredAt).toISOString().slice(0, 16).replace('T', ' ')}</span>
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
