import { createFileRoute, Link } from '@tanstack/react-router'
import { Satellite, Bot, Scale, Globe2, ShieldCheck, ArrowRight, Check, Layers, Compass } from 'lucide-react'
import { useLocale, t } from '#/lib/i18n'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '#/components/ui/card'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  const lang = useLocale()

  const features = [
    {
      icon: Satellite,
      title: lang === 'bn' ? 'NASA পর্যবেক্ষণ' : 'NASA observations',
      body:
        lang === 'bn'
          ? 'POWER বৃষ্টিপাত, তাপমাত্রা এবং HLS সালোকসংশ্লেষণ তথ্য — আবরণ ও এককসহ।'
          : 'POWER rainfall and temperature, plus HLS vegetation — with coverage and units.',
    },
    {
      icon: Scale,
      title: lang === 'bn' ? 'ফসল চক্র তুলনা' : 'Rotation comparison',
      body:
        lang === 'bn'
          ? 'আপনার বর্তমান চক্র এবং দুটি স্থানীয়ভাবে বাস্তবায়নযোগ্য বিকল্প — প্রমাণ ও সীমাবদ্ধতা সহ।'
          : 'Your existing rotation and two locally feasible alternatives — with evidence and constraints.',
    },
    {
      icon: Bot,
      title: lang === 'bn' ? 'রোভার প্রমাণ' : 'Rover evidence',
      body:
        lang === 'bn'
          ? 'স্থানীয় আর্দ্রতা, তাপমাত্রা ও EC পঠন — দৃষ্টিসীমা ও মান যাচাইসহ।'
          : 'Local moisture, temperature and EC readings — with quality and calibration checks.',
    },
    {
      icon: Globe2,
      title: lang === 'bn' ? 'বাংলা ও ইংরেজি' : 'Bangla & English',
      body:
        lang === 'bn'
          ? 'দুই ভাষায়, কম ব্যান্ডউইথের জন্য পাঠযোগ্য রিপোর্ট।'
          : 'Bilingual, with low-bandwidth readable reports.',
    },
  ]

  const stats = [
    { k: lang === 'bn' ? 'জমি' : 'Fields', v: '3' },
    { k: lang === 'bn' ? 'ফসল' : 'Crops', v: '6' },
    { k: lang === 'bn' ? 'রোভার' : 'Rovers', v: '2' },
    { k: lang === 'bn' ? 'ভাষা' : 'Languages', v: '2' },
  ]

  const steps = [
    { icon: Compass, title: lang === 'bn' ? 'জমি বাছাই' : 'Pick a field', body: lang === 'bn' ? 'সীমানা বা পিন থেকে শুরু করুন।' : 'Start from a boundary or a pin.' },
    { icon: Layers, title: lang === 'bn' ? 'তুলনা তৈরি' : 'Build the comparison', body: lang === 'bn' ? 'বেসলাইন + দুটি বিকল্প, প্রমাণসহ।' : 'Baseline + two alternatives, with evidence.' },
    { icon: Check, title: lang === 'bn' ? 'সিদ্ধান্ত নিন' : 'Decide with confidence', body: lang === 'bn' ? 'অফিসার ও গবেষকদের সাথে ভাগ করুন।' : 'Share with officers & researchers.' },
  ]

  return (
    <main className="mx-auto max-w-6xl px-4 py-12 sm:py-16">
      <section className="rise-in relative mb-12">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full glass border border-border/80 px-3.5 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
          <span className="relative flex size-2 items-center justify-center text-primary">
            <span className="pulse-dot size-2 rounded-full bg-primary" />
          </span>
          {t('tagline', lang)} · {lang === 'bn' ? 'বাংলাদেশ পাইলট' : 'Bangladesh pilot'}
        </div>
        <h1 className="max-w-4xl text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
          <span className="text-gradient">
            {lang === 'bn'
              ? 'ফসল চক্রের সিদ্ধান্তে'
              : 'Evidence-based help for'}
          </span>
          <br />
          <span className="text-foreground">
            {lang === 'bn' ? 'প্রমাণভিত্তিক সহায়তা' : 'crop rotation decisions'}
          </span>
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-muted-foreground">
          {lang === 'bn'
            ? 'FieldShift আপনার বর্তমান ফসল চক্রকে স্থানীয়ভাবে সম্ভাব্য দুটি বিকল্পের সাথে তুলনা করে — NASA পর্যবেক্ষণ, স্থানীয় কৃষি নির্দেশনা এবং ঐচ্ছিক রোভার পঠন একত্র করে।'
            : 'FieldShift compares your current crop rotation against two locally feasible alternatives — combining NASA observations, local agronomy guidance and optional rover measurements.'}
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link to="/farmer/fields">
            <button className="btn-glow inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-lg transition-transform duration-200 hover:scale-[1.02]">
              {t('nav_farmer', lang)} workspace
              <ArrowRight className="size-4" />
            </button>
          </Link>
          <Link to="/professional/research">
            <button className="glass inline-flex items-center gap-2 rounded-xl border border-border/80 px-6 py-3 text-sm font-semibold text-foreground shadow-sm transition-all duration-200 hover:border-primary/40 hover:bg-accent/40">
              {t('nav_professional', lang)} workspace
            </button>
          </Link>
        </div>

        <div className="mt-10 grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
          {stats.map((s) => (
            <div key={s.k} className="glass lift rounded-2xl border border-border/70 p-4 shadow-sm">
              <div className="text-2xl font-bold tracking-tight text-foreground">{s.v}</div>
              <div className="mt-0.5 text-xs font-medium text-muted-foreground">{s.k}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {features.map((f, i) => (
          <Card key={i} className="lift group glass overflow-hidden border-border/70 shadow-md">
            <CardHeader className="relative">
              <div className="mb-3 flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 ring-1 ring-primary/20 transition-all duration-300 group-hover:scale-110 group-hover:ring-primary/40">
                <f.icon className="size-6 text-primary" />
              </div>
              <CardTitle className="text-base font-semibold">{f.title}</CardTitle>
              <CardDescription className="leading-relaxed">{f.body}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </section>

      <section className="mt-10">
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-lg font-semibold text-foreground">
            {lang === 'bn' ? 'যেভাবে কাজ করে' : 'How it works'}
          </h2>
          <span className="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {steps.map((s, i) => (
            <div key={i} className="lift relative glass rounded-2xl border border-border/70 p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <s.icon className="size-5" />
                </span>
                <span className="text-xs font-bold tracking-widest text-muted-foreground/70">
                  {String(i + 1).padStart(2, '0')}
                </span>
              </div>
              <div className="font-semibold text-foreground">{s.title}</div>
              <div className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.body}</div>
            </div>
          ))}
        </div>
      </section>

      <Card className="mt-10 border-dashed border-border/80">
        <CardContent className="flex flex-col gap-3 p-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10">
              <ShieldCheck className="size-5 text-primary" />
            </div>
            <div>
              <p className="font-medium text-foreground">{t('disclaimer', lang)}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {lang === 'bn'
                  ? 'এটি একটি নকশা-ভিত্তিক প্রদর্শন; বাস্তব ফলন বা লাভের প্রতিশ্রুতি নয়।'
                  : 'This is a design-baseline demonstration; it is not a promise of real yield or profit.'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
