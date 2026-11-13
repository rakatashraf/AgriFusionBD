import { useState } from 'react'
import { NotebookPen, Trash2, Camera, Droplets, Wheat, FlaskConical } from 'lucide-react'
import {
  loadLocalObservations,
  addLocalObservation,
  deleteLocalObservation,
  OBSERVATION_KINDS,
  type LocalObservation,
  type ObservationKind,
} from '#/lib/fieldSetup'
import { useLocale } from '#/lib/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { Textarea } from '#/components/ui/textarea'
import { Badge } from '#/components/ui/badge'
import { toast } from 'sonner'

const KIND_ICON: Record<ObservationKind, typeof Camera> = {
  soil_test: FlaskConical,
  irrigation: Droplets,
  crop_outcome: Wheat,
  photo_note: Camera,
}

export default function LocalObservations({ fieldId }: { fieldId: string }) {
  const lang = useLocale()
  const [obs, setObs] = useState<LocalObservation[]>(() => loadLocalObservations(fieldId))
  const [kind, setKind] = useState<ObservationKind>('irrigation')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [detail, setDetail] = useState('')
  const [open, setOpen] = useState(false)

  function kindLabel(k: ObservationKind): string {
    const found = OBSERVATION_KINDS.find((x) => x.value === k)
    return found ? (lang === 'bn' ? found.bn : found.en) : k
  }

  function submit() {
    if (!note.trim()) {
      toast.error(lang === 'bn' ? 'একটি নোট লিখুন।' : 'Please write a note.')
      return
    }
    const o: LocalObservation = {
      id: `obs-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`,
      fieldId,
      kind,
      date,
      note: note.trim(),
      detail: detail.trim() || undefined,
    }
    addLocalObservation(o)
    setObs(loadLocalObservations(fieldId))
    setNote('')
    setDetail('')
    setOpen(false)
    toast.success(lang === 'bn' ? 'পর্যবেক্ষণ সংরক্ষণ করা হয়েছে।' : 'Observation saved.')
  }

  function remove(id: string) {
    deleteLocalObservation(fieldId, id)
    setObs(loadLocalObservations(fieldId))
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <NotebookPen className="size-4 text-primary" />
              {lang === 'bn' ? 'স্থানীয় পর্যবেক্ষণ' : 'Local observations'}
            </CardTitle>
            <CardDescription>
              {lang === 'bn'
                ? 'মাটির পরীক্ষা, সেচ, ফসলের ফলাফল বা ছবির নোট যোগ করুন।'
                : 'Add a soil test, irrigation record, crop outcome or photo note.'}
            </CardDescription>
          </div>
          <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
            {open ? (lang === 'bn' ? 'বন্ধ করুন' : 'Close') : lang === 'bn' ? 'যোগ করুন' : 'Add'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {open && (
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="lo-kind" className="text-xs font-medium text-muted-foreground">
                  {lang === 'bn' ? 'ধরন' : 'Type'}
                </label>
                <select
                  id="lo-kind"
                  value={kind}
                  onChange={(e) => setKind(e.target.value as ObservationKind)}
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
                >
                  {OBSERVATION_KINDS.map((k) => (
                    <option key={k.value} value={k.value}>{lang === 'bn' ? k.bn : k.en}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="lo-date" className="text-xs font-medium text-muted-foreground">
                  {lang === 'bn' ? 'তারিখ' : 'Date'}
                </label>
                <Input id="lo-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="lo-note" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'নোট' : 'Note'}
              </label>
              <Textarea
                id="lo-note"
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={lang === 'bn' ? 'যেমন: আজ ২ ঘণ্টা সেচ দেওয়া হয়েছে।' : 'e.g. Irrigated for 2 hours today.'}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="lo-detail" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'বিস্তারিত (ঐচ্ছিক)' : 'Detail (optional)'}
              </label>
              <Input
                id="lo-detail"
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                placeholder={lang === 'bn' ? 'যেমন: পানির উৎস — নলকূপ' : 'e.g. Water source — tubewell'}
              />
            </div>
            <Button size="sm" onClick={submit}>
              {lang === 'bn' ? 'সংরক্ষণ করুন' : 'Save observation'}
            </Button>
          </div>
        )}
        {obs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {lang === 'bn'
              ? 'এই জমিতে এখনো কোনো স্থানীয় পর্যবেক্ষণ নেই।'
              : 'No local observations for this field yet.'}
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {obs.map((o) => {
              const Icon = KIND_ICON[o.kind]
              return (
                <div key={o.id} className="flex items-start justify-between gap-2 rounded-lg border border-border px-3 py-2.5">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent">
                      <Icon className="size-4 text-primary" />
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px]">{kindLabel(o.kind)}</Badge>
                        <span className="text-xs text-muted-foreground">{o.date}</span>
                      </div>
                      <p className="mt-1 text-sm text-foreground">{o.note}</p>
                      {o.detail && <p className="text-xs text-muted-foreground">{o.detail}</p>}
                    </div>
                  </div>
                  <button
                    type="button"
                    aria-label="Delete observation"
                    onClick={() => remove(o.id)}
                    className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
