import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { FlaskConical, Clock, CheckCircle2, AlertTriangle, ArrowRight } from 'lucide-react'
import { listAnalyses, listFields } from '#/lib/api'
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

export default function AnalysesPage() {
  const { fieldId } = Route.useSearch()
  const lang = useLocale()
  const navigate = useNavigate()
  const [analyses, setAnalyses] = useState<AnalysisRun[]>([])
  const [fields, setFields] = useState<Field[]>([])
  const [filter, setFilter] = useState<string>(fieldId ?? '')

  useEffect(() => {
    listFields().then(setFields)
    const load = () => listAnalyses(filter || undefined).then(setAnalyses)
    load()
    const iv = setInterval(load, 1500)
    return () => clearInterval(iv)
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
          <Button size="sm" onClick={() => navigate({ to: '/farmer/analyses/new' })}>
            + {lang === 'bn' ? 'নতুন' : 'New'}
          </Button>
        </div>
      </header>

      <div className="flex flex-col gap-3">
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
                    {a.request.seasonStart} → {a.request.seasonEnd} · {t('rule_version', lang)} {a.ruleVersion}
                  </CardDescription>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={a.status} />
                {(a.status === 'complete' || a.status === 'partial') && (
                  <Button size="sm" variant="outline" onClick={() => navigate({ to: `/farmer/analyses/${a.id}` })}>
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

        {analyses.length === 0 && (
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
