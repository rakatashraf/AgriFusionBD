import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { MapPin, Ruler, Droplets, Wheat, MapPinned } from 'lucide-react'
import { listFields, getFieldIndicators } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { Field } from '#/lib/types'
import FieldMap from '#/components/fields/FieldMap'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Progress } from '#/components/ui/progress'
import { Separator } from '#/components/ui/separator'

export const Route = createFileRoute('/farmer/fields/')({ component: FieldsPage })

export default function FieldsPage() {
  const lang = useLocale()
  const navigate = useNavigate()
  const [fields, setFields] = useState<Field[]>([])
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [indicators, setIndicators] = useState<Record<string, { coverage: number }>>({})

  useEffect(() => {
    listFields().then(setFields)
  }, [])

  useEffect(() => {
    if (!selectedId) return
    getFieldIndicators(selectedId).then((inds) => {
      const hls = inds.filter((i) => i.kind === 'hls_vi')
      const avg = hls.length ? Math.round(hls.reduce((s, i) => s + i.coveragePct, 0) / hls.length) : 0
      setIndicators((prev) => ({ ...prev, [selectedId]: { coverage: avg } }))
    })
  }, [selectedId])

  const selected = fields.find((f) => f.id === selectedId)
  const stats = useMemo(() => {
    if (!selected) return null
    const cov = indicators[selected.id]?.coverage ?? 0
    return { area: selected.areaHa, cov }
  }, [selected, indicators])

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-6 flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-foreground">{t('fields', lang)}</h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'আপনার জমির তালিকা। নকশা বা পিন নির্বাচন করে তুলনা শুরু করুন।'
            : 'Your fields. Select a boundary or pin to begin a comparison.'}
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base">{lang === 'bn' ? 'জমি ম্যাপ' : 'Field map'}</CardTitle>
                <CardDescription>{lang === 'bn' ? 'জমি নির্বাচন করতে ক্লিক করুন' : 'Click a field to select it'}</CardDescription>
              </div>
              <Badge variant="outline" className="gap-1"><MapPinned className="size-3.5" /> {fields.length}</Badge>
            </CardHeader>
            <CardContent>
              <div className="h-[420px] w-full">
                <FieldMap
                  fields={fields}
                  selectedId={selectedId}
                  onSelect={(id) => setSelectedId(id)}
                  className="rounded-xl"
                />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <div className="flex flex-col gap-3">
            {fields.map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedId(f.id)}
                className={
                  'rounded-xl border p-4 text-left transition ' +
                  (f.id === selectedId
                    ? 'border-primary bg-accent/40'
                    : 'border-border bg-card hover:border-primary/40')
                }
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <MapPin className="size-4 text-primary" />
                    <span className="font-medium text-foreground">{f.name}</span>
                  </div>
                  {f.isPinEstimate && (
                    <Badge variant="secondary" className="text-[10px]">{t('pin_estimate', lang)}</Badge>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><Ruler className="size-3" /> {f.areaHa} ha</span>
                  <span className="inline-flex items-center gap-1"><Droplets className="size-3" /> {f.irrigation}</span>
                  <span className="inline-flex items-center gap-1"><Wheat className="size-3" /> {f.soilType ?? '—'}</span>
                </div>
              </button>
            ))}

            {selected && stats && (
              <Card className="mt-1 border-primary/30">
                <CardHeader>
                  <CardTitle className="text-sm">{lang === 'bn' ? 'নির্বাচিত জমি' : 'Selected field'}</CardTitle>
                  <CardDescription>{selected.name}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{t('coverage', lang)} (HLS)</span>
                      <span>{stats.cov}%</span>
                    </div>
                    <Progress value={stats.cov} />
                  </div>
                  <Separator />
                  <div className="flex gap-2">
                    <Button size="sm" className="flex-1" onClick={() => navigate({ to: `/farmer/fields/${selected.id}` })}>
                      {lang === 'bn' ? 'বিস্তারিত দেখুন' : 'View details'}
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1" onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: selected.id } as never })}>
                      {t('request_comparison', lang)}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}
