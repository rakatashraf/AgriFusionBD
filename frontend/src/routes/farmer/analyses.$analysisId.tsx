import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { ArrowLeft, Scale, Info, AlertTriangle, FileText } from 'lucide-react'
import { getAnalysis, getField, listCrops, createCase } from '#/lib/api'
import { getSeasonReport, getForecast } from '#/lib/advisory'
import SeasonReport from '#/components/advisory/SeasonReport'
import ForecastCard from '#/components/advisory/ForecastCard'
import { toast } from 'sonner'
import { useLocale, t } from '#/lib/i18n'
import type { AnalysisRun, Crop, Field, MetricValue, RotationPlan } from '#/lib/types'
import { StatusBadge } from '#/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Progress } from '#/components/ui/progress'
import { Separator } from '#/components/ui/separator'
import { Alert, AlertDescription, AlertTitle } from '#/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#/components/ui/table'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const Route = createFileRoute('/farmer/analyses/$analysisId')({ component: AnalysisDetail })

function Timeline({ plan, crops }: { plan: RotationPlan; crops: Crop[] }) {
  const name = (id?: string) => crops.find((c) => c.id === id)?.name
  return (
    <div className="flex flex-wrap gap-1" aria-label="Crop timeline by month">
      {plan.timeline.map((m) => (
        <div
          key={m.month}
          title={`${MONTHS[m.month - 1]}: ${name(m.cropId) ?? 'Fallow'}`}
          className={
            'flex h-7 w-9 items-center justify-center rounded text-[9px] font-medium ' +
            (m.cropId
              ? 'bg-primary/15 text-primary'
              : 'bg-muted text-muted-foreground/70')
          }
        >
          {name(m.cropId)?.slice(0, 3) ?? '—'}
        </div>
      ))}
    </div>
  )
}

