import { CloudSun, CloudRain, Sun, Cloud, Droplets, Thermometer } from 'lucide-react'
import type { SeasonForecast, LangText } from '#/lib/advisory'
import { useLocale } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'

function txt(t: LangText, lang: 'en' | 'bn'): string {
  return lang === 'bn' ? t.bn : t.en
}

function ConditionIcon({ condition }: { condition: string }) {
  if (condition.includes('Rain') || condition.includes('বৃষ্টি')) return <CloudRain className="size-4 text-sky-600" />
  if (condition.includes('Sunny') || condition.includes('রোদ')) return <Sun className="size-4 text-amber-500" />
  return <CloudSun className="size-4 text-muted-foreground" />
}

export default function ForecastCard({ forecast }: { forecast: SeasonForecast }) {
  const lang = useLocale()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Cloud className="size-4 text-primary" />
          {txt(forecast.season, lang)}
        </CardTitle>
        <CardDescription className="leading-relaxed">{txt(forecast.outlook, lang)}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2 sm:grid-cols-7">
          {forecast.days.map((d) => (
            <div key={d.date} className="rounded-2xl border border-border bg-card p-3">
              <p className="text-xs font-semibold text-foreground">
                {new Date(d.date + 'T00:00:00').toLocaleDateString(lang === 'bn' ? 'bn-BD' : 'en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}
              </p>
              <div className="mt-2 flex items-center gap-1.5">
                <ConditionIcon condition={txt(d.condition, lang)} />
                <span className="text-xs text-muted-foreground">{txt(d.condition, lang)}</span>
              </div>
              <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                <Droplets className="size-3" /> {d.rainMm} mm
              </p>
              <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
                <Thermometer className="size-3" /> {d.tempMaxC}° / {d.tempMinC}°
              </p>
              <p className="mt-2 text-[11px] leading-snug text-foreground">{txt(d.advice, lang)}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
