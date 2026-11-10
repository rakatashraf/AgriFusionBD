import { Bot, FlaskConical, Droplets, Thermometer, Camera, Bug, ShieldAlert } from 'lucide-react'
import type { RoverCheck, LangText } from '#/lib/advisory'
import { useLocale } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Progress } from '#/components/ui/progress'

function txt(t: LangText, lang: 'en' | 'bn'): string {
  return lang === 'bn' ? t.bn : t.en
}

const SEV_CLS: Record<string, string> = {
  low: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  medium: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  high: 'border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
}

export default function RoverCheckCard({ check }: { check: RoverCheck }) {
  const lang = useLocale()
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-lg bg-accent">
              <Bot className="size-6 text-primary" />
            </div>
            <div>
              <CardTitle className="text-base">{check.fieldName}</CardTitle>
              <CardDescription>
                {check.deviceName} · {new Date(check.checkedAt).toISOString().slice(0, 10)}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline">
            {lang === 'bn' ? 'ফসলের স্বাস্থ্য' : 'Crop health'} {Math.round(check.cropHealth.score * 100)}%
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {/* Nutrition + moisture + temperature */}
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <FlaskConical className="size-3.5" /> {lang === 'bn' ? 'পুষ্টি (N / P / K)' : 'Nutrition (N / P / K)'}
            </p>
            <p className="mt-1.5 font-mono text-sm font-semibold text-foreground">
              {check.nutrition.nPpm} / {check.nutrition.pPpm} / {check.nutrition.kPpm} ppm
            </p>
            <p className="mt-1 text-xs leading-snug text-muted-foreground">{txt(check.nutrition.level, lang)}</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Droplets className="size-3.5" /> {lang === 'bn' ? 'মাটির আর্দ্রতা' : 'Soil moisture'}
            </p>
            <p className="mt-1.5 text-sm font-semibold text-foreground">{check.moisturePct}%</p>
            <Progress value={check.moisturePct} className="mt-2 h-1.5" />
          </div>
          <div className="rounded-2xl border border-border bg-card p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Thermometer className="size-3.5" /> {lang === 'bn' ? 'তাপমাত্রা' : 'Temperature'}
            </p>
            <p className="mt-1.5 text-sm font-semibold text-foreground">{check.tempC.toFixed(1)}°C</p>
            <p className="mt-1 text-xs text-muted-foreground">{lang === 'bn' ? 'মাটির উপরিভাগ' : 'Soil surface'}</p>
          </div>
        </div>

        {/* Crop health via camera */}
        <div className="rounded-2xl border border-border bg-muted/30 p-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
            <Camera className="size-3.5" /> {lang === 'bn' ? 'ক্যামেরায় ফসলের স্বাস্থ্য' : 'Crop health (camera)'}
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-foreground">{txt(check.cropHealth.note, lang)}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{txt(check.cropHealth.cameraNote, lang)}</p>
        </div>

        {/* Threats (insects/bugs) */}
        {check.threats.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Bug className="size-3.5" /> {lang === 'bn' ? 'ক্ষতিকর পোকা / হুমকি' : 'Harmful insects / threats'}
            </p>
            <div className="flex flex-col gap-2">
              {check.threats.map((th, i) => (
                <div key={i} className="flex items-start justify-between gap-2 rounded-lg border border-border px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-foreground">{txt(th.type, lang)}</p>
                    <p className="text-xs leading-snug text-muted-foreground">{txt(th.note, lang)}</p>
                  </div>
                  <Badge variant="outline" className={SEV_CLS[th.severity]}>{th.severity}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Diseases */}
        {check.diseases.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <ShieldAlert className="size-3.5" /> {lang === 'bn' ? 'ফসলের রোগ' : 'Crop diseases'}
            </p>
            <div className="flex flex-col gap-2">
              {check.diseases.map((d, i) => (
                <div key={i} className="flex items-start justify-between gap-2 rounded-lg border border-border px-3 py-2">
                  <div>
                    <p className="text-sm font-medium text-foreground">{txt(d.name, lang)}</p>
                    <p className="text-xs leading-snug text-muted-foreground">{txt(d.note, lang)}</p>
                  </div>
                  <Badge variant="outline" className={SEV_CLS[d.severity]}>{d.severity}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}
        {check.threats.length === 0 && check.diseases.length === 0 && (
          <p className="text-sm text-emerald-700 dark:text-emerald-300">
            {lang === 'bn' ? 'কোনো ক্ষতিকর পোকা বা রোগ পাওয়া যায়নি।' : 'No harmful insects or diseases found.'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
