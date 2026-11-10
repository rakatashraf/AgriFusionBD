import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { Sprout, User, Shield, Globe, Bot } from 'lucide-react'
import { login } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import { Button } from '#/components/ui/button'
import { toast } from 'sonner'

export const Route = createFileRoute('/login')({ component: Login })

type RoleChoice = 'farmer' | 'officer' | 'researcher' | 'rover_operator'

const ROLES: Array<{ role: RoleChoice; label: string; desc: string; icon: any }> = [
  {
    role: 'farmer',
    label: 'Farmer',
    desc: 'See your fields, compare rotations, open cases',
    icon: User,
  },
  {
    role: 'officer',
    label: 'Extension officer',
    desc: 'Review farmer cases, document advice',
    icon: Shield,
  },
  {
    role: 'researcher',
    label: 'Researcher',
    desc: 'Explore trends, export data with provenance',
    icon: Globe,
  },
  {
    role: 'rover_operator',
    label: 'Rover operator',
    desc: 'Manage devices, upload field observations',
    icon: Bot,
  },
]

function Login() {
  const lang = useLocale()
  const navigate = useNavigate()
  const [busy, setBusy] = useState<string | null>(null)

  async function choose(role: RoleChoice) {
    setBusy(role)
    try {
      await login(role)
      // Navigate to the role's home page.
      const dest =
        role === 'farmer'
          ? '/farmer/fields'
          : role === 'officer'
            ? '/professional/cases'
            : role === 'researcher'
              ? '/professional/research'
              : '/farmer/rover'
      navigate({ to: dest })
    } catch (err) {
      toast.error(
        lang === 'bn'
          ? `লগইন ব্যর্থ: ${err instanceof Error ? err.message : String(err)}`
          : `Login failed: ${err instanceof Error ? err.message : String(err)}`,
      )
      setBusy(null)
    }
  }

  return (
    <main className="mx-auto flex min-h-[80vh] max-w-2xl flex-col items-center justify-center px-4 py-12">
      <div className="mb-8 flex flex-col items-center gap-2">
        <span className="flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/70 text-primary-foreground shadow-lg shadow-primary/20">
          <Sprout className="size-7" />
        </span>
        <h1 className="text-2xl font-bold text-foreground">{t('app_name', lang)}</h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'একটি ডেমো পরিচয় বেছে নিন — সার্ভার-সাইড রোল অনুসারে অ্যাক্সেস।'
            : 'Pick a demo identity — access is scoped by the server-side role.'}
        </p>
      </div>

      <div className="grid w-full gap-3 sm:grid-cols-2">
        {ROLES.map(({ role, label, desc, icon: Icon }) => (
          <button
            key={role}
            onClick={() => choose(role)}
            disabled={busy !== null}
            className="lift glass group flex flex-col gap-3 rounded-2xl border border-border/70 p-5 text-left shadow-sm transition-all hover:border-primary/40 hover:bg-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="size-5" />
              </span>
              <span className="font-semibold text-foreground">{label}</span>
            </div>
            <span className="text-sm text-muted-foreground">{desc}</span>
            {busy === role && (
              <span className="text-xs font-medium text-primary">Signing in…</span>
            )}
          </button>
        ))}
      </div>

      <p className="mt-8 text-xs text-muted-foreground">
        {lang === 'bn'
          ? 'ডিমো: পাসওয়ার্ডহীন, Django সেশন-ভিত্তিক। প্রোডাকশনে ভেরিফাইড পরিচয় ব্যবহার হবে।'
          : 'Demo: passwordless, Django session-based. Production uses verified identities.'}
      </p>
    </main>
  )
}
