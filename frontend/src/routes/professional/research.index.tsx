import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Globe2, Download, Database, FileDown } from 'lucide-react'
import { listResearchLocations, listExportJobs, createExportJob, downloadExport, listFields } from '#/lib/api'
import AreaSummary from '#/components/advisory/AreaSummary'
import { useLocale, t } from '#/lib/i18n'
import type { ResearchLocation, ResearchExportJob, Field } from '#/lib/types'
import EChart from '#/components/EChart'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '#/components/ui/select'
import { toast } from 'sonner'

export const Route = createFileRoute('/professional/research/')({ component: ResearchPage })

export default function ResearchPage() {
  const lang = useLocale()
  const [locations, setLocations] = useState<ResearchLocation[]>([])
  const [selected, setSelected] = useState('')
  const [jobs, setJobs] = useState<ResearchExportJob[]>([])
  const [format, setFormat] = useState<'csv' | 'geojson'>('csv')
  const [fields, setFields] = useState<Field[]>([])

  const load = () => {
    listResearchLocations().then((l) => {
      setLocations(l)
      if (l.length && !selected) setSelected(l[0].id)
    })
    listExportJobs().then(setJobs)
    listFields().then(setFields).catch(() => {})
  }
  useEffect(load, [])

  const loc = locations.find((l) => l.id === selected)
  const [exporting, setExporting] = useState(false)

  const option = loc
    ? {
        grid: { left: 48, right: 48, top: 32, bottom: 40 },
        legend: { data: ['NDVI', 'Rainfall (mm)'], bottom: 0 },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: loc.series.map((s) => s.date), axisLabel: { color: '#416166', hideOverlap: true } },
        yAxis: [
          { type: 'value', name: 'NDVI', min: 0, max: 1, axisLabel: { color: '#416166' }, splitLine: { lineStyle: { color: 'rgba(65,97,102,0.15)' } } },
          { type: 'value', name: 'mm', axisLabel: { color: '#416166' }, splitLine: { show: false } },
        ],
        series: [
          { name: 'NDVI', type: 'line', smooth: true, data: loc.series.map((s) => s.ndvi), lineStyle: { color: '#2f6a4a', width: 2 }, itemStyle: { color: '#2f6a4a' }, areaStyle: { opacity: 0.1, color: '#2f6a4a' } },
          { name: 'Rainfall (mm)', type: 'bar', yAxisIndex: 1, data: loc.series.map((s) => s.rainfallMm), itemStyle: { color: 'rgba(50,143,151,0.4)', borderRadius: [3, 3, 0, 0] } },
        ],
      }
    : {}

  async function exportData() {
    if (!loc) return
    setExporting(true)
    try {
      const job = await createExportJob({
        scope: `${loc.name} · ${loc.period} · POWER + HLS`,
        format,
      })
      toast.success(lang === 'bn' ? 'এক্সপোর্ট শুরু হয়েছে' : 'Export started')
      load()

      // Poll until complete, then trigger the real download.
      let attempts = 0
      const maxAttempts = 30 // ~60s at 2s intervals
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
                {loc ? `${loc.period} · ${t('coverage', lang)} ${loc.coveragePct}% · 0.5° POWER cell` : ''}
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
            <EChart option={option} height={320} ariaLabel="NDVI and rainfall trend" />
            <p className="mt-3 text-xs text-muted-foreground">
              {lang === 'bn'
                ? 'সাধারণ-বাস্তব মান (POWER ০.৫° কোষ) — এটি একটি কৃষক-সীমানা নয়। রিসম্পলিং নতুন পরিমাপ নয়।'
                : 'Coarse cell value (POWER 0.5°) — not a farm boundary. Resampling is never presented as newly measured detail.'}
            </p>
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
                    <span className="text-sm font-medium">{j.scope.split('·')[0]}</span>
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
                    {j.provenance ? ` · ${t('rule_version', lang)} ${j.provenance.ruleVersion}` : ''}
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

      {/* Assigned-area summary — every registered field, its condition and
          the next step, so a professional can review the whole area. */}
      <div className="mt-4">
        <AreaSummary
          fields={fields}
          areaName={loc ? `${loc.name} · Rajshahi` : 'Rajshahi'}
        />
      </div>
    </main>
  )
}
