// Demo mode: when the Django backend is unreachable (static Pages site),
// the API client falls back to the project's own seed demo data so every
// page works end to end. The data is ALWAYS labelled "Demo" in the UI — it
// is sample data for trying the app, never presented as real measurements.
//
// Rules:
// - Demo mode only activates on a network error (the backend cannot be
//   reached at all). A real HTTP error from a reachable backend is never
//   masked by demo data.
// - Anything the user creates in demo mode is stored in this browser
//   (localStorage) and merged with the seed data on later loads.
// - The seed data comes from ./mock-data, the same dataset the backend's
//   `seed_demo` command loads. No new invented data.

import { useSyncExternalStore } from 'react'
import {
  USERS,
  CROPS,
  FIELDS,
  CROP_HISTORY,
  SOIL_TESTS,
  INDICATORS,
  ASSETS,
  ANALYSES,
  CASES,
  DEVICES,
  OBSERVATIONS,
  RESEARCH_LOCATIONS,
  EXPORT_JOBS,
} from './mock-data'
import type {
  AnalysisRun,
  AnalysisRequest,
  AssistanceCase,
  CaseMessage,
  CropHistory,
  Field,
  FieldIndicator,
  ResearchExportJob,
  RoverObservation,
  User,
} from './types'
import { loadLocalFields, saveLocalField, deleteLocalField, isLocalField } from './geo'

// --- Demo-mode flag -----------------------------------------------------------

let demoMode = false
const listeners = new Set<() => void>()

function emit() {
  for (const l of listeners) l()
}

export function isDemoMode(): boolean {
  return demoMode
}

export function setDemoMode(value: boolean): void {
  if (demoMode === value) return
  demoMode = value
  emit()
}

export function useDemoMode(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange)
      return () => {
        listeners.delete(onChange)
      }
    },
    () => demoMode,
    // Server snapshot: demo mode is a client-side (no-backend) state, so
    // the server always renders as if it were off; the client corrects it
    // after the first failed API call.
    () => false,
  )
}

// --- Local stores for things the user creates in demo mode -------------------

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function writeJson(key: string, value: unknown): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable — demo data stays in memory only */
  }
}

const K = {
  analyses: 'fieldshift.demo.analyses',
  cases: 'fieldshift.demo.cases',
  exports: 'fieldshift.demo.exports',
  observations: 'fieldshift.demo.observations',
  hiddenFields: 'fieldshift.demo.hidden_fields',
  user: 'fieldshift_user',
  profile: 'fieldshift_profile',
  fieldOverrides: 'fieldshift.demo.field_overrides',
}

// --- Signup profile (extra account details collected at sign-up) -----------

export interface SignupProfile {
  name: string
  phone: string
  district: string
  upazila: string
  /** Farmer: total farm size in hectares. */
  farmSizeHa?: string
  /** Officer / researcher: the area they are assigned to. */
  assignedArea?: string
  smsOptIn: boolean
}

export function readDemoProfile(): SignupProfile | null {
  return readJson<SignupProfile | null>(K.profile, null)
}

export function writeDemoProfile(p: SignupProfile): void {
  writeJson(K.profile, p)
}

function loadDemoAnalyses(): AnalysisRun[] {
  return readJson<AnalysisRun[]>(K.analyses, [])
}
function saveDemoAnalysis(run: AnalysisRun): void {
  const all = loadDemoAnalyses().filter((r) => r.id !== run.id)
  all.unshift(run)
  writeJson(K.analyses, all)
}
function loadDemoCases(): AssistanceCase[] {
  return readJson<AssistanceCase[]>(K.cases, [])
}
function saveDemoCase(c: AssistanceCase): void {
  const all = loadDemoCases().filter((x) => x.id !== c.id)
  all.unshift(c)
  writeJson(K.cases, all)
}
function loadDemoExports(): ResearchExportJob[] {
  return readJson<ResearchExportJob[]>(K.exports, [])
}
function saveDemoExport(job: ResearchExportJob): void {
  const all = loadDemoExports().filter((x) => x.id !== job.id)
  all.unshift(job)
  writeJson(K.exports, all)
}
function loadDemoObservations(): RoverObservation[] {
  return readJson<RoverObservation[]>(K.observations, [])
}
function saveDemoObservation(o: RoverObservation): void {
  const all = loadDemoObservations().filter((x) => x.id !== o.id)
  all.unshift(o)
  writeJson(K.observations, all)
}
function loadHiddenFieldIds(): string[] {
  return readJson<string[]>(K.hiddenFields, [])
}
function hideFieldId(id: string): void {
  const ids = loadHiddenFieldIds()
  if (!ids.includes(id)) {
    ids.push(id)
    writeJson(K.hiddenFields, ids)
  }
}

