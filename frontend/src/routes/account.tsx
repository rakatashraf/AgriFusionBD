import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { User as UserIcon, Phone, MapPin, Ruler, MessageSquareText, Sprout } from 'lucide-react'
import { currentUser, readProfile, listFields } from '#/lib/api'
import AreaSummary from '#/components/advisory/AreaSummary'
import { useLocale } from '#/lib/i18n'
import type { Field, User } from '#/lib/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'

export const Route = createFileRoute('/account')({ component: AccountPage })

export default function AccountPage() {
  const lang = useLocale()
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<ReturnType<typeof readProfile>>(null)
  const [fields, setFields] = useState<Field[]>([])
  const [smsOptIn, setSmsOptIn] = useState(true)

  useEffect(() => {
    setUser(currentUser())
    const p = readProfile()
    setProfile(p)
    if (p) setSmsOptIn(p.smsOptIn !== false)
    listFields().then(setFields).catch(() => {})
  }, [])

  function toggleSms(v: boolean) {
    setSmsOptIn(v)
    try {
      const raw = window.localStorage.getItem('fieldshift_profile')
      if (raw) {
        const p = JSON.parse(raw)
        p.smsOptIn = v
        window.localStorage.setItem('fieldshift_profile', JSON.stringify(p))
        setProfile(p)
      }
    } catch {
      /* ignore */
    }
  }

  if (!user) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12 text-center">
        <p className="text-muted-foreground">
          {lang === 'bn' ? 'প্রোফাইল দেখতে সাইন ইন করুন।' : 'Sign in to see your profile.'}
        </p>
        <Link to="/login" className="mt-4 inline-block font-medium text-primary hover:underline">
          {lang === 'bn' ? 'সাইন ইন' : 'Sign in'}
        </Link>
      </main>
    )
  }

  const isFarmer = user.roles.includes('farmer')
  const isProfessional = user.roles.some((r) => r === 'officer' || r === 'researcher')

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <UserIcon className="size-6 text-primary" />
          {lang === 'bn' ? 'আমার প্রোফাইল' : 'My profile'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'আপনার তথ্য, নিবন্ধিত জমি ও SMS পছন্দ।'
            : 'Your details, registered fields and SMS preferences.'}
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Account details */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{user.name}</CardTitle>
            <CardDescription>{user.organization ?? (lang === 'bn' ? 'পাইলট কৃষক' : 'Pilot farmer')}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-1">
              {user.roles.map((r) => (
                <Badge key={r} variant="secondary" className="text-[11px]">{r.replace('_', ' ')}</Badge>
              ))}
            </div>
            <div className="flex flex-col gap-2 text-sm">
              <p className="flex items-center gap-2 text-foreground">
                <Phone className="size-4 text-muted-foreground" />
                {profile?.phone ?? '—'}
              </p>
              <p className="flex items-center gap-2 text-foreground">
                <MapPin className="size-4 text-muted-foreground" />
                {profile ? `${profile.district}${profile.upazila ? ` · ${profile.upazila}` : ''}` : '—'}
              </p>
              {isFarmer && (
                <p className="flex items-center gap-2 text-foreground">
                  <Ruler className="size-4 text-muted-foreground" />
                  {lang === 'bn' ? 'মোট জমি: ' : 'Total farm size: '}
                  {profile?.farmSizeHa ? `${profile.farmSizeHa} ha` : '—'}
                </p>
              )}
              {isProfessional && (
                <p className="flex items-center gap-2 text-foreground">
                  <MapPin className="size-4 text-muted-foreground" />
                  {lang === 'bn' ? 'দায়িত্বপ্রাপ্ত এলাকা: ' : 'Assigned area: '}
                  {profile?.assignedArea ?? 'Rajshahi'}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* SMS preferences */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquareText className="size-4 text-primary" />
              {lang === 'bn' ? 'ফোনে SMS সতর্কতা' : 'SMS alerts to my phone'}
            </CardTitle>
            <CardDescription>
              {lang === 'bn'
                ? 'অনলাইনে না থাকলেও পরামর্শ ও সতর্কতা ফোনে পাবেন।'
                : 'Get advice and warnings on your phone even when you cannot check online.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <label className="flex cursor-pointer items-start gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={smsOptIn}
                onChange={(e) => toggleSms(e.target.checked)}
                className="mt-0.5 size-4 accent-primary"
              />
              <span>
                {lang === 'bn'
                  ? 'পরামর্শ, পূর্বাভাস ও সতর্কতা SMS-এ পাঠান।'
                  : 'Send advice, forecasts and warnings by SMS.'}
              </span>
            </label>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              {lang === 'bn'
                ? 'ডেমো: কোনো আসল SMS গেটওয়ে যুক্ত নেই। প্রোডাকশনে এই পছন্দ অনুযায়ী স্বয়ংক্রিয়ভাবে বার্তা পাঠানো হবে।'
                : 'Demo: no real SMS gateway is connected. In production, messages would be sent automatically according to this preference.'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Farmer: my registered fields */}
      {isFarmer && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sprout className="size-4 text-primary" />
              {lang === 'bn' ? 'আমার নিবন্ধিত জমি' : 'My registered fields'}
            </CardTitle>
            <CardDescription>
              {fields.length} {lang === 'bn' ? 'টি জমি' : 'fields'} ·{' '}
              {fields.reduce((s, f) => s + (f.areaHa || 0), 0).toFixed(2)} ha
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {fields.map((f) => (
              <Link
                key={f.id}
                to={`/farmer/fields/${f.id}`}
                className="flex items-center justify-between rounded-xl border border-border px-4 py-3 text-sm transition hover:border-primary/40"
              >
                <span className="font-medium text-foreground">{f.name}</span>
                <span className="text-muted-foreground">
                  {f.areaHa} ha · {f.soilType ?? '—'} · {f.irrigation}
                </span>
              </Link>
            ))}
            {fields.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {lang === 'bn' ? 'এখনো কোনো জমি নিবন্ধিত হয়নি।' : 'No fields registered yet.'}
              </p>
            )}
            <Link to="/farmer/fields" className="mt-1 text-sm font-medium text-primary hover:underline">
              {lang === 'bn' ? 'জমি যোগ করুন / ম্যাপ দেখুন →' : 'Add a field / view the map →'}
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Professional: assigned area summary */}
      {isProfessional && (
        <div className="mt-4">
          <AreaSummary fields={fields} areaName={profile?.assignedArea ?? 'Rajshahi'} />
        </div>
      )}
    </main>
  )
}
