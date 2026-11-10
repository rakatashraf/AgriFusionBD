import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { MessageSquare, Send, CheckCircle2 } from 'lucide-react'
import { listCases, listFields, postCaseMessage } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { AssistanceCase, Field } from '#/lib/types'
import { StatusBadge } from '#/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Textarea } from '#/components/ui/textarea'
import { toast } from 'sonner'

export const Route = createFileRoute('/farmer/cases/')({ component: CasesPage })

function timeAgo(iso: string) {
  const d = new Date(iso)
  const diff = Math.max(0, Date.now() - d.getTime())
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function CasesPage() {
  const lang = useLocale()
  const [cases, setCases] = useState<AssistanceCase[]>([])
  const [fields, setFields] = useState<Field[]>([])
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  const load = () => {
    listCases().then(setCases)
    listFields().then(setFields)
  }
  useEffect(load, [])

  const fieldLabel = (id: string) => fields.find((f) => f.id === id)?.name ?? id

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
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">{t('cases', lang)}</h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'অফিসার সহায়তার অনুরোধ — অবস্থা ও ইতিহাস সহ।'
            : 'Officer assistance requests — with status and history.'}
        </p>
      </header>

      <div className="flex flex-col gap-4">
        {cases.map((c) => (
          <Card key={c.id}>
            <CardHeader className="flex-row items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base">{c.subject}</CardTitle>
                <CardDescription className="mt-1 flex flex-wrap items-center gap-2">
                  <Link to="/farmer/fields/$fieldId" params={{ fieldId: c.fieldId }} search={{ metric: 'rainfall_mm' } as never} className="underline underline-offset-2">
                    {fieldLabel(c.fieldId)}
                  </Link>
                  <span>·</span>
                  <span>{timeAgo(c.updatedAt)}</span>
                </CardDescription>
              </div>
              <StatusBadge status={c.status} />
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex max-h-72 flex-col gap-3 overflow-y-auto">
                {c.messages.map((m) => (
                  <div
                    key={m.id}
                    className={
                      'max-w-[85%] rounded-lg border px-3 py-2 text-sm ' +
                      (m.authorRole === 'farmer'
                        ? 'self-end border-primary/20 bg-primary/5'
                        : 'self-start border-border bg-muted/40')
                    }
                  >
                    <div className="mb-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                        {m.authorRole.replace('_', ' ')}
                      </Badge>
                      <span>{timeAgo(m.at)}</span>
                    </div>
                    <p className="text-foreground">{m.body}</p>
                  </div>
                ))}
              </div>

              {c.status !== 'resolved' && c.status !== 'rejected' ? (
                <div className="flex items-end gap-2">
                  <Textarea
                    rows={2}
                    placeholder={lang === 'bn' ? 'বার্তা লিখুন…' : 'Write a message…'}
                    value={drafts[c.id] ?? ''}
                    onChange={(e) => setDrafts((d) => ({ ...d, [c.id]: e.target.value }))}
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') send(c.id)
                    }}
                  />
                  <Button size="sm" onClick={() => send(c.id)} disabled={!drafts[c.id]?.trim()}>
                    <Send className="size-4" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="size-4 text-emerald-600" />
                  {lang === 'bn' ? 'এই কেসটি সম্পন্ন।' : 'This case is closed.'}
                </div>
              )}
            </CardContent>
          </Card>
        ))}

        {cases.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
              <MessageSquare className="size-8 text-muted-foreground" />
              <p className="text-muted-foreground">
                {lang === 'bn' ? 'কোনো সক্রিয় কেস নেই।' : 'No active cases yet.'}
              </p>
              <Button variant="outline" size="sm">{lang === 'bn' ? 'নতুন কেস খুলুন' : 'Open a case'}</Button>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  )
}
