// Professional — Rover paths. When a rover request comes in, the
// professional sets the path the rover should follow to gauge the field
// and collect data. Two ways to make a path:
//  1. Select a field — a lawnmower (serpentine) path is auto-generated
//     across it, so the rover covers the whole field.
//  2. Draw on the map — click points to lay out a custom path.
// Saved paths live in this browser on the demo site; a real backend would
// send the path to the rover.
import { createFileRoute } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { Bot, MapPin, Route as RouteIcon, Undo2, Trash2, Play, Check, Save, Send, Clock } from 'lucide-react'
import { currentUser, listFields } from '#/lib/api'
import { useLocale, t } from '#/lib/i18n'
import type { Field, RoverPath, RoverRequest } from '#/lib/types'
import type { LngLat } from '#/lib/geo'
import {
  loadRoverPaths,
  saveRoverPath,
  deleteRoverPath,
  updateRoverPathStatus,
  generateSerpentinePath,
  pathLengthM,
  formatPathLength,
  loadRoverRequests,
  linkPathToRequest,
} from '#/lib/roverPaths'
import RoverPathMap from '#/components/rover/RoverPathMap'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { toast } from 'sonner'

export const Route = createFileRoute('/professional/rover-paths')({ component: RoverPathsPage })

type Mode = 'field' | 'custom'

const STATUS_CLS: Record<RoverPath['status'], string> = {
  planned: 'border-sky-300 bg-sky-100 text-sky-800',
  assigned: 'border-amber-300 bg-amber-100 text-amber-800',
  completed: 'border-emerald-300 bg-emerald-100 text-emerald-800',
}

const STATUS_LABEL: Record<RoverPath['status'], { en: string; bn: string }> = {
  planned: { en: 'Planned', bn: 'পরিকল্পিত' },
  assigned: { en: 'Assigned', bn: 'বরাদ্দ' },
  completed: { en: 'Completed', bn: 'সম্পন্ন' },
}

const REQUEST_STATUS: Record<RoverRequest['status'], { en: string; bn: string; cls: string }> = {
  requested: { en: 'Requested', bn: 'অনুরোধ করা হয়েছে', cls: 'border-sky-300 bg-sky-100 text-sky-800' },
  path_assigned: { en: 'Path assigned', bn: 'পথ নির্ধারিত', cls: 'border-amber-300 bg-amber-100 text-amber-800' },
  completed: { en: 'Completed', bn: 'সম্পন্ন', cls: 'border-emerald-300 bg-emerald-100 text-emerald-800' },
}