// Returned by demoFallback for endpoints whose real response is empty
// (logout, delete, cancel) — so the caller can tell "demo handled it" apart
// from "no demo data for this endpoint" (plain undefined).
export const DEMO_VOID: unique symbol = Symbol('demo-void')

function demoId(prefix: string): string {
  return `demo-${prefix}-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`
}

// --- Demo user ---------------------------------------------------------------

export function demoUser(role: string): User {
  const known = (USERS as Record<string, User>)[role]
  if (known) return known
  return {
    id: `demo-${role}`,
    name: role === 'farmer' ? 'Demo Farmer' : `Demo ${role}`,
    roles: [role as User['roles'][number]],
    locale: 'en',
  }
}

export function readDemoUser(): User | null {
  return readJson<User | null>(K.user, null)
}

// --- Field helpers ------------------------------------------------------------

function loadFieldOverrides(): Record<string, { name?: string; soilType?: string; irrigation?: Field['irrigation']; priorities?: string[]; currentCycleCrops?: string[]; recentCycleCrops?: string[] }> {
  return readJson<Record<string, { name?: string; soilType?: string; irrigation?: Field['irrigation']; priorities?: string[]; currentCycleCrops?: string[]; recentCycleCrops?: string[] }>>(K.fieldOverrides, {})
}

function applyFieldOverrides(f: Field): Field {
  const o = loadFieldOverrides()[f.id]
  if (!o) return f
  return {
    ...f,
    name: o.name ?? f.name,
    soilType: o.soilType ?? f.soilType,
    irrigation: o.irrigation ?? f.irrigation,
    priorities: o.priorities ?? f.priorities,
    currentCycleCrops: o.currentCycleCrops ?? f.currentCycleCrops,
    recentCycleCrops: o.recentCycleCrops ?? f.recentCycleCrops,
  }
}

function allFields(): Field[] {
  const hidden = new Set(loadHiddenFieldIds())
  const seed = FIELDS.filter((f) => !hidden.has(f.id))
  const local = loadLocalFields()
  const localIds = new Set(local.map((f) => f.id))
  return [...seed.filter((f) => !localIds.has(f.id)), ...local].map(applyFieldOverrides)
}

function findField(id: string): Field | undefined {
  return allFields().find((f) => f.id === id)
}

// --- Export CSV generation ----------------------------------------------------

export function demoExportText(locationName: string, format: 'csv' | 'geojson'): { text: string; filename: string } {
  const loc = RESEARCH_LOCATIONS.find((l) => l.name === locationName) ?? RESEARCH_LOCATIONS[0]
  const stamp = new Date().toISOString().slice(0, 10)
  if (format === 'geojson') {
    const geojson = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: loc.coordinates },
          properties: {
            name: loc.name,
            period: loc.period,
            coverage_pct: loc.coveragePct,
            source: 'Demo data — NASA POWER 0.5° cell (sample)',
          },
        },
      ],
    }
    return { text: JSON.stringify(geojson, null, 2), filename: `fieldshift-${loc.id}-${stamp}.geojson` }
  }
  const lines = ['date,ndvi,rainfall_mm,source']
  for (const s of loc.series) {
    lines.push(`${s.date},${s.ndvi.toFixed(3)},${s.rainfallMm.toFixed(1)},demo-nasa-power-0.5deg`)
  }
  return { text: lines.join('\n') + '\n', filename: `fieldshift-${loc.id}-${stamp}.csv` }
}

// --- The fallback --------------------------------------------------------------
// Returns demo data for an API path+method, or undefined when there is no
// demo data for it (the caller then re-throws the original network error).

