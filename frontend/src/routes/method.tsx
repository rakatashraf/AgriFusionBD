import { createFileRoute } from '@tanstack/react-router'
import { Info, FlaskConical, Scale, Droplets, Thermometer, Leaf, Coins } from 'lucide-react'
import { useLocale, t } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Separator } from '#/components/ui/separator'

export const Route = createFileRoute('/method')({ component: MethodPage })

const RULE_VERSION = 'v2026.11.0'

function MethodPage() {
  const lang = useLocale()

  const metrics = [
    {
      key: 'waterEfficiency',
      icon: Droplets,
      weight: '0.25',
      desc: lang === 'bn'
        ? 'FAO-56 Penman-Monteith ET₀ এবং USDA-SCS কার্যকর বৃষ্টিপাত ব্যবহার করে ইরিগেশন চাহিদা (mm)। কম = ভালো।'
        : 'Irrigation demand (mm) from FAO-56 Penman-Monteith ET₀ and USDA-SCS effective rainfall. Lower = better.',
    },
    {
      key: 'heatResilience',
      icon: Thermometer,
      weight: '0.15',
      desc: lang === 'bn'
        ? 'ফসলের তাপ-সহনসীমা অনুযায়ী মৌসুমের থ্রেশহোল্ড-উল্লঙ্ঘন দিন। কম = ভালো।'
        : 'Threshold-exceedance days in the season given the crop’s heat tolerance. Lower = better.',
    },
    {
      key: 'soilCover',
      icon: Leaf,
      weight: '0.15',
      desc: lang === 'bn'
        ? 'HLS NDVI (≥ 40% আবরণ) দিয়ে মৌসুমের গড় ক্যানপি-কভার। বেশি = ভালো।'
        : 'Season-average canopy cover from HLS NDVI (≥ 40% coverage floor). Higher = better.',
    },
    {
      key: 'rotationDiversity',
      icon: Scale,
      weight: '0.15',
      desc: lang === 'bn'
        ? 'Tiemann (2015)-অনুসারে ফসল-চক্রের পরিবার-সম্পূরকতা ও ডায়াজোট্রোফ স্কোর।'
        : 'Rotation family-diversity and legume share, per Tiemann (2015).',
    },
    {
      key: 'economics',
      icon: Coins,
      weight: '0.30',
      desc: lang === 'bn'
        ? 'ফসল-ভিত্তিক মার্জিন-রেঞ্জ (মূল্য/খরচ/ফলন-রেঞ্জ) থেকে গড় নট-মার্জিন (BDT/ha)।'
        : 'Mid-point of the net-margin range (price/cost/yield ranges, BDT/ha) across the rotation.',
    },
  ]

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <header className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <FlaskConical className="size-6 text-primary" />
          {lang === 'bn' ? 'পদ্ধতি ও নিয়ম' : 'Method & rules'}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'প্রতিটি তুলনা এই নিয়ম-সংস্করণ এবং প্রকাশিত মাপডালি-সীমানা অনুযায়ী তৈরি।'
            : 'Every comparison is produced under this rule version and published metric bounds.'}
        </p>
      </header>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center justify-between text-base">
            <span>{lang === 'bn' ? 'নিয়ম-সংস্করণ' : 'Rule version'}</span>
            <Badge variant="secondary">{RULE_VERSION}</Badge>
          </CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'একই ইনপুট-স্ন্যাপশট + নিয়ম-সংস্করণ = পুনরুৎপাদনযোগ্য ফলাফল।'
              : 'Same frozen input snapshot + rule version = reproducible result.'}
          </CardDescription>
        </CardHeader>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Info className="size-4" /> {lang === 'bn' ? 'মাপডালি ও ওজন' : 'Metrics & weights'}
          </CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'ওজনযুক্ত গড়: Σ(wᵢ·sᵢ) / Σ(wᵢ)। মাপডালিগুলোর মান 0–1-এ স্বাভাবিকীকৃত।'
              : 'Weighted mean: Σ(wᵢ·sᵢ) / Σ(wᵢ). Each metric is normalised to 0–1 within declared bounds.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {metrics.map((m) => (
            <div key={m.key} className="flex flex-col gap-1 rounded-lg border border-border p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <m.icon className="size-4 text-primary" />
                  <span className="font-medium text-foreground">{m.key}</span>
                </div>
                <Badge variant="outline" className="text-xs">
                  {lang === 'bn' ? 'ওজন' : 'weight'} {m.weight}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{m.desc}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{lang === 'bn' ? 'ডেটা উৎস' : 'Data sources'}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 text-sm">
          <div>
            <p className="font-medium text-foreground">NASA POWER (daily)</p>
            <p className="text-muted-foreground">
              {lang === 'bn'
                ? '০.৫° কোষ, ২৪ ঘণ্টা বৃষ্টিপাত/তাপমাত্রা। ৭ দিন ক্যাশ, ৩ রিট্রাই, ১০স টাইমআউট। অনুপস্থিত বৃষ্টিপাত কখনও ০ করা হয় না।'
                : '0.5° cell, 24-hour precip/temp. 7-day cache, 3 retries, 10 s timeout. Missing rainfall is never zero-filled.'}
            </p>
          </div>
          <Separator />
          <div>
            <p className="font-medium text-foreground">HLS NDVI (L30)</p>
            <p className="text-muted-foreground">
              {lang === 'bn'
                ? 'প্রতি-দৃশ্য NDVI = (NIR−R)/(NIR+R)। ≥ 40% বৈধ আবরণ না হলে "অনুমান" চিহ্নিত।'
                : 'Per-scene NDVI = (NIR−R)/(NIR+R). Below 40% valid coverage → labelled "inferred".'}
            </p>
          </div>
          <Separator />
          <div>
            <p className="font-medium text-foreground">{lang === 'bn' ? 'ফসল-ক্যাটালগ' : 'Crop catalogue'}</p>
            <p className="text-muted-foreground">
              {lang === 'bn'
                ? 'স্থানীয় কৃষি নির্দেশিকা (পানি/তাপ/মৌসুম/মূল্য-খরচ)। রোল-ভিত্তিক হার্ড-ফিল্টার।'
                : 'Local agronomy guidance (water/heat/season/price-cost). Role-based hard filters.'}
            </p>
          </div>
        </CardContent>
      </Card>

      <p className="mt-6 text-xs text-muted-foreground">
        {t('disclaimer', lang)}
      </p>
    </main>
  )
}
