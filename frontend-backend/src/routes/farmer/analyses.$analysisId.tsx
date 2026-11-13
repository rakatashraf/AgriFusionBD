import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { ArrowLeft, Scale, AlertTriangle, FileText, AlertCircle, Leaf } from 'lucide-react'
import { getAnalysis, getField, listCrops, createCase } from '#/lib/api'
import { isDemoMode } from '#/lib/demo'
import { getSeasonReport, getForecast } from '#/lib/advisory'
import SeasonReport from '#/components/advisory/SeasonReport'
import ForecastCard from '#/components/advisory/ForecastCard'
import { toast } from 'sonner'
import { useLocale, t } from '#/lib/i18n'
import type { AnalysisRun, Crop, Field } from '#/lib/types'
import { StatusBadge } from '#/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Separator } from '#/components/ui/separator'
import { Alert, AlertDescription, AlertTitle } from '#/components/ui/alert'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '#/components/ui/table'

/** Shape the API actually returns for a plan. */
interface ApiPlan {
  name: string
  crops: string[]
  score: number
  feasible: 'feasible' | 'constrained' | 'infeasible'
  isBaseline: boolean
}

/** The API and the demo seed use two different plan shapes. Normalise both to
 *  the display shape so neither can crash the page. */
function normalizePlan(raw: unknown, index: number): ApiPlan {
  const p = (raw ?? {}) as Partial<ApiPlan> & {
    cropIds?: string[]
    weightedScore?: number
    feasibility?: ApiPlan['feasible']
    kind?: string
  }
  const isBaseline = p.isBaseline ?? p.kind === 'baseline'
  return {
    name: p.name ?? (isBaseline ? 'Baseline' : `Alternative ${index}`),
    crops: p.crops ?? p.cropIds ?? [],
    score: p.score ?? p.weightedScore ?? 0,
    feasible: p.feasible ?? p.feasibility ?? 'constrained',
    isBaseline,
  }
}

/** Shape the API returns for evidence. */
interface ApiEvidence {
  hls_scenes?: number
  power_cell?: string
  missing_data?: string[]
  rule_version?: string
  hls_coverage_pct?: number
}

export const Route = createFileRoute('/farmer/analyses/$analysisId')({ component: AnalysisDetail })

const FEASIBLE_CLS: Record<string, string> = {
  feasible: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  constrained: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  infeasible: 'border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
}

function FeasibleBadge({ status }: { status: string }) {
  const cls = FEASIBLE_CLS[status] ?? FEASIBLE_CLS.constrained
  const label: Record<string, { en: string; bn: string }> = {
    feasible: { en: 'Feasible', bn: 'সম্ভব' },
    constrained: { en: 'Constrained', bn: 'সীমাবদ্ধ' },
    infeasible: { en: 'Infeasible', bn: 'অসম্ভব' },
  }
  const l = label[status] ?? label.constrained
  const lang = useLocale()
  return <Badge variant="outline" className={cls}>{l[lang]}</Badge>
}