export default function AnalysisDetail() {
  const { analysisId } = Route.useParams()
  const lang = useLocale()
  const navigate = useNavigate()
  const [run, setRun] = useState<AnalysisRun | null>(null)
  const [crops, setCrops] = useState<Crop[]>([])
  const [field, setField] = useState<Field | null>(null)

  // The field's crop cycles ground the season report below.
  useEffect(() => {
    if (!run?.fieldId) return
    getField(run.fieldId).then(setField).catch(() => setField(null))
  }, [run?.fieldId])

  const TERMINAL = new Set(['complete', 'partial', 'failed', 'cancelled'])

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false

    listCrops().then(setCrops)

    const load = async () => {
      try {
        const r = await getAnalysis(analysisId)
        if (stopped) return
        setRun(r ?? null)
        if (r && TERMINAL.has(r.status)) return // stop polling on terminal state
        timer = setTimeout(load, 1500)
      } catch (err) {
        if (stopped) return
        // Surface the error but don't spin forever — retry once more slowly.
        console.error('analysis poll failed', err)
        timer = setTimeout(load, 4000)
      }
    }
    load()

    return () => {
      stopped = true
      if (timer) clearTimeout(timer)
    }
  }, [analysisId])

  if (!run) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-8">
        <p className="mt-8 text-muted-foreground">Loading analysis…</p>
      </main>
    )
  }

  const metricKeys: Array<MetricValue['key']> = [
    'waterEfficiency', 'heatResilience', 'soilCover', 'rotationDiversity', 'economics',
  ]
  const best = (key: MetricValue['key']) => {
    const m = run.plans?.map((p) => p.metrics.find((x) => x.key === key)?.score ?? 0) ?? []
    return Math.max(...m)
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <button
            onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: '' } as never })}
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" /> {t('analyses', lang)}
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-foreground">
              {lang === 'bn' ? 'ফসল চক্র তুলনা' : 'Rotation comparison'}
            </h1>
            <StatusBadge status={run.status} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {run.request.seasonStart} → {run.request.seasonEnd} · {t('rule_version', lang)} {run.ruleVersion}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              try {
                await createCase({
                  fieldId: run.fieldId,
                  subject: `${lang === 'bn' ? 'ফসল চক্র তুলনা' : 'Rotation comparison'} — ${run.request.seasonStart}→${run.request.seasonEnd}`,
                  body: lang === 'bn'
                    ? 'অনুগ্রহ করে এই তুলনা পর্যালোচনা করুন। বিস্তারিত প্রমাণ ও ওজনসহ।'
                    : 'Please review this comparison. Includes evidence and weights.',
                })
                toast.success(lang === 'bn' ? 'অফিসার কেস খোলা হয়েছে' : 'Officer case opened')
              } catch (err) {
                toast.error(err instanceof Error ? err.message : String(err))
              }
            }}
          >
            {lang === 'bn' ? 'অফিসার কেস খুলুন' : 'Open officer case'}
          </Button>
          <Button size="sm">{lang === 'bn' ? 'পরিকল্পনা নথিভুক্ত করুন' : 'Record plan'}</Button>
        </div>
      </div>

      {(run.warnings ?? []).length > 0 && (
        <Alert variant="default" className="mb-4 border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          <AlertTriangle className="size-4" />
          <AlertTitle>{lang === 'bn' ? 'সতর্কতা' : 'Warnings'}</AlertTitle>
          <AlertDescription>
            {(run.warnings ?? []).map((w, i) => <div key={i}>{w}</div>)}
          </AlertDescription>
        </Alert>
      )}

      {/* Season report — the model-training advisory for this field, in cards.
          Same content a farmer gets by SMS when they cannot check the site. */}
      {(() => {
        const report = getSeasonReport(run.fieldId)
        const forecast = getForecast(run.fieldId)
        if (!report && !forecast) return null
        return (
          <div className="mb-6 flex flex-col gap-4">
            {report && <SeasonReport report={report} crops={{ current: field?.currentCycleCrops, recent: field?.recentCycleCrops }} />}
            {forecast && <ForecastCard forecast={forecast} />}
          </div>
        )
      })()}

      {/* Trade-off matrix */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Scale className="size-4" /> {lang === 'bn' ? 'ট্রেড-অফ তুলনা' : 'Trade-off comparison'}</CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'প্রতিটি মাপডালিতে সেরা মান সবুজ চিহ্নিত। ওজন আপনার অগ্রাধিকার অনুযায়ী।'
              : 'Best value per metric is highlighted. Weights follow your selected priorities.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{lang === 'bn' ? 'মাপডালি' : 'Metric'}</TableHead>
                {run.plans?.map((p) => (
                  <TableHead key={p.id} className="text-right">
                    <span className={p.kind === 'baseline' ? 'font-semibold' : ''}>
                      {p.kind === 'baseline' ? t('baseline', lang) : `${t('alternative', lang)} ${run.plans!.indexOf(p)}`}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {metricKeys.map((key) => {
                const label = run.plans?.[0]?.metrics.find((m) => m.key === key)?.label ?? key
                const target = best(key)
                return (
                  <TableRow key={key}>
                    <TableCell className="font-medium">{label}</TableCell>
                    {run.plans?.map((p) => {
                      const m = p.metrics.find((x) => x.key === key)
                      return (
                        <TableCell key={p.id} className="text-right">
                          <div className={'inline-flex items-center gap-1 ' + (m && m.score === target ? 'font-semibold text-emerald-700 dark:text-emerald-300' : 'text-foreground')}>
                            {m && m.score === target && '★'} {m ? m.score.toFixed(2) : '—'}
                          </div>
                          <div className="text-[11px] text-muted-foreground">{m?.rawValue}</div>
                        </TableCell>
                      )
                    })}
                  </TableRow>
                )
              })}
              <TableRow className="border-t-2">
                <TableCell className="font-semibold">{lang === 'bn' ? 'ওজনযুক্ত স্কোর' : 'Weighted score'}</TableCell>
                {run.plans?.map((p) => (
                  <TableCell key={p.id} className="text-right font-semibold">{p.weightedScore.toFixed(2)}</TableCell>
                ))}
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Plans */}
      <div className="grid gap-4 lg:grid-cols-3">
        {run.plans?.map((p) => (
          <Card key={p.id} className={p.kind === 'baseline' ? 'border-primary/40' : ''}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {p.kind === 'baseline' ? t('baseline', lang) : `${t('alternative', lang)} ${run.plans!.indexOf(p)}`}
                </CardTitle>
                <StatusBadge status={p.feasibility} />
              </div>
              <CardDescription>
                {p.cropIds.map((id) => crops.find((c) => c.id === id)?.name).join(' → ')}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Timeline plan={p} crops={crops} />
              <Separator />
              <div className="flex flex-col gap-1.5">
                {p.metrics.map((m) => (
                  <div key={m.key}>
                    <div className="mb-0.5 flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">{m.label}</span>
                      <span className="font-medium">{m.score.toFixed(2)}</span>
                    </div>
                    <Progress value={m.score * 100} className="h-1.5" />
                  </div>
                ))}
              </div>
              <Separator />
              <div className="text-xs text-muted-foreground">
                {p.reasons.map((r, i) => <div key={i}>• {r}</div>)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Evidence */}
      {run.evidence && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><FileText className="size-4" /> {t('evidence', lang)}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-medium">{t('assumptions', lang)}</p>
              <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
                {run.evidence.assumptions.map((a, i) => <li key={i}>• {a}</li>)}
              </ul>
              <Separator className="my-3" />
              <p className="mb-2 text-sm font-medium">{t('missing_data', lang)}</p>
              {run.evidence.missingData.length === 0 ? (
                <p className="text-sm text-muted-foreground">—</p>
              ) : (
                <ul className="flex flex-col gap-1 text-sm text-amber-700 dark:text-amber-300">
                  {run.evidence.missingData.map((a, i) => <li key={i}>• {a}</li>)}
                </ul>
              )}
            </div>
            <div>
              <p className="mb-2 text-sm font-medium">Data sources</p>
              <div className="flex flex-col gap-2">
                {run.evidence.assets.map((a) => (
                  <div key={a.id} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                    <div>
                      <div className="font-medium">{a.provider} · {a.product}</div>
                      <div className="text-xs text-muted-foreground">
                        {a.validFrom} → {a.validTo} · {a.spatialRes} · {t('coverage', lang)} {a.coveragePct}%
                      </div>
                    </div>
                    <Badge variant="outline">{a.version}</Badge>
                  </div>
                ))}
              </div>
              <Alert className="mt-3 border-border bg-muted/40 text-muted-foreground">
                <Info className="size-4" />
                <AlertDescription className="text-xs">
                  {t('disclaimer', lang)}
                </AlertDescription>
              </Alert>
            </div>
          </CardContent>
        </Card>
      )}
    </main>
  )
}
