import { MessageSquareText, Phone, Clock } from 'lucide-react'
import { getSmsAlerts, type LangText } from '#/lib/advisory'
import { useLocale } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'

function txt(t: LangText, lang: 'en' | 'bn'): string {
  return lang === 'bn' ? t.bn : t.en
}

export default function SmsPanel() {
  const lang = useLocale()
  const alerts = getSmsAlerts()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquareText className="size-4 text-primary" />
          {lang === 'bn' ? 'ফোনে SMS সতর্কতা' : 'SMS alerts to phones'}
        </CardTitle>
        <CardDescription>
          {lang === 'bn'
            ? 'কৃষক অনলাইনে না থাকলেও পরামর্শ ও সতর্কতা স্বয়ংক্রিয়ভাবে ফোনে পাঠানো হয়। নিচে দেখুন ঠিক কী বার্তা যাবে।'
            : 'When a farmer cannot check the website, advice and warnings are sent automatically to their phone. Below is exactly what would be sent.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="rounded-xl border border-border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
          {lang === 'bn'
            ? 'ডেমো: এই পাতায় কোনো আসল SMS গেটওয়ে যুক্ত নেই। বার্তাগুলো দেখানো হচ্ছে যাতে দর্শক কাজের ধারা বুঝতে পারেন — প্রোডাকশনে এগুলো স্বয়ংক্রিয়ভাবে পাঠানো হবে।'
            : 'Demo: no real SMS gateway is connected on this page. The messages are shown so the audience can see the workflow — in production they would be sent automatically.'}
        </div>
        {alerts.map((a) => (
          <div key={a.id} className="rounded-xl border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-full bg-accent">
                  <Phone className="size-4 text-primary" />
                </span>
                <div>
                  <p className="text-sm font-medium text-foreground">{a.farmerName} · {a.fieldName}</p>
                  <p className="text-xs text-muted-foreground">{a.phone} · {txt(a.trigger, lang)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="size-3" />
                  {new Date(a.sentAt).toISOString().slice(0, 16).replace('T', ' ')}
                </span>
                <Badge variant="outline" className={a.status === 'sent' ? 'border-emerald-300 text-emerald-700' : 'border-sky-300 text-sky-700'}>
                  {a.status === 'sent' ? (lang === 'bn' ? 'পাঠানো হয়েছে' : 'Sent') : (lang === 'bn' ? 'নির্ধারিত' : 'Scheduled')}
                </Badge>
              </div>
            </div>
            <p className="mt-2 rounded-lg bg-muted/50 px-3 py-2 text-sm leading-relaxed text-foreground">
              {txt(a.message, lang)}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
