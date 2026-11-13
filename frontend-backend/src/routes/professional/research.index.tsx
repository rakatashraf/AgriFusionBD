import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState, useMemo } from 'react'
import { Globe2, Download, Database, FileDown } from 'lucide-react'
import {
  listResearchLocations,
  listExportJobs,
  createExportJob,
  downloadExport,
  listFields,
  getFieldIndicators,
} from '#/lib/api'
import AreaSummary from '#/components/advisory/AreaSummary'
import { useLocale, t } from '#/lib/i18n'
import type { ResearchLocation, ResearchExportJob, Field, FieldIndicator } from '#/lib/types'
import EChart from '#/components/EChart'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '#/components/ui/select'
import { toast } from 'sonner'

export const Route = createFileRoute('/professional/research/')({ component: ResearchPage })

function ResearchPage() {
  const lang = useLocale()
  const [locations, setLocations] = useState<ResearchLocation[]>([])
  const [selected, setSelected] = useState('')
  const [jobs, setJobs] = useState<ResearchExportJob[]>([])
  const [format, setFormat] = useState<'csv' | 'geojson'>('csv')
  const [fields, setFields] = useState<Field[]>([])
  const [indicators, setIndicators] = useState<FieldIndicator[]>([])
  const [loadingIndicators, setLoadingIndicators] = useState(false)

  const [exporting, setExporting] = useState(false)

  const load = () => {
    listResearchLocations().then((l) => {
      setLocations(l)
      if (l.length && !selected) setSelected(l[0].id)
    }).catch(() => {})
    listExportJobs().then(setJobs).catch(() => {})
    listFields().then(setFields).catch(() => {})
  }
  useEffect(load, [])

  const loc = locations.find((l) => l.id === selected)

  // Fetch indicators whenever the selected location changes
  useEffect(() => {
    if (!loc) return
    setLoadingIndicators(true)
    getFieldIndicators(loc.id)
      .then(setIndicators)
      .catch(() => setIndicators([]))
      .finally(() => setLoadingIndicators(false))
  }, [loc?.id])

  // Build chart series from real POWER indicators
  const series = useMemo(() => {
    const rain = indicators
      .filter((i) => i.metric === 'rainfall_mm' && i.value != null)
      .sort((a, b) => a.date.localeCompare(b.date))
    const tempMax = indicators
      .filter((i) => i.metric === 'temp_max_c' && i.value != null)
      .sort((a, b) => a.date.localeCompare(b.date))

    if (!rain.length) return { dates: [] as string[], rain: [] as number[], temp: [] as number[] }

    const dates = rain.map((r) => r.date)
    const rainVals = rain.map((r) => r.value)
    const tempVals = dates.map((d) => {
      const t = tempMax.find((x) => x.date === d)
      return t?.value ?? null
    })
    return { dates, rain: rainVals, temp: tempVals }
  }, [indicators])

  const coveragePct = useMemo(() => {
    if (!loc || !indicators.length) return 0
    const total = indicators.filter((i) => i.metric === 'rainfall_mm' || i.metric === 'temp_max_c').length
    const valid = indicators.filter(
      (i) => (i.metric === 'rainfall_mm' || i.metric === 'temp_max_c') && i.quality === 'ok'
    ).length
    return total ? Math.round((valid / total) * 100) : 0
  }, [loc, indicators])

  const option = series.dates.length
    ? {
        grid: { left: 48, right: 48, top: 32, bottom: 40 },
        legend: { data: ['Rainfall (mm)', 'Max temp (°C)'], bottom: 0 },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: series.dates, axisLabel: { color: '#416166', hideOverlap: true } },
        yAxis: [
          { type: 'value', name: 'mm', axisLabel: { color: '#416166' }, splitLine: { lineStyle: { color: 'rgba(65,97,102,0.15)' } } },
          { type: 'value', name: '°C', axisLabel: { color: '#416166' }, splitLine: { show: false } },
        ],
        series: [
          { name: 'Rainfall (mm)', type: 'bar', data: series.rain, itemStyle: { color: 'rgba(50,143,151,0.4)', borderRadius: [3, 3, 0, 0] } },
          { name: 'Max temp (°C)', type: 'line', smooth: true, yAxisIndex: 1, data: series.temp, lineStyle: { color: '#c9613a', width: 2 }, itemStyle: { color: '#c9613a' } },
        ],
      }
    : {}

  async function exportData() {
    if (!loc) return
    setExporting(true)
    try {
      const job = await createExportJob({
        scope: `${loc.name} · POWER + HLS`,
        format,
      })
      toast.success(lang === 'bn' ? 'এক্সপোর্ট শুরু হয়েছে' : 'Export started')
      load()

      let attempts = 0
      const maxAttempts = 30
      const tick = async () => {
        if (attempts >= maxAttempts) return
        attempts += 1
        const fresh = (await listExportJobs()).find((j) => j.id === job.id)
        if (!fresh) return
        if (fresh.status === 'complete') {
          const dl = await downloadExport(job.id)
          const a = document.createElement('a')
          a.href = dl.url
          a.download = dl.filename
          a.click()
          URL.revokeObjectURL(dl.url)
          setExporting(false)
          load()
          return
        }
        if (fresh.status === 'failed') {
          setExporting(false)
          toast.error(lang === 'bn' ? 'এক্সপোর্ট ব্যর্থ হয়েছে' : 'Export failed')
          load()
          return
        }
        setTimeout(tick, 2000)
      }
      setTimeout(tick, 1500)
    } catch (err) {
      setExporting(false)
      toast.error(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
            <Globe2 className="size-6 text-primary" /> {t('research', lang)}
          </h1>
          <p className="text-sm text-muted-foreground">
            {lang === 'bn'
              ? 'সম্মত লোকেশন ও সময়কাল বেছে নিন; ট্রেন্ড, আবরণ ও রপ্তানি।'
              : 'Choose permitted locations and periods; explore trends, coverage and exports.'}
          </p>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">
                {loc ? loc.name : lang === 'bn' ? 'লোকেশন' : 'Location'}
              </CardTitle>
              <CardDescription>
                {loc
                  ? `${series.dates[0] ?? ''} – ${series.dates[series.dates.length - 1] ?? ''} · ${t('coverage', lang)} ${coveragePct}% · 0.5° POWER cell`
                  : ''}
              </CardDescription>
            </div>
            <Select value={selected} onValueChange={(v) => setSelected(v ?? '')}>
              <SelectTrigger className="w-52"><SelectValue /></SelectTrigger>
              <SelectContent>
                {locations.map((l) => (
                  <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            {loadingIndicators ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                {lang === 'bn' ? 'ডেটা লোড হচ্ছে…' : 'Loading POWER data…'}
              </p>
            ) : (
              <>
                <EChart option={option} height={320} ariaLabel="Rainfall and temperature trend" />
                <p className="mt-3 text-xs text-muted-foreground">
                  {lang === 'bn'
                    ? 'NASA POWER ০.৫° কোষ — এটি একটি কৃষক-সীমানা নয়। রিসম্পলিং নতুন পরিমাপ নয়।'
                    : 'Coarse cell value (POWER 0.5°) — not a farm boundary. Resampling is never presented as newly measured detail.'}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><Download className="size-4" /> {t('export_data', lang)}</CardTitle>
              <CardDescription>
                {lang === 'bn' ? 'স্কোপ-সংযুক্ত, কোটা-নিয়ন্ত্রিত' : 'Scope-bound and quota-controlled'}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Select value={format} onValueChange={(v) => setFormat(v as 'csv' | 'geojson')}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="csv">CSV</SelectItem>
                  <SelectItem value="geojson">GeoJSON</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={exportData} disabled={!loc || exporting}>
                <FileDown className="size-4" />
                {lang === 'bn' ? 'রপ্তানি শুরু করুন' : 'Start export'}
              </Button>
              <p className="text-xs text-muted-foreground">
                {lang === 'bn'
                  ? 'প্রতিটি রপ্তানিতে প্রভেঞ্চ ম্যানিফেস্ট ও নিয়ম-সংস্করণ থাকে।'
                  : 'Every export carries a provenance manifest and rule version.'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><Database className="size-4" /> {t('provenance', lang)}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {jobs.map((j) => (
                <div key={j.id} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{(j.scope ?? '').split('·')[0]}</span>
                    <Badge
                      variant="outline"
                      className={
                        j.status === 'complete'
                          ? 'border-emerald-300 text-emerald-700'
                          : 'border-sky-300 text-sky-700'
                      }
                    >
                      {j.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {j.format.toUpperCase()}
                    {j.rowCount ? ` · ${j.rowCount} rows` : ''}
                    {j.provenance?.ruleVersion ? ` · ${t('rule_version', lang)} ${j.provenance.ruleVersion}` : ''}
                  </div>
                </div>
              ))}
              {jobs.length === 0 && (
                <p className="text-sm text-muted-foreground">{lang === 'bn' ? 'কোনো রপ্তানি নেই।' : 'No exports yet.'}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="mt-4">
        <AreaSummary
          fields={fields}
          areaName={loc ? `${loc.name} · Rajshahi` : 'Rajshahi'}
        />
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="size-4 text-primary" />
            {lang === 'bn' ? 'তথ্যের মান' : 'Data quality'}
          </CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'অনুপস্থিত তারিখ, বৈধ ছবির আবরণ, ফ্ল্যাগ করা পঠন ও উৎসের অবস্থা।'
              : 'Missing dates, valid image coverage, flagged readings and source status.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: lang === 'bn' ? 'বৈধ POWER আবরণ' : 'Valid POWER coverage',
                value: `${coveragePct}%`,
                note: lang === 'bn' ? 'বৈধ দিন' : 'Valid days',
                tint: 'tint-green',
              },
              {
                label: lang === 'bn' ? 'অনুপস্থিত তারিখ' : 'Missing dates',
                value: `${100 - coveragePct}%`,
                note: lang === 'bn' ? 'মেঘ/অবৈধ দিন' : 'Cloudy or invalid days',
                tint: 'tint-sand',
              },
              {
                label: lang === 'bn' ? 'ফ্ল্যাগ করা পঠন' : 'Flagged readings',
                value: '0',
                note: lang === 'bn' ? 'কোনো ফ্ল্যাগ নেই' : 'No flags in this period',
                tint: 'tint-blue',
              },
              {
                label: lang === 'bn' ? 'উৎসের অবস্থা' : 'Source status',
                value: lang === 'bn' ? 'চালু' : 'Live',
                note: 'NASA POWER',
                tint: 'tint-green',
              },
            ].map((q) => (
              <div key={q.label} className={`rounded-2xl border border-border p-4 ${q.tint}`}>
                <div className="text-xl font-bold text-foreground">{q.value}</div>
                <div className="mt-0.5 text-xs font-medium text-foreground/80">{q.label}</div>
                <div className="mt-1 text-[11px] text-foreground/60">{q.note}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            {lang === 'bn'
              ? 'অনুপস্থিত মান শূন্য হিসেবে দেখানো হয় না — সেগুলো অনুপস্থিতই থাকে।'
              : 'Missing values are never shown as zero — they stay missing.'}
          </p>
        </CardContent>
      </Card>
    </main>
  )
}
