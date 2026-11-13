import { AlertTriangle, Info, Droplets, Satellite, Leaf, Scale, ShieldCheck, CloudOff, FlaskConical } from 'lucide-react'
import type { SeasonReport, LangText } from '#/lib/advisory'
import { rotationPhoto } from '#/lib/images'
import { useLocale } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'

function txt(t: LangText, lang: 'en' | 'bn'): string {
  return lang === 'bn' ? t.bn : t.en
}

const CONFIDENCE: Record<string, { en: string; bn: string; cls: string }> = {
  high: { en: 'High confidence', bn: 'উচ্চ আস্থা', cls: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200' },
  medium: { en: 'Medium confidence', bn: 'মাঝারি আস্থা', cls: 'border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-200' },
  low: { en: 'Low confidence', bn: 'কম আস্থা', cls: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200' },
}

const WATER_NEED: Record<string, { en: string; bn: string }> = {
  low: { en: 'Water need: low', bn: 'পানির চাহিদা: কম' },
  medium: { en: 'Water need: medium', bn: 'পানির চাহিদা: মাঝারি' },
  high: { en: 'Water need: high', bn: 'পানির চাহিদা: বেশি' },
}

const WARN_CLS: Record<string, string> = {
  info: 'tint-blue',
  warn: 'tint-sand',
  danger: 'tint-red',
}

export default function SeasonReport({ report, crops }: { report: SeasonReport; crops?: { current?: string[]; recent?: string[] } }) {
  const lang = useLocale()
  const conf = CONFIDENCE[report.confidence]

  return (
    <div className="flex flex-col gap-4">
      {/* Header: field, season, date, confidence */}
      <Card className="forest-panel border-0">
        <CardContent className="flex flex-col gap-2 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="forest-eyebrow text-xs font-bold uppercase tracking-widest">
              {txt(report.season, lang)} · {report.date}
            </p>
            <h2 className="forest-title mt-1 text-2xl font-bold">{report.fieldName}</h2>
            <p className="forest-copy mt-1 text-sm">{txt(report.currentSituation, lang)}</p>
          </div>
          <Badge variant="outline" className={conf.cls + ' shrink-0'}>{conf[lang]}</Badge>
        </CardContent>
      </Card>

      {/* Crop cycles — what the farmer actually grows, so the advice below
       *  is read against the real current and recent crops. */}
      {(crops?.current?.length || crops?.recent?.length) ? (
        <Card>
          <CardContent className="flex flex-col gap-1.5 p-4 text-sm sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6">
            {crops.current?.length ? (
              <p className="text-foreground">
                <span className="font-semibold">{lang === 'bn' ? 'বর্তমান চক্র: ' : 'Current cycle: '}</span>
                {crops.current.join(', ')}
              </p>
            ) : null}
            {crops.recent?.length ? (
              <p className="text-muted-foreground">
                <span className="font-semibold">{lang === 'bn' ? 'সাম্প্রতিক চক্র: ' : 'Recent cycle: '}</span>
                {crops.recent.join(', ')}
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground">
              {lang === 'bn'
                ? 'নিচের পরামর্শ এই ফসলগুলোর আলোকে দেওয়া।'
                : 'The advice below is read against these crops.'}
            </p>
          </CardContent>
        </Card>
      ) : null}

      {/* Warnings */}
      {report.warnings?.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {report.warnings.map((w, i) => (
            <Card key={i} className={WARN_CLS[w.level]}>
              <CardContent className="flex items-start gap-3 p-4">
                <AlertTriangle className="mt-0.5 size-5 shrink-0 text-foreground" />
                <p className="text-sm font-medium leading-relaxed text-foreground">{txt(w.text, lang)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* What the numbers mean + satellite evidence */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Info className="size-4 text-primary" />
              {lang === 'bn' ? 'সংখ্যাগুলোর মানে কী' : 'What the numbers mean'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-foreground">{txt(report.numbersMean, lang)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Satellite className="size-4 text-primary" />
              {lang === 'bn' ? 'উপগ্রহ থেকে প্রমাণ' : 'Evidence from satellites'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-foreground">{txt(report.evidence, lang)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Irrigation decision + next step */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className={report.irrigationLevel === 'ok' ? 'tint-green' : report.irrigationLevel === 'watch' ? 'tint-sand' : 'tint-red'}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Droplets className="size-4 text-primary" />
              {lang === 'bn' ? 'সেচ সিদ্ধান্ত' : 'Irrigation decision'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium leading-relaxed text-foreground">{txt(report.irrigationDecision, lang)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CloudOff className="size-4 text-primary" />
              {lang === 'bn' ? 'পরবর্তী পদক্ষেপ' : 'Next step'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-foreground">{txt(report.nextStep, lang)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Crop rotation suggestions */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Scale className="size-5 text-primary" />
          <h3 className="text-lg font-semibold text-foreground">
            {lang === 'bn' ? 'ফসল চক্রের পরামর্শ' : 'Crop rotation suggestions'}
          </h3>
          <span className="text-xs text-muted-foreground">
            {lang === 'bn' ? '(প্রার্থী মাত্র — স্থানীয়ভাবে যাচাই করুন)' : '(candidate only — verify locally)'}
          </span>
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          {(report.rotations ?? []).map((r, i) => (
            <Card key={i} className="tint-green">
              <CardHeader>
                <div className="flex items-start gap-3">
                  <img
                    src={rotationPhoto(i)}
                    alt={txt(r.title, lang)}
                    loading="lazy"
                    className="h-[78px] w-[92px] shrink-0 rounded-[14px] object-cover"
                  />
                  <div className="min-w-0">
                    <CardTitle className="text-base leading-snug">{txt(r.title, lang)}</CardTitle>
                    <CardDescription>
                      {WATER_NEED[r.waterNeed][lang]} · {lang === 'bn' ? 'উপযুক্ততা' : 'Suitability'}{' '}
                      {(r.suitability * 100).toFixed(0)} / 100
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                <p className="leading-relaxed text-foreground">
                  <span className="font-semibold">{lang === 'bn' ? 'কেন: ' : 'Why: '}</span>
                  {txt(r.why, lang)}
                </p>
                <p className="leading-relaxed text-foreground">
                  <span className="font-semibold">{lang === 'bn' ? 'ঝুঁকি: ' : 'Risk: '}</span>
                  {txt(r.risk, lang)}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{txt(report.rotationNote, lang)}</p>
      </div>

      {/* Note, confidence, soil care */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-primary" />
              {lang === 'bn' ? 'মনে রাখবেন' : 'Please note'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-foreground">{txt(report.note, lang)}</p>
          </CardContent>
        </Card>
        <Card className="tint-sand">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Leaf className="size-4 text-primary" />
              {lang === 'bn' ? 'আস্থা' : 'Confidence'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-foreground">{conf[lang]}</p>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{txt(report.confidenceReason, lang)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FlaskConical className="size-4 text-primary" />
              {lang === 'bn' ? 'মাটি ও পরিচর্যা' : 'Soil and care'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-foreground">{txt(report.soilCare, lang)}</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
