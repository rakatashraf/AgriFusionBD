import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { ArrowLeft, Droplets, Wheat, Ruler, Leaf } from 'lucide-react'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Progress } from '#/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '#/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#/components/ui/table'
import { Separator } from '#/components/ui/separator'

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

  useEffect(() => {
    getField(fieldId).then((f) => setField(f ?? null))
    getFieldCropHistory(fieldId).then(setHistory)
    getFieldSoilTests(fieldId).then(setSoil)
    getFieldIndicators(fieldId).then(setIndicators)
    listCrops().then(setCrops)
    listObservations(fieldId).then(setRover)
  }, [fieldId])

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
        <Button onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: field.id } as never })}>
          {t('request_comparison', lang)}
        </Button>
      </div>

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

        <Card>
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
          <Select
            value={metric}
            onValueChange={(v) => navigate({ search: (prev) => ({ ...prev, metric: v }) as never, replace: true })}
          >
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="rainfall_mm">Rainfall (mm)</SelectItem>
              <SelectItem value="temp_mean_c">Mean temp (°C)</SelectItem>
              <SelectItem value="ndvi">NDVI (HLS)</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          <IndicatorChart indicators={indicators} metric={metric} />
          <p className="mt-3 text-xs text-muted-foreground">
            {lang === 'bn'
              ? 'নোট: বৃত্তের রঙ মান নির্দেশ করে (সবুজ = ok, হলুদ = partial)। ক্লাউডি/অবাস্তব দিন গোণা হয় না।'
              : 'Note: point colour encodes quality (green = ok, amber = partial). Cloudy or invalid days are not counted.'}
          </p>
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'ফসল ইতিহাস' : 'Crop history'}</CardTitle>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {lang === 'bn' ? 'কোনো ইতিহাস নথিভুক্ত নেই।' : 'No history recorded yet.'}
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Year</TableHead>
                    <TableHead>Crop</TableHead>
                    <TableHead className="text-right">Yield</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((h, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{h.year}</TableCell>
                      <TableCell>{cropName(h.cropId)}</TableCell>
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
    </main>
  )
}