export function demoFallback<T>(path: string, method: string, body?: unknown): T | undefined {
  const [rawPathRaw, rawQuery] = path.split('?')
  // Router-backed endpoints use a trailing slash; normalise so the demo
  // fallback matches either style.
  const rawPath = rawPathRaw.length > 1 ? rawPathRaw.replace(/\/+$/, '') : rawPathRaw
  const parts = rawPath.split('/').filter(Boolean)
  const query = new URLSearchParams(rawQuery ?? '')
  const m = method.toUpperCase()

  // --- Auth ---
  if (rawPath === '/auth/me' && m === 'GET') {
    return (readDemoUser() ?? demoUser('farmer')) as T
  }
  if (rawPath === '/auth/login' && m === 'POST') {
    const role = ((body as { role?: string } | undefined)?.role ?? 'farmer') as string
    const user = demoUser(role)
    writeJson(K.user, user)
    return user as T
  }
  if (rawPath === '/auth/signup' && m === 'POST') {
    const b = (body ?? {}) as { name?: string; phone?: string; role?: string; district?: string; upazila?: string; farmSizeHa?: string; assignedArea?: string; smsOptIn?: boolean }
    const role = (b.role ?? 'farmer') as string
    const user: User = {
      id: `demo-${role}-${Date.now().toString(36)}`,
      name: (b.name ?? '').trim() || (role === 'farmer' ? 'Demo Farmer' : `Demo ${role}`),
      roles: [role as User['roles'][number]],
      organization: (b.district ?? '').trim() ? `${b.district} · ${b.upazila ?? ''}`.trim() : undefined,
      locale: 'en',
    }
    writeJson(K.user, user)
    writeJson(K.profile, {
      name: user.name,
      phone: (b.phone ?? '').trim(),
      district: (b.district ?? '').trim(),
      upazila: (b.upazila ?? '').trim(),
      farmSizeHa: (b.farmSizeHa ?? '').trim() || undefined,
      assignedArea: (b.assignedArea ?? '').trim() || undefined,
      smsOptIn: b.smsOptIn !== false,
    } as SignupProfile)
    return user as T
  }
  if (rawPath === '/auth/logout' && m === 'POST') {
    if (typeof window !== 'undefined') window.localStorage.removeItem(K.user)
    return DEMO_VOID as unknown as T
  }

  // --- Fields ---
  if (rawPath === '/fields' && m === 'GET') return allFields() as T
  if (rawPath === '/fields' && m === 'POST') {
    const input = body as { name: string; geometry: Field['geometry']; areaHa: number; irrigation: Field['irrigation']; currentCycleCrops?: string[]; recentCycleCrops?: string[] }
    const field: Field = {
      id: demoId('field'),
      farmId: 'local',
      name: input.name,
      geometry: input.geometry,
      areaHa: input.areaHa,
      irrigation: input.irrigation,
      priorities: [],
      status: 'active',
      updatedAt: new Date().toISOString(),
      isPinEstimate: false,
      currentCycleCrops: input.currentCycleCrops?.length ? input.currentCycleCrops : undefined,
      recentCycleCrops: input.recentCycleCrops?.length ? input.recentCycleCrops : undefined,
    }
    saveLocalField(field)
    return field as T
  }
  if (parts[0] === 'fields' && parts.length === 2 && m === 'GET') {
    return findField(parts[1]) as T
  }
  if (parts[0] === 'fields' && parts.length === 2 && m === 'DELETE') {
    const f = findField(parts[1])
    if (f) {
      if (isLocalField(f)) deleteLocalField(f.id)
      else hideFieldId(f.id)
    }
    return DEMO_VOID as unknown as T
  }
  if (parts[0] === 'fields' && parts.length === 2 && (m === 'PATCH' || m === 'PUT')) {
    const b = (body ?? {}) as { name?: string; soilType?: string; irrigation?: Field['irrigation']; priorities?: string[]; currentCycleCrops?: string[]; recentCycleCrops?: string[] }
    const overrides = loadFieldOverrides()
    overrides[parts[1]] = {
      ...(overrides[parts[1]] ?? {}),
      ...(b.name !== undefined ? { name: b.name } : {}),
      ...(b.soilType !== undefined ? { soilType: b.soilType } : {}),
      ...(b.irrigation !== undefined ? { irrigation: b.irrigation } : {}),
      ...(b.priorities !== undefined ? { priorities: b.priorities } : {}),
      ...(b.currentCycleCrops !== undefined ? { currentCycleCrops: b.currentCycleCrops } : {}),
      ...(b.recentCycleCrops !== undefined ? { recentCycleCrops: b.recentCycleCrops } : {}),
    }
    writeJson(K.fieldOverrides, overrides)
    return findField(parts[1]) as T
  }
  if (parts[0] === 'fields' && parts[2] === 'crop-history' && m === 'GET') {
    const rows: CropHistory[] = CROP_HISTORY.filter((r) => r.fieldId === parts[1])
    return (rows.length ? rows : CROP_HISTORY) as T
  }
  if (parts[0] === 'fields' && parts[2] === 'soil-tests' && m === 'GET') {
    return SOIL_TESTS as T
  }
  if (parts[0] === 'fields' && parts[2] === 'indicators' && m === 'GET') {
    const rows: FieldIndicator[] = INDICATORS.filter((i) => i.fieldId === parts[1])
    return (rows.length ? rows : INDICATORS) as T
  }
  if (parts[0] === 'fields' && parts[2] === 'analyses' && m === 'POST') {
    const req = body as AnalysisRequest & { idempotencyKey?: string }
    const template = ANALYSES.find((a) => a.status === 'complete') ?? ANALYSES[0]
    const now = new Date().toISOString()
    const run: AnalysisRun = {
      id: demoId('analysis'),
      fieldId: req.fieldId,
      status: 'complete',
      progressPct: 100,
      submittedAt: now,
      completedAt: now,
      ruleVersion: template?.ruleVersion ?? 'v2026.11.0',
      idempotencyKey: req.idempotencyKey ?? demoId('idem'),
      request: {
        fieldId: req.fieldId,
        seasonStart: req.seasonStart,
        seasonEnd: req.seasonEnd,
        weights: req.weights,
        excludeCropIds: req.excludeCropIds,
      },
      plans: template?.plans,
      warnings: ['Demo result — sample rotation plans for trying the app.'],
      evidence: template?.evidence,
    }
    saveDemoAnalysis(run)
    return run as T
  }

  // --- Catalogue ---
  if (rawPath === '/catalogue/crops' && m === 'GET') return CROPS as T

  // --- Analyses ---
  if (rawPath === '/analyses' && m === 'GET') {
    const fieldId = query.get('field')
    const all = [...loadDemoAnalyses(), ...ANALYSES]
    return (fieldId ? all.filter((a) => a.fieldId === fieldId) : all) as T
  }
  if (parts[0] === 'analyses' && parts.length === 2 && m === 'GET') {
    const all = [...loadDemoAnalyses(), ...ANALYSES]
    return all.find((a) => a.id === parts[1]) as T
  }
  if (parts[0] === 'analyses' && parts[2] === 'evidence' && m === 'GET') {
    const all = [...loadDemoAnalyses(), ...ANALYSES]
    return all.find((a) => a.id === parts[1])?.evidence as T
  }
  if (parts[0] === 'analyses' && parts[2] === 'cancel' && m === 'POST') {
    const all = loadDemoAnalyses()
    const run = all.find((a) => a.id === parts[1])
    if (run) {
      run.status = 'cancelled'
      saveDemoAnalysis(run)
    }
    return DEMO_VOID as unknown as T
  }

  // --- Environmental assets ---
  if (rawPath === '/environmental/assets' && m === 'GET') return ASSETS as T

  // --- Cases ---
  if (rawPath === '/cases' && m === 'GET') {
    const fieldId = query.get('field')
    const all = [...loadDemoCases(), ...CASES]
    return (fieldId ? all.filter((c) => c.fieldId === fieldId) : all) as T
  }
  if (rawPath === '/cases' && m === 'POST') {
    const input = body as { fieldId: string; subject: string; body: string }
    const now = new Date().toISOString()
    const c: AssistanceCase = {
      id: demoId('case'),
      fieldId: input.fieldId,
      farmerId: 'demo-farmer',
      subject: input.subject,
      status: 'open',
      createdAt: now,
      updatedAt: now,
      messages: [
        {
          id: demoId('msg'),
          authorRole: 'farmer',
          body: input.body,
          at: now,
        },
      ],
    }
    saveDemoCase(c)
    return c as T
  }
  if (parts[0] === 'cases' && parts[2] === 'messages' && m === 'POST') {
    const input = body as { body: string }
    const all = [...loadDemoCases(), ...CASES]
    const c = all.find((x) => x.id === parts[1])
    const msg: CaseMessage = {
      id: demoId('msg'),
      authorRole: 'farmer',
      body: input.body,
      at: new Date().toISOString(),
    }
    if (c) {
      const updated: AssistanceCase = { ...c, messages: [...(c.messages ?? []), msg], updatedAt: new Date().toISOString() }
      if (loadDemoCases().some((x) => x.id === c.id)) saveDemoCase(updated)
      else saveDemoCase(updated)
    }
    return msg as T
  }
  if (parts[0] === 'cases' && parts.length === 2 && m === 'PATCH') {
    const input = body as { decision?: string; note?: string }
    const all = [...loadDemoCases(), ...CASES]
    const c = all.find((x) => x.id === parts[1])
    if (!c) return undefined
    const status = input.decision === 'accept' ? 'in_review' : input.decision === 'reject' ? 'rejected' : c.status
    const updated: AssistanceCase = { ...c, status, updatedAt: new Date().toISOString() }
    saveDemoCase(updated)
    return updated as T
  }

  // --- Rover ---
  if (rawPath === '/devices' && m === 'GET') return DEVICES as T
  if (rawPath === '/observations' && m === 'GET') {
    const fieldId = query.get('field')
    const all = [...loadDemoObservations(), ...OBSERVATIONS]
    return (fieldId ? all.filter((o) => o.fieldId === fieldId) : all) as T
  }
  if (parts[0] === 'devices' && parts[2] === 'observations' && m === 'POST') {
    const input = body as { fieldId: string; sensor: 'moisture' | 'temperature' | 'ec'; value: number; depthCm?: number }
    const obs: RoverObservation = {
      id: demoId('obs'),
      deviceId: parts[1],
      messageId: demoId('msg'),
      fieldId: input.fieldId,
      measuredAt: new Date().toISOString(),
      uploadedAt: new Date().toISOString(),
      coordinates: [88.6, 25.34],
      gpsAccuracyM: 5,
      depthCm: input.depthCm ?? 10,
      sensor: input.sensor,
      value: input.value,
      unit: input.sensor === 'moisture' ? '%' : input.sensor === 'temperature' ? '°C' : 'dS/m',
      calibrationId: 'demo-cal',
      quality: 'ok',
    }
    saveDemoObservation(obs)
    return obs as T
  }

  // --- Research ---
  if (rawPath === '/research/locations' && m === 'GET') return RESEARCH_LOCATIONS as T
  if (rawPath === '/research/exports' && m === 'GET') {
    return [...loadDemoExports(), ...EXPORT_JOBS] as T
  }
  if (rawPath === '/research/exports' && m === 'POST') {
    const input = body as { scope: string; format: 'csv' | 'geojson' }
    const locName = input.scope.split('·')[0]?.trim() ?? ''
    const loc = RESEARCH_LOCATIONS.find((l) => l.name === locName)
    const job: ResearchExportJob = {
      id: demoId('export'),
      scope: input.scope,
      format: input.format,
      status: 'complete',
      rowCount: loc ? loc.series.length : 0,
      provenance: {
        ruleVersion: 'v2026.11.0',
        dataSnapshots: ['demo-nasa-power-0.5deg', 'demo-hls'],
        generatedAt: new Date().toISOString(),
      },
      createdAt: new Date().toISOString(),
    }
    saveDemoExport(job)
    return job as T
  }

  return undefined
}

// --- Demo export download ------------------------------------------------------
// Builds a real downloadable file from the demo research series. Used by
// downloadExport when the backend cannot be reached.

export function demoDownload(id: string): { url: string; filename: string } | undefined {
  const job = [...loadDemoExports(), ...EXPORT_JOBS].find((j) => j.id === id)
  if (!job) return undefined
  const locName = job.scope.split('·')[0]?.trim() ?? ''
  const { text, filename } = demoExportText(locName, job.format)
  const blob = new Blob([text], { type: job.format === 'csv' ? 'text/csv' : 'application/geo+json' })
  return { url: URL.createObjectURL(blob), filename }
}
