import { Link, useRouterState, useNavigate } from '@tanstack/react-router'
import { Sprout, Languages, FlaskConical } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLocale, setLocale, t } from '#/lib/i18n'
import { currentUser, listFields } from '#/lib/api'
import { useDemoMode } from '#/lib/demo'
import { Button } from '#/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetDescription } from '#/components/ui/sheet'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from '#/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '#/components/ui/avatar'
import { Badge } from '#/components/ui/badge'
import { Separator } from '#/components/ui/separator'

type Workspace = 'farmer' | 'professional'

const NAV: Record<Workspace, Array<{ label: string; path: string; key?: 'fields' | 'analyses' | 'cases' | 'rover' | 'research' | 'jobs' }>> = {
  farmer: [
    { label: 'Fields', path: '/farmer/fields', key: 'fields' },
    { label: 'Analyses', path: '/farmer/analyses', key: 'analyses' },
    { label: 'Cases', path: '/farmer/cases', key: 'cases' },
    { label: 'Rover', path: '/farmer/rover', key: 'rover' },
  ],
  professional: [
    { label: 'Cases', path: '/professional/cases', key: 'cases' },
    { label: 'Research', path: '/professional/research', key: 'research' },
    { label: 'Jobs', path: '/professional/jobs', key: 'jobs' },
  ],
}

function initials(name: string) {
  return name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const navigate = useNavigate()
  // The workspace follows the URL, so the header nav always matches the
  // section the user is actually in (farmer vs professional).
  const workspace: Workspace = pathname.startsWith('/professional') ? 'professional' : 'farmer'
  const [mobileOpen, setMobileOpen] = useState(false)
  const lang = useLocale()
  const user = currentUser()
  const demoMode = useDemoMode()
  const isActive = (p: string) => pathname === p || pathname.startsWith(p + '/')

  // Probe the backend once on mount. On the static site there is no
  // backend, so this fails and the demo fallback switches demo mode on —
  // which is what makes the Demo banner appear on the home page too
  // (the home page itself makes no API calls, so without this probe the
  // banner would only appear after visiting a data page). On a real
  // backend the call succeeds and demo mode stays off.
  useEffect(() => {
    void listFields().catch(() => {})
  }, [])

  const nav = NAV[workspace]

  function switchWorkspace() {
    if (workspace === 'farmer') {
      navigate({ to: '/professional/research' })
    } else {
      navigate({ to: '/farmer/fields' })
    }
  }

  function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
    return (
      <nav className="flex flex-col gap-1" aria-label="Primary">
        {nav.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            onClick={onNavigate}
            aria-current={isActive(item.path) ? 'page' : undefined}
            className={
              'rounded-full px-3.5 py-2 text-sm font-medium transition-all duration-200 ' +
              (isActive(item.path)
                ? 'bg-gradient-to-b from-primary/90 to-primary text-primary-foreground shadow-md shadow-primary/20'
                : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground')
            }
          >
            {t((item.key ?? 'fields'), lang)}
          </Link>
        ))}
      </nav>
    )
  }

  function WorkspaceSwitcher() {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={switchWorkspace}
          aria-label={t('switch_workspace', lang)}
        >
          {workspace === 'farmer' ? 'Professional' : 'Farmer'}
          <span className="ml-1 opacity-60">↔</span>
        </Button>
      </div>
    )
  }

  function UserMenu() {
    if (!user) return null
    return (
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="ghost" size="sm" aria-label="Account menu">
              <Avatar className="size-6">
                <AvatarFallback>{initials(user.name)}</AvatarFallback>
              </Avatar>
              <span className="hidden sm:inline">{user.name.split(' ')[0]}</span>
            </Button>
          }
        />
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <div className="flex flex-col gap-1">
              <span className="font-semibold">{user.name}</span>
              <span className="text-xs text-muted-foreground">
                {user.organization ?? 'Pilot farmer'}
              </span>
              <div className="mt-1 flex flex-wrap gap-1">
                {user.roles.map((r) => (
                  <Badge key={r} variant="secondary" className="text-[10px]">
                    {r.replace('_', ' ')}
                  </Badge>
                ))}
              </div>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setLocale(lang === 'en' ? 'bn' : 'en')}>
            <Languages className="size-4" />
            {lang === 'en' ? 'বাংলায় দেখুন' : 'Switch to English'}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <div className="aurora" aria-hidden="true">
        <span className="orb orb--a" />
        <span className="orb orb--b" />
        <span className="orb orb--c" />
      </div>
      <div className="grid-overlay" aria-hidden="true" />
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/70 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
          <Link to="/" className="group flex items-center gap-2 font-semibold">
            <span className="flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/70 text-primary-foreground shadow-lg shadow-primary/20 transition-transform duration-300 group-hover:scale-105 group-hover:rotate-3">
              <Sprout className="size-4" />
            </span>
            <span className="hidden bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent sm:inline">
              {t('app_name', lang)}
            </span>
          </Link>

          {/* Desktop nav */}
          <div className="ml-2 hidden md:flex md:items-center md:gap-1">
            {nav.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                aria-current={isActive(item.path) ? 'page' : undefined}
                className={
                  'rounded-full px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ' +
                  (isActive(item.path)
                    ? 'bg-gradient-to-b from-primary/90 to-primary text-primary-foreground shadow-md shadow-primary/20'
                    : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground')
                }
              >
                {t((item.key ?? 'fields'), lang)}
              </Link>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setLocale(lang === 'en' ? 'bn' : 'en')}
              aria-label="Switch language"
            >
              <Languages className="size-4" />
              <span className="hidden sm:inline">{lang === 'en' ? 'BN' : 'EN'}</span>
            </Button>
            <WorkspaceSwitcher />
            <UserMenu />
          </div>

          {/* Mobile trigger */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger
              render={
                <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                  ☰
                </Button>
              }
            />
            <SheetContent side="left" className="w-72">
              <SheetHeader>
                <SheetTitle>{t('app_name', lang)}</SheetTitle>
                <SheetDescription>{t('tagline', lang)}</SheetDescription>
              </SheetHeader>
              <Separator className="my-4" />
              <NavLinks onNavigate={() => setMobileOpen(false)} />
              <Separator className="my-4" />
              <div className="flex flex-col gap-2 px-2">
                <WorkspaceSwitcher />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      {demoMode && (
        <div className="border-b border-amber-300/60 bg-amber-100/90 px-4 py-2 text-center text-xs font-medium text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/80 dark:text-amber-200" role="status">
          <span className="inline-flex items-center gap-1.5">
            <FlaskConical className="size-3.5" />
            {lang === 'bn'
              ? 'ডেমো মোড — ব্যাকএন্ড সংযুক্ত নেই, তাই নমুনা তথ্য দেখানো হচ্ছে। আপনার আঁকা জমি এই ডিভাইসে সংরক্ষিত হয়।'
              : 'Demo mode — the backend is not connected, so you are seeing sample data. Lands you draw are saved on this device.'}
          </span>
        </div>
      )}

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>
            {t('app_name', lang)} · Bangladesh pilot · Design baseline 1.0
          </p>
          <p className="max-w-2xl">
            {t('disclaimer', lang)}
          </p>
        </div>
      </footer>
    </div>
  )
}
