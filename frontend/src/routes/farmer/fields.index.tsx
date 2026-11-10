import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { MapPin, Ruler, Droplets, Wheat, MapPinned, PenLine, Trash2, Satellite, Sprout } from 'lucide-react'
import { listFields, getFieldIndicators, createField, deleteField } from '#/lib/api'
import { getSeasonReport, getForecast } from '#/lib/advisory'
import { fieldPhoto } from '#/lib/images'
import SeasonReport from '#/components/advisory/SeasonReport'
import ForecastCard from '#/components/advisory/ForecastCard'
import SmsPanel from '#/components/advisory/SmsPanel'
import { useLocale, t } from '#/lib/i18n'
import type { Field } from '#/lib/types'
import FieldMap, { type DrawPreview } from '#/components/fields/FieldMap'
import {
  geodesicAreaSqM,
  polygonCentroid,
  areaUnits,
  formatCoord,
  formatAreaLine,
  loadLocalFields,
  saveLocalField,
  deleteLocalField,
  isLocalField,
  fieldFromRing,
  type LngLat,
} from '#/lib/geo'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '#/components/ui/card'
import { Badge } from '#/components/ui/badge'
import { Button } from '#/components/ui/button'
import { Input } from '#/components/ui/input'
import { Progress } from '#/components/ui/progress'
import { Separator } from '#/components/ui/separator'

export const Route = createFileRoute('/farmer/fields/')({ component: FieldsPage })

const IRRIGATION_OPTIONS: Array<{ value: Field['irrigation']; en: string; bn: string }> = [
  { value: 'rainfed', en: 'Rainfed', bn: 'বৃষ্টিনির্ভর' },
  { value: 'canal', en: 'Canal', bn: 'খাল' },
  { value: 'pump', en: 'Pump', bn: 'পাম্প' },
  { value: 'tubewell', en: 'Tubewell', bn: 'নলকূপ' },
]

