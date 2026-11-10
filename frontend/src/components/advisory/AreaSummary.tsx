import { MapPin, AlertTriangle, ArrowRight } from 'lucide-react'
import { SEASON_REPORTS, type LangText } from '#/lib/advisory'
import { fieldPhoto } from '#/lib/images'
import { useLocale } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'

function txt(t: LangText, lang: 'en' | 'bn'): string {
  return lang === 'bn' ? t.bn : t.en
}

const CONF_CLS: Record<string, string> = {
  high: 'border-emerald-300 text-emerald-700',
  medium: 'border-sky-300 text-sky-700',
  low: 'border-amber-300 text-amber-700',
}

export interface AreaField {
  id: string
  name: string
  areaHa: number
  soilType?: string
  irrigation: string
}

export default function AreaSummary({ fields, areaName }: { fields: AreaField[]; areaName: string }) {
  const lang = useLocale()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MapPin className="size-4 text-primary" />
          {lang === 'bn' ? 'এলাকার সারসংক্ষেপ — প্রতিটি জমি' : 'Area summary — every field'}
        </CardTitle>
        <CardDescription>
          {areaName} · {fields.length} {lang === 'bn' ? 'টি নিবন্ধিত জমি' : 'registered fields'} ·{' '}
          {lang === 'bn'
            ? 'প্রতিটি জমির অবস্থা দেখুন ও প্রয়োজনীয় পদক্ষেপ নিন।'
            : 'Check the condition of every field and take the necessary steps.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {fields.map((f, idx) => {
          const report = SEASON_REPORTS.find((r) => r.fieldId === f.id)
          const topWarning = report?.warnings[0]
          return (
            <div key={f.id} className="flex gap-3 rounded-xl border border-border p-3">
              <img
                src={fieldPhoto(f.name, idx)}
                alt={f.name}
                loading="lazy"
                className="h-20 w-24 shrink-0 rounded-lg object-cover"
              />
              <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-foreground">{f.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {f.areaHa} ha · {f.soilType ?? '—'} · {f.irrigation}
                  </p>
                </div>
                {report && (
                  <Badge variant="outline" className={CONF_CLS[report.confidence]}>
                    {lang === 'bn'
                      ? report.confidence === 'high' ? 'উচ্চ আস্থা' : report.confidence === 'medium' ? 'মাঝারি আস্থা' : 'কম আস্থা'
                      : report.confidence === 'high' ? 'High confidence' : report.confidence === 'medium' ? 'Medium confidence' : 'Low confidence'}
                  </Badge>
                )}
              </div>
              {report && (
                <>
                  <p className="mt-2 text-sm leading-relaxed text-foreground">{txt(report.currentSituation, lang)}</p>
                  {topWarning && (
                    <p className="mt-1.5 flex items-start gap-1.5 text-xs leading-snug text-amber-800 dark:text-amber-200">
                      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
                      {txt(topWarning.text, lang)}
                    </p>
                  )}
                  <p className="mt-1.5 text-xs leading-snug text-muted-foreground">
                    <span className="font-medium text-foreground">{lang === 'bn' ? 'পরবর্তী পদক্ষেপ: ' : 'Next step: '}</span>
                    {txt(report.nextStep, lang)}
                  </p>
                </>
              )}
              {!report && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {lang === 'bn' ? 'এই জমির এখনো কোনো মৌসুমের প্রতিবেদন নেই।' : 'No season report for this field yet.'}
                </p>
              )}
              <div className="mt-3">
                <a
                  href={`/AgriFusionBD/farmer/analyses?fieldId=${f.id}`}
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  {lang === 'bn' ? 'পূর্ণ প্রতিবেদন দেখুন' : 'View full report'}
                  <ArrowRight className="size-3.5" />
                </a>
              </div>
              </div>
            </div>
          )
        })}
        {fields.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {lang === 'bn' ? 'এই এলাকায় কোনো নিবন্ধিত জমি নেই।' : 'No registered fields in this area.'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