function AnalysisDetail() {
  const { analysisId } = Route.useParams()
  const lang = useLocale()
  const navigate = useNavigate()
  const [run, setRun] = useState<AnalysisRun | null>(null)
  const [crops, setCrops] = useState<Crop[]>([])
  const [field, setField] = useState<Field | null>(null)

  const TERMINAL = new Set(['complete', 'partial', 'failed', 'cancelled'])

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let stopped = false

    listCrops().then(setCrops).catch(() => setCrops([]))

    const load = async () => {
      try {
        const r = await getAnalysis(analysisId)
        if (stopped) return
        setRun(r ?? null)
        if (r?.fieldId) {
          getField(r.fieldId).then(setField).catch(() => setField(null))
        }
        if (r && (TERMINAL.has(r.status) || isDemoMode())) return
        timer = setTimeout(load, 1500)
      } catch (err) {
        if (stopped) return
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

  // Normalise the API/demo plan shapes into the display shape.
  const plans = (run.plans ?? []).map(normalizePlan)
  const evidence = (run.evidence ?? {}) as unknown as ApiEvidence
  const missingData: string[] = run.missingData ?? evidence.missing_data ?? []

  const cropName = (id: string) => crops.find((c) => c.id === id)?.name ?? id

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <button
            onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: undefined } })}
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
            {t('rule_version', lang)} {run.ruleVersion}
            {evidence.rule_version && evidence.rule_version !== run.ruleVersion && (
              <> · {evidence.rule_version}</>
            )}
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
                  subject: lang === 'bn' ? 'ফসল চক্র তুলনা' : 'Rotation comparison',
                  body: lang === 'bn'
                    ? 'অনুগ্রহ করে এই তুলনা পর্যালোচনা করুন।'
                    : 'Please review this rotation comparison.',
                })
                toast.success(lang === 'bn' ? 'অফিসার কেস খোলা হয়েছে' : 'Officer case opened')
              } catch (err) {
                toast.error(err instanceof Error ? err.message : String(err))
              }
            }}
          >
            {lang === 'bn' ? 'অফিসার কেস খুলুন' : 'Open officer case'}
          </Button>
        </div>
      </div>

      {/* Warnings */}
      {(run.warnings ?? []).length > 0 && (
        <Alert variant="default" className="mb-4 border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
          <AlertTriangle className="size-4" />
          <AlertTitle>{lang === 'bn' ? 'সতর্কতা' : 'Warnings'}</AlertTitle>
          <AlertDescription>
            {(run.warnings ?? []).map((w, i) => <div key={i}>{w}</div>)}
          </AlertDescription>
        </Alert>
      )}

      {/* Season report */}
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

      {/* Comparison table */}
      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base"><Scale className="size-4" /> {lang === 'bn' ? 'ট্রেড-অফ তুলনা' : 'Trade-off comparison'}</CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'প্রতিটি পরিকল্পনার স্কোর ও সম্ভাব্যতা।'
              : 'Score and feasibility for each rotation plan.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{lang === 'bn' ? 'পরিকল্পনা' : 'Plan'}</TableHead>
                <TableHead>{lang === 'bn' ? 'ফসল' : 'Crops'}</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead className="text-right">{lang === 'bn' ? 'সম্ভাব্যতা' : 'Feasibility'}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.map((p, i) => (
                <TableRow key={i} className={p.isBaseline ? 'bg-primary/5' : ''}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {p.isBaseline && <Leaf className="size-3.5 text-primary" />}
                      {p.name}
                      {p.isBaseline && (
                        <Badge variant="outline" className="text-[10px]">
                          {t('baseline', lang)}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {p.crops.map((c) => cropName(c)).join(' → ')}
                  </TableCell>
                  <TableCell className="text-right font-semibold">{p.score.toFixed(2)}</TableCell>
                  <TableCell className="text-right">
                    <FeasibleBadge status={p.feasible} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Plan cards */}
      <div className="grid gap-4 lg:grid-cols-3">
        {plans.map((p, i) => (
          <Card key={i} className={p.isBaseline ? 'border-primary/40' : ''}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{p.name}</CardTitle>
                <FeasibleBadge status={p.feasible} />
              </div>
              <CardDescription>
                {p.isBaseline
                  ? (lang === 'bn' ? 'বর্তমান চক্র' : 'Current rotation')
                  : (lang === 'bn' ? `অ্যালেটনেটিভ ${i}` : `Alternative ${i}`)}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {/* Crop sequence */}
              <div className="flex flex-wrap items-center gap-1">
                {p.crops.map((cid, j) => (
                  <div key={j} className="flex items-center gap-1">
                    {j > 0 && <span className="text-muted-foreground">→</span>}
                    <Badge variant="outline" className="font-normal">{cropName(cid)}</Badge>
                  </div>
                ))}
              </div>
              <Separator />
              {/* Score */}
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{lang === 'bn' ? 'স্কোর' : 'Score'}</span>
                <span className="font-semibold">{p.score.toFixed(2)}</span>
              </div>
              {/* Feasibility detail */}
              {p.feasible !== 'feasible' && (
                <Alert className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
                  <AlertCircle className="size-4" />
                  <AlertDescription className="text-xs">
                    {p.feasible === 'constrained'
                      ? (lang === 'bn'
                        ? 'এই পরিকল্পনাটি কিছু সীমাবদ্ধতার মধ্যে রয়েছে।'
                        : 'This plan has some constraints.')
                      : (lang === 'bn'
                        ? 'এই পরিকল্পনাটি বর্তমান অবস্থায় বাস্তবসম্মত নয়।'
                        : 'This plan is not currently feasible.')}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Evidence */}
      {evidence && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><FileText className="size-4" /> {t('evidence', lang)}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {/* Data sources */}
            <div>
              <p className="mb-2 text-sm font-medium">{lang === 'bn' ? 'ডেটা উৎস' : 'Data sources'}</p>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium">USGS HLS (Harmonized Landsat & Sentinel-2)</div>
                    <div className="text-xs text-muted-foreground">
                      NDVI · {evidence.hls_scenes ?? '—'} scenes · {evidence.hls_coverage_pct ?? '—'}% coverage
                    </div>
                  </div>
                  <Badge variant="outline">HLS</Badge>
                </div>
                <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium">NASA POWER (Prediction of Worldwide Energy Resources)</div>
                    <div className="text-xs text-muted-foreground">
                      {lang === 'bn' ? 'বৃষ্টি, তাপমাত্রা, আর্দ্রতা, সূর্যের বিকিরণ' : 'Rainfall, temperature, humidity, solar radiation'}
                      {evidence.power_cell ? ` · ${evidence.power_cell}` : ''}
                    </div>
                  </div>
                  <Badge variant="outline">POWER</Badge>
                </div>
              </div>
            </div>

            <Separator />

            {/* Missing data */}
            <div>
              <p className="mb-2 text-sm font-medium">{lang === 'bn' ? 'অনুপস্থিত ডেটা' : 'Missing data'}</p>
              {missingData.length === 0 ? (
                <p className="text-sm text-muted-foreground">—</p>
              ) : (
                <ul className="flex flex-col gap-1 text-sm text-amber-700 dark:text-amber-300">
                  {missingData.map((m, i) => (
                    <li key={i} className="flex items-start gap-1">
                      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> {m}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <Separator />

            {/* Disclaimer */}
            <Alert className="border-border bg-muted/40 text-muted-foreground">
              <AlertDescription className="text-xs">
                {lang === 'bn'
                  ? 'এই তুলনাটি সিদ্ধান্তের সহায়তার জন্য; ফলন, লাভ বা মাটির স্বাস্থ্যের গ্যারান্টি দেয় না।'
                  : 'This comparison supports decisions; it does not guarantee yield, profit, or soil-health improvement.'}
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      )}
    </main>
  )
}
