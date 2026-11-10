import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { Sprout, User, Shield, Globe, Bot, UserPlus, LogIn } from 'lucide-react'
import { login, signup } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
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

function roleDest(role: RoleChoice): string {
  return role === 'farmer'
    ? '/farmer/fields'
    : role === 'officer'
      ? '/professional/cases'
      : role === 'researcher'
        ? '/professional/research'
        : '/farmer/rover'
}

function Login() {
  const lang = useLocale()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [busy, setBusy] = useState<string | null>(null)

  // Sign-up form state.
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [role, setRole] = useState<RoleChoice>('farmer')
  const [district, setDistrict] = useState('Rajshahi')
  const [upazila, setUpazila] = useState('')
  const [farmSizeHa, setFarmSizeHa] = useState('')
  const [assignedArea, setAssignedArea] = useState('')
  const [smsOptIn, setSmsOptIn] = useState(true)

  async function choose(r: RoleChoice) {
    setBusy(r)
    try {
      await login(r)
      navigate({ to: roleDest(r) })
    } catch (err) {
      toast.error(
        lang === 'bn'
          ? `লগইন ব্যর্থ: ${err instanceof Error ? err.message : String(err)}`
          : `Login failed: ${err instanceof Error ? err.message : String(err)}`,
      )
      setBusy(null)
    }
  }

  async function doSignup(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !phone.trim()) {
      toast.error(lang === 'bn' ? 'নাম ও ফোন নম্বর দিন।' : 'Please enter your name and phone number.')
      return
    }
    setBusy('signup')
    try {
      await signup({
        name: name.trim(),
        phone: phone.trim(),
        role,
        district: district.trim(),
        upazila: upazila.trim(),
        farmSizeHa: role === 'farmer' ? farmSizeHa.trim() : undefined,
        assignedArea: role !== 'farmer' ? assignedArea.trim() : undefined,
        smsOptIn,
      })
      toast.success(lang === 'bn' ? 'অ্যাকাউন্ট তৈরি হয়েছে। স্বাগতম!' : 'Account created. Welcome!')
      navigate({ to: roleDest(role) })
    } catch (err) {
      toast.error(
        lang === 'bn'
          ? `সাইন আপ ব্যর্থ: ${err instanceof Error ? err.message : String(err)}`
          : `Sign up failed: ${err instanceof Error ? err.message : String(err)}`,
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

      {/* Sign in / Sign up toggle */}
      <div className="mb-6 flex rounded-full border border-border bg-card p-1">
        <button
          type="button"
          onClick={() => setMode('signin')}
          className={
            'flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition ' +
            (mode === 'signin' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')
          }
        >
          <LogIn className="size-4" /> {lang === 'bn' ? 'সাইন ইন' : 'Sign in'}
        </button>
        <button
          type="button"
          onClick={() => setMode('signup')}
          className={
            'flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-medium transition ' +
            (mode === 'signup' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')
          }
        >
          <UserPlus className="size-4" /> {lang === 'bn' ? 'সাইন আপ' : 'Sign up'}
        </button>
      </div>

      {mode === 'signin' ? (
        <div className="grid w-full gap-3 sm:grid-cols-2">
          {ROLES.map(({ role: r, label, desc, icon: Icon }) => (
            <button
              key={r}
              onClick={() => choose(r)}
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
              {busy === r && (
                <span className="text-xs font-medium text-primary">Signing in…</span>
              )}
            </button>
          ))}
        </div>
      ) : (
        <form onSubmit={doSignup} className="w-full rounded-2xl border border-border bg-card p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label htmlFor="su-name" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'নাম' : 'Full name'} *
              </label>
              <Input id="su-name" value={name} onChange={(e) => setName(e.target.value)} placeholder={lang === 'bn' ? 'যেমন: রফিকুল ইসলাম' : 'e.g. Rafiqul Islam'} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="su-phone" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'ফোন নম্বর' : 'Phone number'} *
              </label>
              <Input id="su-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+880 1XXX-XXXXXX" inputMode="tel" />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="su-role" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'আপনি কে?' : 'I am a'}
              </label>
              <select
                id="su-role"
                value={role}
                onChange={(e) => setRole(e.target.value as RoleChoice)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
              >
                <option value="farmer">{lang === 'bn' ? 'কৃষক' : 'Farmer'}</option>
                <option value="officer">{lang === 'bn' ? 'সম্প্রসারণ অফিসার' : 'Extension officer'}</option>
                <option value="researcher">{lang === 'bn' ? 'গবেষক' : 'Researcher'}</option>
                <option value="rover_operator">{lang === 'bn' ? 'রোভার অপারেটর' : 'Rover operator'}</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="su-district" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'জেলা' : 'District'}
              </label>
              <Input id="su-district" value={district} onChange={(e) => setDistrict(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="su-upazila" className="text-xs font-medium text-muted-foreground">
                {lang === 'bn' ? 'উপজেলা' : 'Upazila'}
              </label>
              <Input id="su-upazila" value={upazila} onChange={(e) => setUpazila(e.target.value)} placeholder={lang === 'bn' ? 'যেমন: পবা' : 'e.g. Paba'} />
            </div>
            {role === 'farmer' ? (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="su-farm" className="text-xs font-medium text-muted-foreground">
                  {lang === 'bn' ? 'মোট জমির পরিমাণ (হেক্টর)' : 'Total farm size (hectares)'}
                </label>
                <Input id="su-farm" value={farmSizeHa} onChange={(e) => setFarmSizeHa(e.target.value)} placeholder="e.g. 2.5" inputMode="decimal" />
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="su-area" className="text-xs font-medium text-muted-foreground">
                  {lang === 'bn' ? 'দায়িত্বপ্রাপ্ত এলাকা' : 'Assigned area'}
                </label>
                <Input id="su-area" value={assignedArea} onChange={(e) => setAssignedArea(e.target.value)} placeholder={lang === 'bn' ? 'যেমন: রাজশাহী সদর' : 'e.g. Rajshahi Sadar'} />
              </div>
            )}
          </div>
          <label className="mt-4 flex cursor-pointer items-start gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={smsOptIn}
              onChange={(e) => setSmsOptIn(e.target.checked)}
              className="mt-0.5 size-4 accent-primary"
            />
            <span>
              {lang === 'bn'
                ? 'পরামর্শ ও সতর্কতা ফোনে SMS-এ পাঠান (অনলাইনে না থাকলেও পাবেন)।'
                : 'Send advice and warnings to my phone by SMS (so I get them even when I cannot check online).'}
            </span>
          </label>
          <Button type="submit" className="mt-5 w-full" disabled={busy !== null}>
            {busy === 'signup' ? '…' : lang === 'bn' ? 'অ্যাকাউন্ট তৈরি করুন' : 'Create account'}
          </Button>
          <p className="mt-3 text-center text-xs text-muted-foreground">
            {lang === 'bn'
              ? 'ডেমো: অ্যাকাউন্ট এই ব্রাউজারে সংরক্ষিত হয়। প্রোডাকশনে ভেরিফাইড পরিচয় ব্যবহার হবে।'
              : 'Demo: the account is stored in this browser. Production uses verified identities.'}
          </p>
        </form>
      )}

      <p className="mt-8 text-xs text-muted-foreground">
        {lang === 'bn'
          ? 'ডিমো: পাসওয়ার্ডহীন, Django সেশন-ভিত্তিক। প্রোডাকশনে ভেরিফাইড পরিচয় ব্যবহার হবে।'
          : 'Demo: passwordless, Django session-based. Production uses verified identities.'}
      </p>
    </main>
  )
}
