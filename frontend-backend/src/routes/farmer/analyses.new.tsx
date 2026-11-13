import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { ArrowLeft, Send } from 'lucide-react'
import { submitAnalysis, listFields, listCrops } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { Crop, Field, AnalysisRequest } from '#/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { Label } from '#/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '#/components/ui/select'
import { Separator } from '#/components/ui/separator'
import { Checkbox } from '#/components/ui/checkbox'
import { toast } from 'sonner'

const WEIGHT_LABELS = [
  ['waterEfficiency', 'Water efficiency'],
  ['heatResilience', 'Heat resilience'],
  ['soilCover', 'Soil cover'],
  ['rotationDiversity', 'Rotation diversity'],
  ['economics', 'Economics'],
] as const

export const Route = createFileRoute('/farmer/analyses/new')({
  component: NewAnalysis,
  validateSearch: (s: Record<string, unknown>) => ({ fieldId: (s.fieldId as string) || undefined }),
})

function NewAnalysis() {
  const { fieldId } = Route.useSearch()
  const lang = useLocale()
  const navigate = useNavigate()
  const [fields, setFields] = useState<Field[]>([])
  const [crops, setCrops] = useState<Crop[]>([])
  const [selectedField, setSelectedField] = useState(fieldId ?? '')
  const [start, setStart] = useState('2026-12-01')
  const [end, setEnd] = useState('2027-11-30')
  const [weights, setWeights] = useState<Record<string, number>>({
    waterEfficiency: 0.4, heatResilience: 0.25, soilCover: 0.1, rotationDiversity: 0.1, economics: 0.15,
  })
  const [excluded, setExcluded] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listFields().then(setFields).catch(() => {})
    listCrops().then(setCrops).catch(() => setCrops([]))
  }, [])

  function submit() {
    if (!selectedField) return
    setBusy(true)
    const req: AnalysisRequest = {
      fieldId: selectedField,
      seasonStart: start,
      seasonEnd: end,
      weights: weights as AnalysisRequest['weights'],
      excludeCropIds: excluded,
    }
    submitAnalysis(req)
      .then((run) => {
        toast.success(lang === 'bn' ? 'অনুরোধ জমা হয়েছে' : 'Request submitted')
        navigate({ to: '/farmer/analyses/$analysisId', params: { analysisId: run.id }, search: {} })
      })
      .catch(() => toast.error(lang === 'bn' ? 'ত্রুটি হয়েছে' : 'Something went wrong'))
      .finally(() => setBusy(false))
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <button
        onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: undefined } })}
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {t('analyses', lang)}
      </button>
      <h1 className="mb-6 text-2xl font-bold text-foreground">
        {lang === 'bn' ? 'তুলনা অনুরোধ করুন' : 'Request a comparison'}
      </h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{lang === 'bn' ? 'মৌলিক তথ্য' : 'Basics'}</CardTitle>
          <CardDescription>
            {lang === 'bn'
              ? 'জমি, মৌসুম এবং আপনার অগ্রাধিকার নির্বাচন করুন।'
              : 'Choose a field, the season, and your priorities.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label>{lang === 'bn' ? 'জমি' : 'Field'}</Label>
              <Select value={selectedField} onValueChange={(v) => setSelectedField(v ?? '')}>
                <SelectTrigger><SelectValue placeholder={lang === 'bn' ? 'জমি বাছাই করুন' : 'Select a field'} /></SelectTrigger>
                <SelectContent>
                  {fields.map((f) => (
                    <SelectItem key={f.id} value={f.id}>{f.name}{f.isPinEstimate ? ' (pin)' : ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label>{lang === 'bn' ? 'এখন থেকে' : 'From'}</Label>
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label>{lang === 'bn' ? 'এ পর্যন্ত' : 'To'}</Label>
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
          </div>

          <Separator />

          <div>
            <Label className="mb-3 block">{t('weights', lang)}</Label>
            <div className="flex flex-col gap-3">
              {WEIGHT_LABELS.map(([key, label]) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-40 text-sm text-foreground">{label}</span>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={weights[key]}
                    onChange={(e) => setWeights((w) => ({ ...w, [key]: Number(e.target.value) }))}
                    className="flex-1 accent-[var(--primary)]"
                  />
                  <span className="w-10 text-right text-sm font-medium">{Math.round(weights[key] * 100)}%</span>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          <div>
            <Label className="mb-2 block">{lang === 'bn' ? 'বাদ দিতে চান কোন ফসল' : 'Excluded crops'}</Label>
            <div className="flex flex-wrap gap-3">
              {crops.map((c) => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={excluded.includes(c.id)}
                    onCheckedChange={(v) =>
                      setExcluded((prev) => (v ? [...prev, c.id] : prev.filter((x) => x !== c.id)))
                    }
                  />
                  {lang === 'bn' ? c.nameBn : c.name}
                </label>
              ))}
            </div>
          </div>

          <Separator />

          <Button onClick={submit} disabled={busy || !selectedField} className="w-full">
            <Send className="size-4" />
            {busy ? (lang === 'bn' ? 'জমা হচ্ছে…' : 'Submitting…') : (lang === 'bn' ? 'অনুরোধ জমা দিন' : 'Submit request')}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            {lang === 'bn'
              ? 'এই অনুরোধ একটি আইডি-পাওয়ার চাকরিতে রূপ নেবে; ফলাফল দেখতে কয়েক মিনিট লাগতে পারে।'
              : 'This request becomes an idempotent job; results may take a few minutes.'}
          </p>
        </CardContent>
      </Card>
    </main>
  )
}
