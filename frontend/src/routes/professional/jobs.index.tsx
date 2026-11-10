import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Server, Layers, Database, Cpu } from 'lucide-react'
import { listAnalyses, listExportJobs } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { AnalysisRun, ResearchExportJob } from '#/lib/types'
import { StatusBadge } from '#/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Progress } from '#/components/ui/progress'
import { Separator } from '#/components/ui/separator'

export const Route = createFileRoute('/professional/jobs/')({ component: JobsPage })

export default function JobsPage() {
  const lang = useLocale()
  const [analyses, setAnalyses] = useState<AnalysisRun[]>([])
  const [exports, setExports] = useState<ResearchExportJob[]>([])

  useEffect(() => {
    const load = () => {
      listAnalyses().then(setAnalyses)
      listExportJobs().then(setExports)
    }
    load()
    const iv = setInterval(load, 1500)
    return () => clearInterval(iv)
  }, [])

  const activeAnalyses = analyses.filter((a) => a.status === 'running' || a.status === 'queued')
  const activeExports = exports.filter((e) => e.status === 'running' || e.status === 'queued')
  const completedAnalyses = analyses.filter((a) => a.status === 'complete' || a.status === 'partial')

  const queueStats = [
    { icon: Server, label: lang === 'bn' ? 'সক্রিয় বিশ্লেষণ' : 'Active analyses', value: activeAnalyses.length, active: true },
    { icon: Layers, label: lang === 'bn' ? 'সম্পন্ন' : 'Completed', value: completedAnalyses.length, active: false },
    { icon: Database, label: lang === 'bn' ? 'সক্রিয় রপ্তানি' : 'Active exports', value: activeExports.length, active: true },
    { icon: Cpu, label: lang === 'bn' ? 'ব্যর্থ/বাতিল' : 'Failed/Cancelled', value: analyses.filter((a) => a.status === 'failed' || a.status === 'cancelled').length, active: false },
  ]

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">{t('jobs', lang)}</h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'ব্যাচ-প্রগতি, রপ্তানি ও পুনরুৎপাদনযোগ্যতা — পৃথক কোয় (ইনজেশন, বিশ্লেষণ, রাস্টার, রপ্তানি)।'
            : 'Batch progress, exports and reproducibility — separate queues (ingestion, analysis, raster, export).'}
        </p>
      </header>

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {queueStats.map((s) => (
          <Card key={s.label}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className={'flex size-10 items-center justify-center rounded-lg ' + (s.active ? 'bg-accent' : 'bg-muted')}>
                <s.icon className={'size-5 ' + (s.active ? 'text-primary' : 'text-muted-foreground')} />
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground">{s.value}</div>
                <div className="text-xs text-muted-foreground">{s.label}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'বিশ্লেষণ চাকরি' : 'Analysis jobs'}</CardTitle>
            <CardDescription>
              {lang === 'bn' ? 'দীর্ঘ-সময়ে চলমান কাজ' : 'Long-running work'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {analyses.slice(0, 8).map((a) => (
              <div key={a.id} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{a.id}</span>
                  <StatusBadge status={a.status} />
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{a.ruleVersion}</span>
                  <span>·</span>
                  <span>{a.submittedAt.slice(0, 16).replace('T', ' ')}</span>
                  {(a.status === 'running' || a.status === 'queued') && (
                    <div className="ml-auto w-32">
                      <Progress value={a.progressPct} className="h-1.5" />
                    </div>
                  )}
                </div>
              </div>
            ))}
            {analyses.length === 0 && (
              <p className="text-sm text-muted-foreground">{lang === 'bn' ? 'কোনো চাকরি নেই।' : 'No jobs.'}</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'রপ্তানি চাকরি' : 'Export jobs'}</CardTitle>
            <CardDescription>
              {lang === 'bn' ? 'প্রভেঞ্চ ও কোটা সহ' : 'With provenance and quota'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {exports.map((e) => (
              <div key={e.id} className="flex flex-col gap-1.5 rounded-lg border border-border p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{e.scope.split('·')[0]}</span>
                  <Badge
                    variant="outline"
                    className={
                      e.status === 'complete'
                        ? 'border-emerald-300 text-emerald-700'
                        : 'border-sky-300 text-sky-700'
                    }
                  >
                    {e.status}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  {e.format.toUpperCase()}
                  {e.rowCount ? ` · ${e.rowCount} rows` : ''}
                  {e.provenance ? ` · ${t('rule_version', lang)} ${e.provenance.ruleVersion}` : ''}
                </div>
              </div>
            ))}
            {exports.length === 0 && (
              <p className="text-sm text-muted-foreground">{lang === 'bn' ? 'কোনো রপ্তানি নেই।' : 'No exports.'}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4 border-dashed">
        <CardContent className="p-4 text-sm text-muted-foreground">
          <div className="flex flex-col gap-1">
            <Separator />
            <p>
              {lang === 'bn'
                ? 'স্কেলিং নীতি: ওয়েব-রিকোয়েস্ট ও CPU/মেমরি-ঘন রাস্টার-প্রসেসিং আলাদাভাবে স্কেল করে। প্রদানকারীর হার-সীমা (NASA) স্বয়ংক্রিয়ভাবে দূর হয় না — কোয়-সীমা ও কোয়ালাইড-কোয় (coalesce) ব্যবহার করে একই পাবলিক অ্যাসেটের পুনরাবৃত্ত অনুরোধ একে একে ঐক্য করে।'
                : 'Scaling policy: web requests and CPU/memory-heavy raster processing scale separately. Provider rate limits (NASA) are not removed by autoscaling — bounded concurrency and request coalescing collapse duplicate public-asset fetches into one.'}
            </p>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
