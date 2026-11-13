import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { FlaskConical, Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react'
import { listAnalyses, listFields, ApiError } from '#/lib/api'
import { isDemoMode } from '#/lib/demo'
import { useLocale, t } from '#/lib/i18n'
import type { AnalysisRun, Field } from '#/lib/types'
import { StatusBadge } from '#/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Button } from '#/components/ui/button'
import { Progress } from '#/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '#/components/ui/select'

export const Route = createFileRoute('/farmer/analyses/')({
  component: AnalysesPage,
  validateSearch: (s: Record<string, unknown>) => ({
    fieldId: (s.fieldId as string) || undefined,
  }),
})

function AnalysesPage() {
  const { fieldId } = Route.useSearch()
  const lang = useLocale()
  const navigate = useNavigate()
  const [analyses, setAnalyses] = useState<AnalysisRun[]>([])
  const [fields, setFields] = useState<Field[]>([])
  const [filter, setFilter] = useState<string>(fieldId ?? '')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    listFields().then((v) => { if (!cancelled) setFields(v) }).catch(() => {})

    const load = async () => {
      try {
        const rows = await listAnalyses(filter || undefined)
        if (cancelled) return
        setAnalyses(rows)
        // Only poll while something is still running; terminal rows never
        // change on their own, so an unconditional interval just churns.
        // Demo runs are static snapshots — never poll them.
        if (!isDemoMode() && rows.some((a) => a.status === 'queued' || a.status === 'running')) {
          timer = setTimeout(load, 1500)
        }
      } catch (err) {
        // Retry only transient network failures; auth/validation errors are
        // not going to fix themselves by polling.
        if (!cancelled && err instanceof ApiError && err.status === 0) {
          timer = setTimeout(load, 4000)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [filter])

  const fieldLabel = (id: string) => fields.find((f) => f.id === id)?.name ?? id

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('analyses', lang)}</h1>
          <p className="text-sm text-muted-foreground">
            {lang === 'bn'
              ? 'ফসল চক্রের তুলনা — প্রগতি, আংশিক-ফলাফল ও ব্যর্থতা সব দেখা যায়।'
              : 'Rotation comparisons — progress, partial results and failures all visible.'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={filter || 'all'} onValueChange={(v) => setFilter((v ?? 'all') === 'all' ? '' : (v ?? ''))}>
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All fields</SelectItem>
              {fields.map((f) => (
                <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={() => navigate({ to: '/farmer/analyses/new', search: { fieldId: undefined } })}>
            + {lang === 'bn' ? 'নতুন' : 'New'}
          </Button>
        </div>
      </header>

      <div className="flex flex-col gap-3">
        {loading && analyses.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              <span className="animate-pulse">{lang === 'bn' ? 'লোড হচ্ছে…' : 'Loading…'}</span>
            </CardContent>
          </Card>
        ) : null}
        {analyses.map((a) => (
          <Card key={a.id} className="transition hover:border-primary/30">
            <CardHeader className="flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-lg bg-accent">
                  {a.status === 'complete' ? (
                    <CheckCircle2 className="size-5 text-emerald-600" />
                  ) : a.status === 'failed' ? (
                    <AlertTriangle className="size-5 text-rose-600" />
                  ) : (
                    <FlaskConical className="size-5 text-primary" />
                  )}
                </div>
                <div>
                  <CardTitle className="text-base">{fieldLabel(a.fieldId)}</CardTitle>
                  <CardDescription>
                    {a.request?.seasonStart && a.request?.seasonEnd
                      ? `${a.request.seasonStart} → ${a.request.seasonEnd} · `
                      : a.submittedAt
                        ? `${a.submittedAt.slice(0, 10)} · `
                        : ''}
                    {t('rule_version', lang)} {a.ruleVersion}
                  </CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={a.status} />
                {(a.status === 'complete' || a.status === 'partial') && (
                  <Button size="sm" variant="outline" onClick={() => navigate({ to: '/farmer/analyses/$analysisId', params: { analysisId: a.id }, search: {} })}>
                    View <ArrowRight className="size-3.5" />
                  </Button>
                )}
              </div>
            </CardHeader>
            {(a.status === 'running' || a.status === 'queued') && (
              <CardContent>
                <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><Clock className="size-3" /> {t(a.status, lang)}</span>
                  <span>{a.progressPct}%</span>
                </div>
                <Progress value={a.progressPct} />
              </CardContent>
            )}
          </Card>
        ))}

        {!loading && analyses.length === 0 && (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              {t('no_results', lang)}
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  )
}
