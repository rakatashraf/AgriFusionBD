import { Link } from '@tanstack/react-router'
import { Compass, MapPin, Home, Wrench, Search } from 'lucide-react'
import { useLocale } from '#/lib/i18n'
import { Button } from '#/components/ui/button'

/* ── 404 / 500 ────────────────────────────────────────────────────── */

const LOGO = `${import.meta.env.BASE_URL}agrifusion-logo.png`

/**
 * Shared shell for error pages (404, 500).
 * Renders the AgriFusion BD branding, a large icon, a headline, a short
 * explanation, and contextual quick links.
 */
function ErrorShell({
  code,
  icon: Icon,
  title,
  body,
  accent,
}: {
  code: string
  icon: React.ComponentType<{ className?: string }>
  title: { en: string; bn: string }
  body: { en: string; bn: string }
  accent: string
}) {
  const lang = useLocale()
  const quickLinks = [
    {
      to: '/',
      label: { en: 'Home', bn: 'হোম' },
      icon: Home,
    },
    {
      to: '/farmer/fields',
      label: { en: 'My fields', bn: 'আমার জমি' },
      icon: MapPin,
    },
    {
      to: '/farmer/analyses',
      label: { en: 'Analyses', bn: 'বিশ্লেষণ' },
      icon: Search,
    },
    {
      to: '/method',
      label: { en: 'Method', bn: 'পদ্ধতি' },
      icon: Compass,
    },
  ]

  return (
    <main className="mx-auto flex min-h-[80vh] max-w-2xl flex-col items-center justify-center px-4 py-16">
      {/* Logo */}
      <img
        src={LOGO}
        alt="AgriFusion BD logo"
        className="mb-6 size-20 rounded-full shadow-md"
      />

      {/* Code badge */}
      <div
        className={`mb-5 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-bold tracking-wide ${accent}`}
      >
        <Icon className="size-4" />
        {code}
      </div>

      {/* Headline */}
      <h1 className="mb-3 text-center text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
        {title[lang]}
      </h1>

      {/* Body */}
      <p className="mb-8 max-w-md text-center text-sm leading-relaxed text-muted-foreground">
        {body[lang]}
      </p>

      {/* Primary action */}
      <Link to="/" className="mb-10">
        <Button size="lg">
          <Home className="size-4" />
          {lang === 'bn' ? 'হোমে ফিরুন' : 'Back to home'}
        </Button>
      </Link>

      {/* Quick links */}
      <div className="w-full">
        <p className="mb-3 text-center text-xs font-medium tracking-wider text-muted-foreground/60 uppercase">
          {lang === 'bn' ? 'দ্রুত লিংক' : 'Quick links'}
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {quickLinks.map(({ to, label, icon: LIcon }) => (
            <Link
              key={to}
              to={to as never}
              className="group flex flex-col items-center gap-1.5 rounded-xl border border-border/60 bg-card p-3 shadow-sm transition-all hover:border-primary/30 hover:bg-accent/30"
            >
              <LIcon className="size-4 text-muted-foreground transition-colors group-hover:text-primary" />
              <span className="text-xs font-medium text-foreground">{label[lang]}</span>
            </Link>
          ))}
        </div>
      </div>
    </main>
  )
}

/* ── 404 ──────────────────────────────────────────────────────────── */

export function NotFound() {
  return (
    <ErrorShell
      code="404"
      icon={Search}
      title={{
        en: 'Page not found',
        bn: 'পেজটি পাওয়া যায়নি',
      }}
      body={{
        en: 'The page you are looking for does not exist or has been moved. Try one of the links below, or head back to the home page.',
        bn: 'আপনি যে পেজটি খুঁজছেন সেটি নেই বা সরিয়ে ফেলা হয়েছে। নিচের যেকোনো লিংক চেষ্টা করুন, অথবা হোম পেজে ফিরে যান।',
      }}
      accent="border-border bg-muted text-muted-foreground"
    />
  )
}

/* ── 500 ──────────────────────────────────────────────────────────── */

export function ServerError() {
  return (
    <ErrorShell
      code="500"
      icon={Wrench}
      title={{
        en: 'Something went wrong',
        bn: 'কিছু একটা ভুল হয়েছে',
      }}
      body={{
        en: 'The server encountered an unexpected error. This is a problem on our side — please try again in a moment. If the issue persists, contact your extension officer or check back later.',
        bn: 'সার্ভারে একটি অনাকাঙ্ক্ষিত ত্রুটি হয়েছে। এটি আমাদের দিক থেকে সমস্যা — অনুগ্রহ করে কিছুক্ষণ পরে আবার চেষ্টা করুন। সমস্যা ধরে থাকলে আপনার সম্প্রসারণ অফিসারকে জানান।',
      }}
      accent="border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
    />
  )
}