export default function FieldsPage() {
  const lang = useLocale()
  const navigate = useNavigate()
  const [fields, setFields] = useState<Field[]>([])
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [indicators, setIndicators] = useState<Record<string, { coverage: number }>>({})

  // Drawing a new land boundary.
  const [drawMode, setDrawMode] = useState(false)
  const [drawPreview, setDrawPreview] = useState<DrawPreview | null>(null)
  const [pendingRing, setPendingRing] = useState<LngLat[] | null>(null)
  const [landName, setLandName] = useState('')
  const [irrigation, setIrrigation] = useState<Field['irrigation']>('rainfed')
  const [currentCrops, setCurrentCrops] = useState('')
  const [recentCrops, setRecentCrops] = useState('')
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  // Lands come from the backend when it is reachable; lands drawn on the
  // static site are kept in this browser and merged in.
  useEffect(() => {
    const local = loadLocalFields()
    listFields()
      .then((apiFields) => {
        const localIds = new Set(local.map((f) => f.id))
        setFields([...apiFields.filter((f) => !localIds.has(f.id)), ...local])
      })
      .catch(() => {
        setFields(local)
      })
  }, [])

  useEffect(() => {
    if (!selectedId) return
    getFieldIndicators(selectedId).then((inds) => {
      const hls = inds.filter((i) => i.kind === 'hls_vi')
      const avg = hls.length ? Math.round(hls.reduce((s, i) => s + i.coveragePct, 0) / hls.length) : 0
      setIndicators((prev) => ({ ...prev, [selectedId]: { coverage: avg } }))
    }).catch(() => { /* indicators are optional on the demo site */ })
  }, [selectedId])

  const selected = fields.find((f) => f.id === selectedId)
  const stats = useMemo(() => {
    if (!selected) return null
    const cov = indicators[selected.id]?.coverage ?? 0
    return { area: selected.areaHa, cov }
  }, [selected, indicators])

  const totalHa = useMemo(() => fields.reduce((s, f) => s + (f.areaHa || 0), 0), [fields])
  const totalUnits = useMemo(() => areaUnits(totalHa * 10_000), [totalHa])

  const selectedCentroid = useMemo(() => {
    if (!selected) return null
    return polygonCentroid(selected.geometry.coordinates[0])
  }, [selected])

  const pendingAreaSqM = pendingRing ? geodesicAreaSqM(pendingRing) : 0
  const pendingCentroid = pendingRing ? polygonCentroid(pendingRing) : null

  const handleDrawComplete = (ring: LngLat[]) => {
    setPendingRing(ring)
    setDrawMode(false)
    setDrawPreview(null)
    setLandName(lang === 'bn' ? `জমি ${fields.length + 1}` : `Land ${fields.length + 1}`)
    setNotice(null)
  }

  const handleSaveLand = async () => {
    if (!pendingRing) return
    const name = landName.trim() || (lang === 'bn' ? `জমি ${fields.length + 1}` : `Land ${fields.length + 1}`)
    const areaHa = Math.round((pendingAreaSqM / 10_000) * 100) / 100
    const closed: LngLat[] = pendingRing.slice()
    if (closed[0][0] !== closed[closed.length - 1][0] || closed[0][1] !== closed[closed.length - 1][1]) {
      closed.push(closed[0])
    }
    // Crop cycles the farmer typed, comma-separated — these ground the
    // season report and rotation advice for this field.
    const currentCycleCrops = currentCrops.split(',').map((s) => s.trim()).filter(Boolean)
    const recentCycleCrops = recentCrops.split(',').map((s) => s.trim()).filter(Boolean)
    setSaving(true)
    try {
      const created = await createField({
        name,
        geometry: { type: 'Polygon', coordinates: [closed] },
        areaHa,
        irrigation,
        currentCycleCrops: currentCycleCrops.length ? currentCycleCrops : undefined,
        recentCycleCrops: recentCycleCrops.length ? recentCycleCrops : undefined,
      })
      setFields((prev) => [...prev, created])
      setSelectedId(created.id)
      setNotice(lang === 'bn' ? 'জমি সংরক্ষণ করা হয়েছে।' : 'Land saved to your account.')
    } catch {
      // No backend on the static site — keep the land in this browser.
      const local = fieldFromRing(pendingRing, name, irrigation, { current: currentCycleCrops, recent: recentCycleCrops })
      saveLocalField(local)
      setFields((prev) => [...prev, local])
      setSelectedId(local.id)
      setNotice(
        lang === 'bn'
          ? 'ব্যাকএন্ড সংযোগ নেই — জমিটি এই ব্রাউজারে সংরক্ষণ করা হয়েছে।'
          : 'No backend connection — land saved on this device. It stays in this browser.',
      )
    } finally {
      setSaving(false)
      setPendingRing(null)
      setDrawPreview(null)
      setCurrentCrops('')
      setRecentCrops('')
    }
  }

  const handleDelete = async (field: Field) => {
    if (isLocalField(field)) {
      deleteLocalField(field.id)
      setFields((prev) => prev.filter((f) => f.id !== field.id))
      if (selectedId === field.id) setSelectedId(undefined)
      return
    }
    try {
      await deleteField(field.id)
      setFields((prev) => prev.filter((f) => f.id !== field.id))
      if (selectedId === field.id) setSelectedId(undefined)
    } catch {
      setNotice(
        lang === 'bn'
          ? 'সার্ভার থেকে মুছতে পারা যায়নি। ব্যাকএন্ড চালু থাকলে আবার চেষ্টা করুন।'
          : 'Could not delete from the server. Try again when the backend is reachable.',
      )
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-6 flex flex-col gap-2">
        <h1 className="text-2xl font-bold text-foreground">{t('fields', lang)}</h1>
        <p className="text-sm text-muted-foreground">
          {lang === 'bn'
            ? 'আপনার জমির তালিকা। স্যাটেলাইট ম্যাপে জমির চারপাশে রেখা টেনে নতুন জমি যোগ করুন — যতগুলো খুশি।'
            : 'Your fields. Draw a line around a plot on the satellite map to add it — as many as you like.'}
        </p>
        <p className="text-sm font-medium text-foreground">
          {lang === 'bn' ? 'মোট জমি: ' : 'Total land: '}
          {totalHa.toFixed(2)} ha · {totalUnits.acre.toFixed(2)} acre · {totalUnits.bigha.toFixed(2)} bigha
          {fields.length > 0 && ` (${fields.length} ${fields.length === 1 ? (lang === 'bn' ? 'টি জমি' : 'land') : (lang === 'bn' ? 'টি জমি' : 'lands')})`}
        </p>
      </header>

      {notice && (
        <div className="mb-4 rounded-xl border border-border bg-card px-4 py-3 text-sm text-foreground" role="status">
          {notice}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Satellite className="size-4 text-primary" />
                  {lang === 'bn' ? 'জমি ম্যাপ' : 'Field map'}
                </CardTitle>
                <CardDescription>
                  {drawMode
                    ? lang === 'bn'
                      ? 'জমির প্রতিটি কোণে ক্লিক করুন, তারপর শেষ করুন'
                      : 'Click each corner of your land, then finish'
                    : lang === 'bn'
                      ? 'জমি নির্বাচন করতে ক্লিক করুন, বা নতুন জমি আঁকুন'
                      : 'Click a field to select it, or draw a new one'}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="gap-1"><MapPinned className="size-3.5" /> {fields.length}</Badge>
                <Button
                  size="sm"
                  variant={drawMode ? 'secondary' : 'default'}
                  onClick={() => {
                    setPendingRing(null)
                    setDrawMode((v) => !v)
                  }}
                >
                  <PenLine className="mr-1 size-3.5" />
                  {drawMode
                    ? lang === 'bn' ? 'আঁকা বন্ধ করুন' : 'Stop drawing'
                    : lang === 'bn' ? 'জমি আঁকুন' : 'Draw land'}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="h-[420px] w-full">
                <FieldMap
                  fields={fields}
                  selectedId={selectedId}
                  onSelect={(id) => setSelectedId(id)}
                  drawMode={drawMode}
                  onDrawPreview={(p) => setDrawPreview(p)}
                  onDrawComplete={handleDrawComplete}
                  onDrawCancel={() => {
                    setDrawMode(false)
                    setDrawPreview(null)
                  }}
                  className="rounded-xl"
                />
              </div>
              {drawMode && drawPreview && drawPreview.points.length > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {lang === 'bn' ? 'এখন পর্যন্ত: ' : 'So far: '}
                  {drawPreview.points.length} {lang === 'bn' ? 'কোণ' : 'corners'}
                  {drawPreview.points.length >= 3 && ` · ${formatAreaLine(drawPreview.areaSqM)}`}
                  {drawPreview.cursor && (
                    <> · {formatCoord(drawPreview.cursor.lat)}, {formatCoord(drawPreview.cursor.lng)}</>
                  )}
                </p>
              )}
            </CardContent>
          </Card>

          {pendingRing && pendingCentroid && (
            <Card className="mt-4 border-primary/40">
              <CardHeader>
                <CardTitle className="text-base">{lang === 'bn' ? 'নতুন জমি সংরক্ষণ করুন' : 'Save this land'}</CardTitle>
                <CardDescription>
                  {lang === 'bn' ? 'সীমানা আঁকা শেষ। নাম দিন ও সংরক্ষণ করুন।' : 'Boundary drawn. Give it a name and save it.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="land-name" className="text-xs font-medium text-muted-foreground">
                      {lang === 'bn' ? 'জমির নাম' : 'Land name'}
                    </label>
                    <Input
                      id="land-name"
                      value={landName}
                      onChange={(e) => setLandName(e.target.value)}
                      placeholder={lang === 'bn' ? 'যেমন: উত্তর প্লট' : 'e.g. North plot'}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="land-irrigation" className="text-xs font-medium text-muted-foreground">
                      {lang === 'bn' ? 'সেচ' : 'Irrigation'}
                    </label>
                    <select
                      id="land-irrigation"
                      value={irrigation}
                      onChange={(e) => setIrrigation(e.target.value as Field['irrigation'])}
                      className="h-9 rounded-md border border-input bg-background px-3 text-sm outline-none"
                    >
                      {IRRIGATION_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{lang === 'bn' ? o.bn : o.en}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="land-current-crops" className="text-xs font-medium text-muted-foreground">
                      {lang === 'bn' ? 'বর্তমান চক্রের ফসল' : 'Current cycle crop(s)'}
                    </label>
                    <Input
                      id="land-current-crops"
                      value={currentCrops}
                      onChange={(e) => setCurrentCrops(e.target.value)}
                      placeholder={lang === 'bn' ? 'যেমন: টি. আমন, সরিষা' : 'e.g. T. Aman, Mustard'}
                    />
                    <p className="text-[11px] text-muted-foreground">
                      {lang === 'bn' ? 'একাধিক ফসল কমা দিয়ে আলাদা করুন।' : 'Separate multiple crops with commas.'}
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="land-recent-crops" className="text-xs font-medium text-muted-foreground">
                      {lang === 'bn' ? 'সাম্প্রতিক চক্রের ফসল' : 'Recent cycle crop(s)'}
                    </label>
                    <Input
                      id="land-recent-crops"
                      value={recentCrops}
                      onChange={(e) => setRecentCrops(e.target.value)}
                      placeholder={lang === 'bn' ? 'যেমন: বোরো' : 'e.g. Boro'}
                    />
                    <p className="text-[11px] text-muted-foreground">
                      {lang === 'bn' ? 'আগের চক্রে যা চাষ হয়েছিল।' : 'What was grown in the previous cycle.'}
                    </p>
                  </div>
                </div>
                <div className="rounded-lg bg-muted/60 px-3 py-2 text-xs leading-relaxed">
                  <p className="font-medium text-foreground">{formatAreaLine(pendingAreaSqM)}</p>
                  <p className="text-muted-foreground">
                    {lang === 'bn' ? 'কেন্দ্র: ' : 'Centre: '}
                    <span className="tabular-nums">{formatCoord(pendingCentroid.lat)}, {formatCoord(pendingCentroid.lng)}</span>
                    {' · '}
                    {pendingRing.length} {lang === 'bn' ? 'টি কোণ' : 'corners'}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => void handleSaveLand()} disabled={saving} className="flex-1">
                    {saving ? '…' : lang === 'bn' ? 'সংরক্ষণ করুন' : 'Save land'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setPendingRing(null)} className="flex-1">
                    {lang === 'bn' ? 'বাতিল করুন' : 'Discard'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="lg:col-span-2">
          <div className="flex flex-col gap-3">
            {fields.length === 0 && (
              <Card>
                <CardContent className="py-6 text-sm text-muted-foreground">
                  {lang === 'bn'
                    ? 'এখনো কোনো জমি নেই। স্যাটেলাইট ম্যাপে জমির চারপাশে রেখা টেনে প্রথম জমিটি যোগ করুন।'
                    : 'No lands yet. Draw a line around your first plot on the satellite map to add it.'}
                </CardContent>
              </Card>
            )}

            {fields.map((f, idx) => (
              <div
                key={f.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedId(f.id)}
                onKeyDown={(e) => { if (e.key === 'Enter') setSelectedId(f.id) }}
                className={
                  'flex gap-3 rounded-xl border p-3 text-left transition cursor-pointer ' +
                  (f.id === selectedId
                    ? 'border-primary bg-accent/40'
                    : 'border-border bg-card hover:border-primary/40')
                }
              >
                <img
                  src={fieldPhoto(f.name, idx)}
                  alt={f.name}
                  loading="lazy"
                  className="h-20 w-24 shrink-0 rounded-lg object-cover"
                />
                <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <MapPin className="size-4 shrink-0 text-primary" />
                    <span className="font-medium text-foreground">{f.name}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {isLocalField(f) ? (
                      <Badge variant="secondary" className="text-[10px]">
                        {lang === 'bn' ? 'এই ডিভাইসে' : 'On this device'}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-[10px]">
                        {lang === 'bn' ? 'নমুনা' : 'Demo'}
                      </Badge>
                    )}
                    {f.isPinEstimate && (
                      <Badge variant="secondary" className="text-[10px]">{t('pin_estimate', lang)}</Badge>
                    )}
                    <button
                      type="button"
                      aria-label={lang === 'bn' ? 'জমি মুছুন' : 'Delete land'}
                      onClick={(e) => {
                        e.stopPropagation()
                        void handleDelete(f)
                      }}
                      className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><Ruler className="size-3" /> {f.areaHa} ha</span>
                  <span className="inline-flex items-center gap-1"><Droplets className="size-3" /> {f.irrigation}</span>
                  <span className="inline-flex items-center gap-1"><Wheat className="size-3" /> {f.soilType ?? '—'}</span>
                </div>
                {(f.currentCycleCrops?.length || f.recentCycleCrops?.length) ? (
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    {f.currentCycleCrops?.length ? (
                      <span className="text-foreground">
                        <span className="font-medium">{lang === 'bn' ? 'বর্তমান: ' : 'Current: '}</span>
                        {f.currentCycleCrops.join(', ')}
                      </span>
                    ) : null}
                    {f.recentCycleCrops?.length ? (
                      <span className="text-muted-foreground">
                        <span className="font-medium">{lang === 'bn' ? 'সাম্প্রতিক: ' : 'Recent: '}</span>
                        {f.recentCycleCrops.join(', ')}
                      </span>
                    ) : null}
                  </div>
                ) : null}
                </div>
              </div>
            ))}

            {selected && stats && selectedCentroid && (
              <Card className="mt-1 border-primary/30">
                <CardHeader>
                  <CardTitle className="text-sm">{lang === 'bn' ? 'নির্বাচিত জমি' : 'Selected field'}</CardTitle>
                  <CardDescription>{selected.name}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="rounded-lg bg-muted/60 px-3 py-2 text-xs leading-relaxed">
                    <p className="font-medium text-foreground">
                      {areaUnits(selected.areaHa * 10_000).ha.toFixed(2)} ha ·{' '}
                      {areaUnits(selected.areaHa * 10_000).acre.toFixed(2)} acre ·{' '}
                      {areaUnits(selected.areaHa * 10_000).bigha.toFixed(2)} bigha
                    </p>
                    <p className="text-muted-foreground">
                      {lang === 'bn' ? 'কেন্দ্র: ' : 'Centre: '}
                      <span className="tabular-nums">{formatCoord(selectedCentroid.lat)}, {formatCoord(selectedCentroid.lng)}</span>
                    </p>
                  </div>
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{t('coverage', lang)} (HLS)</span>
                      <span>{stats.cov}%</span>
                    </div>
                    <Progress value={stats.cov} />
                  </div>
                  <Separator />
                  <div className="flex gap-2">
                    <Button size="sm" className="flex-1" onClick={() => navigate({ to: `/farmer/fields/${selected.id}` })}>
                      {lang === 'bn' ? 'বিস্তারিত দেখুন' : 'View details'}
                    </Button>
                    <Button size="sm" variant="outline" className="flex-1" onClick={() => navigate({ to: '/farmer/analyses', search: { fieldId: selected.id } as never })}>
                      {t('request_comparison', lang)}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Season advice for the selected field (defaults to the first field).
          The same advisory a farmer receives by SMS when they cannot check
          the website — suggestions, forecast and warnings, in cards. */}
      {(() => {
        const advisoryField = selected ?? fields[0]
        if (!advisoryField) return null
        const report = getSeasonReport(advisoryField.id)
        const forecast = getForecast(advisoryField.id)
        if (!report && !forecast) return null
        return (
          <section className="mt-8">
            <div className="mb-4 flex items-center gap-2">
              <Sprout className="size-5 text-primary" />
              <h2 className="text-xl font-bold text-foreground">
                {lang === 'bn' ? 'মৌসুমের পরামর্শ' : 'Season advice'}
                {' — '}
                {advisoryField.name}
              </h2>
            </div>
            <div className="flex flex-col gap-4">
              {report && <SeasonReport report={report} crops={{ current: advisoryField.currentCycleCrops, recent: advisoryField.recentCycleCrops }} />}
              {forecast && <ForecastCard forecast={forecast} />}
              <SmsPanel />
            </div>
          </section>
        )
      })()}
    </main>
  )
}
