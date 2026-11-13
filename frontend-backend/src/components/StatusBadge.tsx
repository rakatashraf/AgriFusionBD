import { Badge } from '#/components/ui/badge'
import { useLocale } from '#/lib/i18n'
import type { AnalysisStatus, CaseStatus } from '#/lib/types'

const STATUS_STYLES: Record<string, string> = {
  complete: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  resolved: 'border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  running: 'border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-200',
  in_review: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  queued: 'border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-300',
  partial: 'border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  failed: 'border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
  cancelled: 'border-zinc-300 bg-zinc-100 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-400',
  rejected: 'border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-900/40 dark:text-rose-200',
  open: 'border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-200',
  active: 'border-emerald-300 bg-emerald-100 text-emerald-800',
}

const LABELS: Record<string, { en: string; bn: string }> = {
  queued: { en: 'Queued', bn: 'লাইনে' },
  running: { en: 'Running', bn: 'চলমান' },
  complete: { en: 'Complete', bn: 'সম্পন্ন' },
  partial: { en: 'Partial', bn: 'আংশিক' },
  failed: { en: 'Failed', bn: 'ব্যর্থ' },
  cancelled: { en: 'Cancelled', bn: 'বাতিল' },
  open: { en: 'Open', bn: 'খোলা' },
  in_review: { en: 'In review', bn: 'পর্যালোচনায়' },
  resolved: { en: 'Resolved', bn: 'সমাধান' },
  rejected: { en: 'Rejected', bn: 'বাতিল' },
  feasible: { en: 'Feasible', bn: 'সম্ভব' },
  constrained: { en: 'Constrained', bn: 'সীমিত' },
  infeasible: { en: 'Infeasible', bn: 'অসম্ভব' },
}

export function StatusBadge({ status }: { status: AnalysisStatus | CaseStatus | string }) {
  const lang = useLocale()
  const label = LABELS[status]?.[lang] ?? status
  return (
    <Badge variant="outline" className={STATUS_STYLES[status] ?? ''}>
      {label}
    </Badge>
  )
}