export default function RoverPathsPage() {
  const lang = useLocale()
  const [fields, setFields] = useState<Field[]>([])
  const [paths, setPaths] = useState<RoverPath[]>([])
  const [requests, setRequests] = useState<RoverRequest[]>([])
  const [mode, setMode] = useState<Mode>('field')
  const [selectedFieldId, setSelectedFieldId] = useState<string>('')
  const [spacingM, setSpacingM] = useState(8)
  const [customPoints, setCustomPoints] = useState<LngLat[]>([])
  const [pathName, setPathName] = useState('')

  useEffect(() => {
    listFields().then(setFields).catch(() => setFields([]))
    setPaths(loadRoverPaths())
    setRequests(loadRoverRequests())
  }, [])

  const selectedField = fields.find((f) => f.id === selectedFieldId)

  // Field mode: the path is the lawnmower pattern across the selected field.
  const fieldPath = useMemo(() => {
    if (mode !== 'field' || !selectedField) return []
    return generateSerpentinePath(selectedField.geometry.coordinates[0] as LngLat[], spacingM)
  }, [mode, selectedField, spacingM])

  const points = mode === 'field' ? fieldPath : customPoints
  const lengthM = useMemo(() => pathLengthM(points), [points])

  function handleFieldClick(id: string) {
    setMode('field')
    setSelectedFieldId(id)
    setCustomPoints([])
  }

  function handleMapClick(lngLat: LngLat) {
    if (mode !== 'custom') {
      setMode('custom')
      setSelectedFieldId('')
    }
    setCustomPoints((prev) => [...prev, lngLat])
  }

  function handleSave() {
    if (points.length < 2) {
      toast.error(lang === 'bn' ? 'পথ তৈরি করতে অন্তত ২টি বিন্দু দিন।' : 'A path needs at least 2 points.')
      return
    }
    const fieldName = selectedField?.name
    const name =
      pathName.trim() ||
      (fieldName
        ? lang === 'bn' ? `${fieldName} — রোভার পথ` : `Rover path — ${fieldName}`
        : lang === 'bn' ? `কাস্টম পথ ${paths.length + 1}` : `Custom path ${paths.length + 1}`)
    const user = currentUser()
    const path: RoverPath = {
      id: `path-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`,
      name,
      fieldId: selectedField?.id,
      fieldName,
      points: points.map(([lng, lat]) => [lng, lat] as [number, number]),
      lengthM: Math.round(lengthM),
      status: 'planned',
      createdBy: user?.name ?? 'Professional',
      createdAt: new Date().toISOString(),
    }
    setPaths(saveRoverPath(path))
    // If a farmer asked for rover analysis on this field, the new path
    // answers that request — link it and move the request to "path assigned".
    if (path.fieldId) setRequests(linkPathToRequest(path.fieldId, path.id))
    setPathName('')
    setCustomPoints([])
    toast.success(lang === 'bn' ? 'রোভার পথ সংরক্ষণ করা হয়েছে।' : 'Rover path saved.')
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <RouteIcon className="size-6 text-primary" />
          {lang === 'bn' ? 'রোভার পথ' : 'Rover paths'}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'রোভার অনুরোধ এলে পথ নির্ধারণ করুন — জমি বেছে নিলে রোভার পুরো জমি ঘুরে তথ্য সংগ্রহ করবে, অথবা মানচিত্রে নিজে বিন্দু বসিয়ে কাস্টম পথ আঁকুন।'
            : 'When a rover request comes in, set the path the rover should follow to gauge the field and collect data — pick a field and the rover covers the whole field, or click points on the map for a custom path.'}
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-5">
        {/* Builder */}
        <Card className="lg:col-span-3" id="rp-builder">
          <CardHeader>
            <CardTitle className="text-base">{lang === 'bn' ? 'নতুন পথ তৈরি করুন' : 'Create a new path'}</CardTitle>
            <CardDescription>
              {lang === 'bn'
                ? 'জমি বেছে নিন অথবা মানচিত্রে ক্লিক করে বিন্দু বসান।'
                : 'Pick a field, or click points on the map.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={mode === 'field' ? 'default' : 'outline'}
                onClick={() => { setMode('field'); setCustomPoints([]) }}
                className="flex-1"
              >
                <MapPin className="size-4" /> {lang === 'bn' ? 'জমি বেছে নিন' : 'Select a field'}
              </Button>
              <Button
                size="sm"
                variant={mode === 'custom' ? 'default' : 'outline'}
                onClick={() => { setMode('custom'); setSelectedFieldId('') }}
                className="flex-1"
              >
                <RouteIcon className="size-4" /> {lang === 'bn' ? 'মানচিত্রে আঁকুন' : 'Draw on map'}
              </Button>
            </div>

            {mode === 'field' && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="rp-field" className="text-xs font-medium text-muted-foreground">
                    {lang === 'bn' ? 'জমি' : 'Field'}
                  </label>
                  <select
                    id="rp-field"
                    value={selectedFieldId}
                    onChange={(e) => setSelectedFieldId(e.target.value)}
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
                  >
                    <option value="">{lang === 'bn' ? 'জমি বেছে নিন' : 'Choose a field'}</option>
                    {fields.map((f) => (
                      <option key={f.id} value={f.id}>{f.name} · {f.areaHa} ha</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="rp-spacing" className="text-xs font-medium text-muted-foreground">
                    {lang === 'bn' ? 'পাসের দূরত্ব' : 'Pass spacing'}
                  </label>
                  <select
                    id="rp-spacing"
                    value={spacingM}
                    onChange={(e) => setSpacingM(Number(e.target.value))}
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
                  >
                    <option value={5}>5 m — {lang === 'bn' ? 'ঘন' : 'dense'}</option>
                    <option value={8}>8 m — {lang === 'bn' ? 'সাধারণ' : 'standard'}</option>
                    <option value={12}>12 m — {lang === 'bn' ? 'হালকা' : 'light'}</option>
                  </select>
                </div>
              </div>
            )}

            <div className="h-[340px] w-full">
              <RoverPathMap
                fields={fields}
                selectedFieldId={selectedFieldId || undefined}
                points={points}
                onFieldClick={handleFieldClick}
                onMapClick={handleMapClick}
              />
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span className="font-medium text-foreground">
                {points.length} {lang === 'bn' ? 'টি বিন্দু' : 'waypoints'}
              </span>
              <span className="text-muted-foreground">
                {lang === 'bn' ? 'মোট দৈর্ঘ্য: ' : 'Total length: '}
                <span className="font-medium text-foreground">{formatPathLength(lengthM)}</span>
              </span>
              {mode === 'custom' && customPoints.length > 0 && (
                <span className="ml-auto flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setCustomPoints((p) => p.slice(0, -1))}>
                    <Undo2 className="size-3.5" /> {lang === 'bn' ? 'পূর্বাবস্থা' : 'Undo'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setCustomPoints([])}>
                    <Trash2 className="size-3.5" /> {lang === 'bn' ? 'মুছুন' : 'Clear'}
                  </Button>
                </span>
              )}
            </div>

            <div className="flex gap-2">
              <Input
                value={pathName}
                onChange={(e) => setPathName(e.target.value)}
                placeholder={lang === 'bn' ? 'পথের নাম (ঐচ্ছিক)' : 'Path name (optional)'}
              />
              <Button onClick={handleSave} disabled={points.length < 2}>
                <Save className="size-4" /> {lang === 'bn' ? 'পথ সংরক্ষণ করুন' : 'Save path'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {lang === 'bn'
                ? 'ডেমো: পথগুলো এই ব্রাউজারে সংরক্ষণ করা হয়। আসল ব্যবস্থায় পথটি রোভারে পাঠানো হবে।'
                : 'Demo: paths are saved in this browser. In the real system the path is sent to the rover.'}
            </p>
          </CardContent>
        </Card>

        {/* Saved paths + incoming farmer requests */}
        <div className="flex flex-col gap-3 lg:col-span-2">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Send className="size-5 text-primary" />
            {lang === 'bn' ? 'কৃষকের অনুরোধ' : 'Farmer requests'} ({requests.filter((r) => r.status !== 'completed').length})
          </h2>
          {requests.length === 0 && (
            <Card>
              <CardContent className="py-6 text-sm text-muted-foreground">
                {lang === 'bn'
                  ? 'এখনো কোনো রোভার অনুরোধ আসেনি। কৃষক তার যেকোনো নিবন্ধিত জমির জন্য রোভার বিশ্লেষণ চাইতে পারেন।'
                  : 'No rover requests yet. A farmer can ask for rover analysis on any of their registered fields.'}
              </CardContent>
            </Card>
          )}
          {requests.map((r) => {
            const st = REQUEST_STATUS[r.status]
            return (
              <Card key={r.id}>
                <CardContent className="flex flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Bot className="size-4 shrink-0 text-primary" />
                      <p className="font-medium text-foreground">{r.fieldName}</p>
                    </div>
                    <Badge variant="outline" className={st.cls}>{st[lang]}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {lang === 'bn' ? 'কৃষক: ' : 'Farmer: '}{r.farmerName}
                    {r.note ? ` — ${r.note}` : ''} ·{' '}
                    <span className="inline-flex items-center gap-1"><Clock className="size-3" /> {new Date(r.createdAt).toISOString().slice(0, 10)}</span>
                  </p>
                  {r.status === 'requested' && (
                    <div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setMode('field')
                          setSelectedFieldId(r.fieldId)
                          setCustomPoints([])
                          document.getElementById('rp-builder')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                        }}
                      >
                        <RouteIcon className="size-3.5" /> {lang === 'bn' ? 'এই জমির পথ তৈরি করুন' : 'Set path for this field'}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}

          <h2 className="mt-2 text-lg font-semibold text-foreground">
            {lang === 'bn' ? 'সংরক্ষিত পথ' : 'Saved paths'} ({paths.length})
          </h2>
          {paths.length === 0 && (
            <Card>
              <CardContent className="py-6 text-sm text-muted-foreground">
                {lang === 'bn'
                  ? 'এখনো কোনো পথ তৈরি হয়নি। উপরে একটি জমি বেছে নিন অথবা মানচিত্রে বিন্দু বসান।'
                  : 'No paths yet. Pick a field above, or click points on the map.'}
              </CardContent>
            </Card>
          )}
          {paths.map((p) => (
            <Card key={p.id}>
              <CardContent className="flex flex-col gap-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Bot className="size-4 shrink-0 text-primary" />
                    <p className="font-medium text-foreground">{p.name}</p>
                  </div>
                  <Badge variant="outline" className={STATUS_CLS[p.status]}>
                    {STATUS_LABEL[p.status][lang]}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {p.fieldName ? `${p.fieldName} · ` : ''}
                  {p.points.length} {lang === 'bn' ? 'টি বিন্দু' : 'waypoints'} · {formatPathLength(p.lengthM)} ·{' '}
                  {lang === 'bn' ? 'তৈরি: ' : 'By '}{p.createdBy}
                </p>
                <div className="flex gap-2">
                  {p.status === 'planned' && (
                    <Button size="sm" variant="outline" onClick={() => setPaths(updateRoverPathStatus(p.id, 'assigned'))}>
                      <Play className="size-3.5" /> {lang === 'bn' ? 'রোভারে পাঠান' : 'Assign to rover'}
                    </Button>
                  )}
                  {p.status === 'assigned' && (
                    <Button size="sm" variant="outline" onClick={() => setPaths(updateRoverPathStatus(p.id, 'completed'))}>
                      <Check className="size-3.5" /> {lang === 'bn' ? 'সম্পন্ন চিহ্নিত করুন' : 'Mark completed'}
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => setPaths(deleteRoverPath(p.id))}>
                    <Trash2 className="size-3.5" /> {lang === 'bn' ? 'মুছুন' : 'Delete'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </main>
  )
}
