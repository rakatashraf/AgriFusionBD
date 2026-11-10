import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { ClipboardCheck, MessageSquare, Send } from 'lucide-react'
import { listCases, listFields, postCaseMessage, decideCase } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { AssistanceCase, Field } from '#/lib/types'
import { StatusBadge } from '#/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Textarea } from '#/components/ui/textarea'
import { toast } from 'sonner'

export const Route = createFileRoute('/professional/cases/')({ component: OfficerCasesPage })

export default function OfficerCasesPage() {
  const lang = useLocale()
  const [cases, setCases] = useState<AssistanceCase[]>([])
  const [fields, setFields] = useState<Field[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [filter, setFilter] = useState('all')

  const load = () => {
    listCases().then(setCases)
    listFields().then(setFields)
  }
  useEffect(load, [])

  const fieldLabel = (id: string) => fields.find((f) => f.id === id)?.name ?? id
  const shown = cases.filter((c) => (filter === 'all' ? true : c.status === filter))
  const [deciding, setDeciding] = useState<string | null>(null)

  // Officer dashboard summary — assigned cases, pending review, open, resolved.
  const openCount = cases.filter((c) => c.status === 'open').length
  const reviewCount = cases.filter((c) => c.status === 'in_review').length
  const resolvedCount = cases.filter((c) => c.status === 'resolved').length

  async function decide(caseId: string, decision: 'accept' | 'question' | 'reject') {
    const note = drafts[caseId]?.trim()
    setDeciding(caseId)
    try {
      await decideCase(caseId, decision, note)
      load()
      toast.success(
        lang === 'bn'
          ? decision === 'accept' ? 'গ্রহণ করা হয়েছে' : decision === 'question' ? 'প্রশ্ন করা হয়েছে' : 'বাতিল করা হয়েছে'
          : decision === 'accept' ? 'Accepted' : decision === 'question' ? 'Marked for review' : 'Rejected',
      )
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      toast.error(lang === 'bn' ? `সমস্যা: ${msg}` : `Failed: ${msg}`)
    } finally {
      setDeciding(null)
    }
  }

  async function send(caseId: string) {
    const body = drafts[caseId]?.trim()
    if (!body) return
    await postCaseMessage(caseId, body)
    setDrafts((d) => ({ ...d, [caseId]: '' }))
    load()
    toast.success(lang === 'bn' ? 'পাঠানো হয়েছে' : 'Sent')
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
            <ClipboardCheck className="size-6 text-primary" /> {t('cases', lang)} — {lang === 'bn' ? 'অফিসার' : 'Officer'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {lang === 'bn'
              ? 'আপনার অঞ্চলের অনুমোদিত খামার ও কেসের তালিকা। পরামর্শ নথিভুক্ত করুন।'
              : 'Your assigned-area worklist. Document advice and track status.'}
          </p>
        </div>
        <div className="flex gap-1.5">
          {['all', 'open', 'in_review', 'resolved'].map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={
                'rounded-full px-3 py-1 text-xs font-medium transition ' +
                (filter === s
                  ? 'bg-primary text-primary-foreground'
                  : 'border border-border bg-card text-muted-foreground hover:text-foreground')
              }
            >
              {s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: lang === 'bn' ? 'মোট কেস' : 'Assigned cases', value: cases.length, tint: 'tint-blue' },
          { label: lang === 'bn' ? 'খোলা' : 'Open', value: openCount, tint: 'tint-sand' },
          { label: lang === 'bn' ? 'পর্যালোচনায়' : 'Pending review', value: reviewCount, tint: 'tint-red' },
          { label: lang === 'bn' ? 'সমাধান হয়েছে' : 'Resolved', value: resolvedCount, tint: 'tint-green' },
        ].map((s) => (
          <div key={s.label} className={`rounded-2xl border border-border p-4 ${s.tint}`}>
            <div className="text-2xl font-bold text-foreground">{s.value}</div>
            <div className="mt-0.5 text-xs font-medium text-foreground/70">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-4">
        {shown.map((c) => (
          <Card key={c.id}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">{c.subject}</CardTitle>
                <CardDescription className="mt-1 flex flex-wrap items-center gap-2">
                  <Link to="/farmer/fields/$fieldId" params={{ fieldId: c.fieldId }} search={{ metric: 'rainfall_mm' } as never} className="underline underline-offset-2">
                    {fieldLabel(c.fieldId)}
                  </Link>
                  <span>·</span>
                  <span className="text-xs">Farmer: {c.farmerId}</span>
                </CardDescription>
              </div>
              <StatusBadge status={c.status} />
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex max-h-60 flex-col gap-2 overflow-y-auto">
                {c.messages.map((m) => (
                  <div
                    key={m.id}
                    className={'max-w-[80%] rounded-lg px-3 py-2 text-sm ' +
                      (m.authorRole === 'farmer' ? 'self-end border border-primary/20 bg-primary/5' : 'self-start border border-border bg-muted/40')}
                  >
                    <div className="mb-1 text-[11px] text-muted-foreground">
                      <Badge variant="outline" className="h-4 px-1.5 text-[10px]">{m.authorRole.replace('_', ' ')}</Badge>{' '}
                      {m.at.slice(0, 16).replace('T', ' ')}
                    </div>
                    <p className="text-foreground">{m.body}</p>
                  </div>
                ))}
              </div>

              <div className="flex items-end gap-2">
                <Textarea
                  rows={2}
                  placeholder={lang === 'bn' ? 'পরামর্শ বা উত্তর লিখুন…' : 'Write advice or a reply…'}
                  value={drafts[c.id] ?? ''}
                  onChange={(e) => setDrafts((d) => ({ ...d, [c.id]: e.target.value }))}
                />
                <Button size="sm" onClick={() => send(c.id)} disabled={!drafts[c.id]?.trim()}>
                  <Send className="size-4" />
                </Button>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={deciding === c.id}
                  onClick={() => decide(c.id, 'accept')}
                >
                  {lang === 'bn' ? 'গ্রহণ' : 'Accept'}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={deciding === c.id}
                  onClick={() => decide(c.id, 'question')}
                >
                  {lang === 'bn' ? 'প্রশ্ন করুন' : 'Question'}
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={deciding === c.id}
                  onClick={() => decide(c.id, 'reject')}
                >
                  {lang === 'bn' ? 'বাতিল' : 'Reject'}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}

        {shown.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
              <MessageSquare className="size-8 text-muted-foreground" />
              <p className="text-muted-foreground">{lang === 'bn' ? 'এই ফিল্টারে কোনো কেস নেই।' : 'No cases for this filter.'}</p>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  )
}
