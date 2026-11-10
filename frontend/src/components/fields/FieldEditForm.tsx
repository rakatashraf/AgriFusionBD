import { useState } from 'react'
import { Pencil, X } from 'lucide-react'
import { updateField } from '#/lib/api'
import { useLocale } from '#/lib/i18n'
import type { Field } from '#/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { toast } from 'sonner'

const PRIORITY_OPTIONS = ['water_efficiency', 'heat_resilience', 'soil_cover', 'rotation_diversity', 'economics']

const SOIL_TYPES = ['Clay', 'Loam', 'Sandy loam', 'Silt loam', 'Sandy', 'Clay loam']

export default function FieldEditForm({ field, onSaved, onCancel }: { field: Field; onSaved: (f: Field) => void; onCancel: () => void }) {
  const lang = useLocale()
  const [name, setName] = useState(field.name)
  const [soilType, setSoilType] = useState(field.soilType ?? '')
  const [irrigation, setIrrigation] = useState<Field['irrigation']>(field.irrigation)
  const [priorities, setPriorities] = useState<string[]>(field.priorities ?? [])
  const [saving, setSaving] = useState(false)

  function togglePriority(p: string) {
    setPriorities((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]))
  }

  async function save() {
    if (!name.trim()) {
      toast.error(lang === 'bn' ? 'জমির নাম দিন।' : 'Please enter a field name.')
      return
    }
    setSaving(true)
    try {
      const updated = await updateField(field.id, {
        name: name.trim(),
        soilType: soilType.trim() || undefined,
        irrigation,
        priorities,
      })
      toast.success(lang === 'bn' ? 'জমি সংরক্ষণ করা হয়েছে।' : 'Field saved.')
      onSaved(updated)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
      setSaving(false)
    }
  }

  return (
    <Card className="border-primary/40">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <Pencil className="size-4" />
              {lang === 'bn' ? 'জমি সম্পাদনা করুন' : 'Edit field'}
            </CardTitle>
            <CardDescription>
              {lang === 'bn' ? 'নাম, মাটি, সেচ ও অগ্রাধিকার পরিবর্তন করুন।' : 'Change the name, soil, irrigation and priorities.'}
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={onCancel} aria-label="Close">
            <X className="size-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="fe-name" className="text-xs font-medium text-muted-foreground">
              {lang === 'bn' ? 'জমির নাম' : 'Field name'}
            </label>
            <Input id="fe-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="fe-soil" className="text-xs font-medium text-muted-foreground">
              {lang === 'bn' ? 'মাটির ধরন' : 'Soil type'}
            </label>
            <select
              id="fe-soil"
              value={soilType}
              onChange={(e) => setSoilType(e.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
            >
              <option value="">{lang === 'bn' ? 'জানা নেই' : 'Not known'}</option>
              {SOIL_TYPES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="fe-irr" className="text-xs font-medium text-muted-foreground">
              {lang === 'bn' ? 'সেচ' : 'Irrigation'}
            </label>
            <select
              id="fe-irr"
              value={irrigation}
              onChange={(e) => setIrrigation(e.target.value as Field['irrigation'])}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
            >
              <option value="rainfed">{lang === 'bn' ? 'বৃষ্টিনির্ভর' : 'Rainfed'}</option>
              <option value="canal">{lang === 'bn' ? 'খাল' : 'Canal'}</option>
              <option value="pump">{lang === 'bn' ? 'পাম্প' : 'Pump'}</option>
              <option value="tubewell">{lang === 'bn' ? 'নলকূপ' : 'Tubewell'}</option>
            </select>
          </div>
        </div>
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            {lang === 'bn' ? 'অগ্রাধিকার' : 'Priorities'}
          </p>
          <div className="flex flex-wrap gap-2">
            {PRIORITY_OPTIONS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => togglePriority(p)}
                className={
                  'rounded-full border px-3 py-1 text-xs font-medium transition ' +
                  (priorities.includes(p)
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-card text-muted-foreground hover:text-foreground')
                }
              >
                {p.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => void save()} disabled={saving} className="flex-1">
            {saving ? '…' : lang === 'bn' ? 'সংরক্ষণ করুন' : 'Save changes'}
          </Button>
          <Button size="sm" variant="outline" onClick={onCancel} className="flex-1">
            {lang === 'bn' ? 'বাতিল' : 'Cancel'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
