import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Droplets, Wheat, Ruler, Leaf, Pencil, Download, CalendarDays } from 'lucide-react'
import {
  getField,
  getFieldCropHistory,
  getFieldSoilTests,
  getFieldIndicators,
  listCrops,
  listObservations,
} from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { Crop, Field, FieldIndicator, SoilTest, CropHistory, RoverObservation } from '#/lib/types'
import FieldMap from '#/components/fields/FieldMap'
import IndicatorChart from '#/components/fields/IndicatorChart'
import FieldEditForm from '#/components/fields/FieldEditForm'
import LocalObservations from '#/components/fields/LocalObservations'
import { loadExtraCropHistory, addExtraCropHistory, type LocalCropHistory } from '#/lib/fieldSetup'
import { fieldPhoto } from '#/lib/images'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { Progress } from '#/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '#/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#/components/ui/table'
import { Separator } from '#/components/ui/separator'
import { toast } from 'sonner'

export const Route = createFileRoute('/farmer/fields/$fieldId')({
  component: FieldDetail,
  validateSearch: (search: Record<string, unknown>) => ({
    metric: (search.metric as string) ?? 'rainfall_mm',
  }),
})

export default function FieldDetail() {
  const { fieldId } = Route.useParams()
  const { metric } = Route.useSearch()
  const navigate = useNavigate()
  const lang = useLocale()

  const [field, setField] = useState<Field | null>(null)
  const [history, setHistory] = useState<CropHistory[]>([])
  const [soil, setSoil] = useState<SoilTest[]>([])
  const [indicators, setIndicators] = useState<FieldIndicator[]>([])
  const [crops, setCrops] = useState<Crop[]>([])
  const [rover, setRover] = useState<RoverObservation[]>([])
  const [editing, setEditing] = useState(false)
  const [rangeDays, setRangeDays] = useState(90)
  const [extraHistory, setExtraHistory] = useState<LocalCropHistory[]>(() => loadExtraCropHistory(fieldId))
  const [showHistoryForm, setShowHistoryForm] = useState(false)
  const [histYear, setHistYear] = useState(new Date().getFullYear())
  const [histCrop, setHistCrop] = useState('')
  const [histPlanting, setHistPlanting] = useState('')
  const [histHarvest, setHistHarvest] = useState('')
  const [histYield, setHistYield] = useState('')

  useEffect(() => {
    getField(fieldId).then((f) => setField(f ?? null))
    getFieldCropHistory(fieldId).then(setHistory)
    getFieldSoilTests(fieldId).then(setSoil)
    getFieldIndicators(fieldId).then(setIndicators)
    listCrops().then(setCrops)
    listObservations(fieldId).then(setRover)
  }, [fieldId])

  // Weather-history date range: only show indicators within the chosen window.
  const rangedIndicators = useMemo(() => {
    if (indicators.length === 0) return indicators
    const maxDate = indicators.reduce((a, b) => (a.date > b.date ? a : b), indicators[0]).date
    const cutoff = new Date(maxDate)
    cutoff.setDate(cutoff.getDate() - rangeDays)
    const cut = cutoff.toISOString().slice(0, 10)
    return indicators.filter((i) => i.date >= cut)
  }, [indicators, rangeDays])

  function downloadIndicatorsCsv() {
    const rows = rangedIndicators
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((i) => `${i.date},${i.metric},${i.value},${i.coveragePct},${i.quality}`)
    const text = ['date,metric,value,coverage_pct,quality', ...rows].join('\n')
    const blob = new Blob([text], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `agrifusion-field-${fieldId}-${metric}-${rangeDays}d.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(lang === 'bn' ? 'CSV ডাউনলোড হয়েছে।' : 'CSV downloaded.')
  }

  function addHistoryEntry() {
    if (!histCrop.trim()) {
      toast.error(lang === 'bn' ? 'ফসলের নাম দিন।' : 'Please enter the crop name.')
      return
    }
    const entry: LocalCropHistory = {
      year: histYear,
      cropName: histCrop.trim(),
      plantingDate: histPlanting || undefined,
      harvestDate: histHarvest || undefined,
      yieldT: histYield ? Number(histYield) : undefined,
    }
    addExtraCropHistory(fieldId, entry)
    setExtraHistory(loadExtraCropHistory(fieldId))
    setHistCrop('')
    setHistPlanting('')
    setHistHarvest('')
    setHistYield('')
    setShowHistoryForm(false)
    toast.success(lang === 'bn' ? 'ফসলের ইতিহাস যোগ হয়েছে।' : 'Crop history added.')
  }

  if (!field) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Button variant="ghost" size="sm" onClick={() => navigate({ to: '/farmer/fields' })}>
          <ArrowLeft className="size-4" /> {t('fields', lang)}
        </Button>
        <p className="mt-8 text-muted-foreground">Loading field…</p>
      </main>
    )
  }

  const cropName = (id?: string) => crops.find((c) => c.id === id)?.name ?? id
  const hlsAvg = (() => {
    const h = indicators.filter((i) => i.kind === 'hls_vi')
    return h.length ? Math.round(h.reduce((s, i) => s + i.coveragePct, 0) / h.length) : 0
  })()

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <button
            onClick={() => navigate({ to: '/farmer/fields' })}
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" /> {t('fields', lang)}
          </button>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground">{field.name}</h1>
            {field.isPinEstimate && (
              <Badge variant="secondary" className="text-[10px]">{t('pin_estimate', lang)}</Badge>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditing((v) => !v)}>
            <Pencil className="size-4" /> {lang === 'bn' ? 'জমি সম্পাদনা করুন' : 'Edit field'}
          </Button>
          <Button onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: field.id } as never })}>
            {t('request_comparison', lang)}
          </Button>
        </div>
      </div>

      {editing && field && (
        <div className="mb-4">
          <FieldEditForm
            field={field}
            onSaved={(f) => {
              setField(f)
              setEditing(false)
            }}
            onCancel={() => setEditing(false)}
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'বর্ডার' : 'Boundary'}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] w-full">
              <FieldMap fields={[field]} focusId={field.id} className="rounded-xl" />
            </div>
          </CardContent>
        </Card>

        <Card className="overflow-hidden p-0">
          <img
            src={fieldPhoto(field.name)}
            alt={field.name}
            loading="lazy"
            className="h-32 w-full object-cover"
          />
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'প্রোফাইল' : 'Profile'}</CardTitle>
            <CardDescription>{lang === 'bn' ? 'স্থানীয় ইনপুট' : 'Local inputs'}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-muted-foreground"><Ruler className="size-4" /> {t('fields', lang)}</span>
              <span className="font-medium text-foreground">{field.areaHa} ha</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-muted-foreground"><Droplets className="size-4" /> Irrigation</span>
              <span className="font-medium text-foreground capitalize">{field.irrigation}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-muted-foreground"><Wheat className="size-4" /> Soil</span>
              <span className="font-medium text-foreground">{field.soilType ?? '—'}</span>
            </div>
            <Separator />
            <div>
              <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                <span>{t('coverage', lang)} (HLS)</span>
                <span>{hlsAvg}%</span>
              </div>
              <Progress value={hlsAvg} />
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {field.priorities.map((p) => (
                <Badge key={p} variant="outline" className="text-[10px]">{p.replace('_', ' ')}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">{lang === 'bn' ? 'পরিবেশগত প্রমাণ' : 'Environmental evidence'}</CardTitle>
            <CardDescription>
              {lang === 'bn'
                ? 'POWER দৈনিক ও HLS VI — প্রতিটি পয়েন্টে একক ও আবরণ'
                : 'POWER dailies and HLS VI — units and coverage on every point'}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5">
              <CalendarDays className="size-4 text-muted-foreground" />
              {([30, 90, 180] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setRangeDays(d)}
                  className={
                    'rounded-full px-2.5 py-1 text-xs font-medium transition ' +
                    (rangeDays === d
                      ? 'bg-primary text-primary-foreground'
                      : 'border border-border bg-card text-muted-foreground hover:text-foreground')
                  }
                >
                  {d}d
                </button>
              ))}
            </div>
            <Select
              value={metric}
              onValueChange={(v) => navigate({ search: (prev) => ({ ...prev, metric: v }) as never, replace: true })}
            >
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="rainfall_mm">Rainfall (mm)</SelectItem>
                <SelectItem value="temp_mean_c">Mean temp (°C)</SelectItem>
                <SelectItem value="ndvi">NDVI (HLS)</SelectItem>
              </SelectContent>
            </Select>
            <Button size="sm" variant="outline" onClick={downloadIndicatorsCsv}>
              <Download className="size-4" /> {lang === 'bn' ? 'CSV' : 'CSV'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <IndicatorChart indicators={rangedIndicators} metric={metric} />
          <p className="mt-3 text-xs text-muted-foreground">
            {lang === 'bn'
              ? `নোট: বৃত্তের রঙ মান নির্দেশ করে (সবুজ = ok, হলুদ = partial)। ক্লাউডি/অবাস্তব দিন গোণা হয় না। গত ${rangeDays} দিন দেখানো হচ্ছে।`
              : `Note: point colour encodes quality (green = ok, amber = partial). Cloudy or invalid days are not counted. Showing the last ${rangeDays} days.`}
          </p>
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base">{lang === 'bn' ? 'ফসল ইতিহাস' : 'Crop history'}</CardTitle>
                <CardDescription>
                  {lang === 'bn' ? 'আগের ফসল ও রোপণের তারিখ।' : 'Past crops and planting dates.'}
                </CardDescription>
              </div>
              <Button size="sm" variant="outline" onClick={() => setShowHistoryForm((v) => !v)}>
                {showHistoryForm ? (lang === 'bn' ? 'বন্ধ করুন' : 'Close') : lang === 'bn' ? 'যোগ করুন' : 'Add'}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {showHistoryForm && (
              <div className="mb-4 flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ch-year" className="text-xs font-medium text-muted-foreground">{lang === 'bn' ? 'বছর' : 'Year'}</label>
                    <Input id="ch-year" type="number" value={histYear} onChange={(e) => setHistYear(Number(e.target.value))} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ch-crop" className="text-xs font-medium text-muted-foreground">{lang === 'bn' ? 'ফসল' : 'Crop'}</label>
                    <Input id="ch-crop" value={histCrop} onChange={(e) => setHistCrop(e.target.value)} placeholder={lang === 'bn' ? 'যেমন: T. Aman' : 'e.g. T. Aman'} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ch-planting" className="text-xs font-medium text-muted-foreground">{lang === 'bn' ? 'রোপণের তারিখ' : 'Planting date'}</label>
                    <Input id="ch-planting" type="date" value={histPlanting} onChange={(e) => setHistPlanting(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ch-harvest" className="text-xs font-medium text-muted-foreground">{lang === 'bn' ? 'কাটার তারিখ' : 'Harvest date'}</label>
                    <Input id="ch-harvest" type="date" value={histHarvest} onChange={(e) => setHistHarvest(e.target.value)} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ch-yield" className="text-xs font-medium text-muted-foreground">{lang === 'bn' ? 'ফলন (টন)' : 'Yield (t)'}</label>
                    <Input id="ch-yield" type="number" step="0.1" value={histYield} onChange={(e) => setHistYield(e.target.value)} placeholder="—" />
                  </div>
                </div>
                <Button size="sm" onClick={addHistoryEntry}>{lang === 'bn' ? 'ইতিহাস সংরক্ষণ করুন' : 'Save history'}</Button>
              </div>
            )}
            {history.length === 0 && extraHistory.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {lang === 'bn' ? 'কোনো ইতিহাস নথিভুক্ত নেই।' : 'No history recorded yet.'}
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Year</TableHead>
                    <TableHead>Crop</TableHead>
                    <TableHead>{lang === 'bn' ? 'রোপণ' : 'Planted'}</TableHead>
                    <TableHead className="text-right">Yield</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((h, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{h.year}</TableCell>
                      <TableCell>{cropName(h.cropId)}</TableCell>
                      <TableCell className="text-muted-foreground">—</TableCell>
                      <TableCell className="text-right">{h.yieldT ? `${h.yieldT} t` : '—'}</TableCell>
                    </TableRow>
                  ))}
                  {extraHistory.map((h, i) => (
                    <TableRow key={`extra-${i}`}>
                      <TableCell className="font-medium">{h.year}</TableCell>
                      <TableCell>{h.cropName}</TableCell>
                      <TableCell className="text-muted-foreground">{h.plantingDate ?? '—'}</TableCell>
                      <TableCell className="text-right">{h.yieldT ? `${h.yieldT} t` : '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'রোভার পঠন' : 'Rover readings'}</CardTitle>
            <CardDescription>
              {lang === 'bn' ? 'দৃষ্টিসীমা ও গভীরতা সহ' : 'With quality and depth'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {rover.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {lang === 'bn'
                  ? 'এই জমিতে এখনও রোভার পঠন নেই। অফিসারকে পরিদর্শন চান।'
                  : 'No rover readings yet for this field. Request an inspection.'}
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {rover.map((o) => (
                  <div key={o.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                    <div className="flex items-center gap-2">
                      <Leaf className="size-4 text-primary" />
                      <span className="capitalize">{o.sensor}</span>
                      <span className="text-muted-foreground">@ {o.depthCm} cm</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-medium">{o.value} {o.unit}</span>
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
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {soil.length > 0 && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'মাটির পরীক্ষা' : 'Soil test'}</CardTitle>
            <CardDescription>{soil[0].lab ?? ''} · {soil[0].takenAt}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
              {[
                ['pH', soil[0].ph],
                ['OM %', soil[0].organicMatterPct],
                ['EC dS/m', soil[0].ecDsM],
                ['N ppm', soil[0].nitrogenPpm],
                ['P ppm', soil[0].phosphorusPpm],
                ['K ppm', soil[0].potassiumPpm],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-border p-3 text-center">
                  <div className="text-xs text-muted-foreground">{k}</div>
                  <div className="mt-1 text-lg font-semibold text-foreground">{v}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="mt-4">
        <LocalObservations fieldId={field.id} />
      </div>
    </main>
  )
}

