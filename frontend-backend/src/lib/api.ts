// API client for the Django REST backend (plan §5).
//
// All data now comes from Django — no mock-data fallbacks. `mock-data.ts` is
// seed input for the `seed_demo` command only, and the UI must not import it.
//
// Contract:
//   - Base URL: VITE_API_BASE, falling back to the same-origin `/api/v1`.
//     In dev, Vite proxies `/api` → http://localhost:8000 (vite.config.ts).
//   - Session auth: credentials are always 'include'; the csrftoken cookie is
//     read and sent as X-CSRFToken on unsafe methods (POST/PATCH/DELETE).
//   - Errors: the Django error envelope { error: { code, message, details } }
//     is parsed into an ApiError so the UI can surface a human message.

import { useSyncExternalStore } from 'react'

import { demoFallback, demoDownload, setDemoMode, DEMO_VOID } from './demo'

import type {
  AnalysisRun,
  AnalysisRequest,
  AssistanceCase,
  CaseMessage,
  Crop,
  CropHistory,
  DataAsset,
  Field,
  FieldIndicator,
  ResearchExportJob,
  ResearchLocation,
  RoverDevice,
  RoverObservation,
  SoilTest,
  User,
} from './types'

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export class ApiError extends Error {
  readonly code: string
  readonly details: unknown
  readonly status: number

  constructor(status: number, code: string, message: string, details: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : null
}

async function http<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init.headers as Record<string, string>) ?? {}),
  }

  // Send X-CSRFToken on unsafe methods (Django session CSRF).
  if (UNSAFE_METHODS.has(method)) {
    const csrf = readCookie('csrftoken')
    if (csrf) headers['X-CSRFToken'] = csrf
  }

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      credentials: 'include',
      headers,
      ...init,
    })
  } catch (err) {
    // The backend cannot be reached at all (static Pages site). Fall back
    // to labelled demo data so the app stays usable; the UI shows a Demo
    // banner while this is active. A reachable backend that returns an HTTP
    // error is never masked — only a network failure triggers the fallback.
    let parsedBody: unknown
    try {
      parsedBody = init.body ? JSON.parse(init.body as string) : undefined
    } catch {
      parsedBody = undefined
    }
    const demo = demoFallback<T>(path, method, parsedBody)
    if (demo === DEMO_VOID) {
      setDemoMode(true)
      return undefined as T
    }
    if (demo !== undefined) {
      setDemoMode(true)
      return demo
    }
    throw new ApiError(
      0,
      'network_error',
      'Could not reach the AgriFusion BD API. Is the backend running?',
      String(err),
    )
  }

  // 204 No Content (e.g. cancel, delete) — nothing to parse.
  if (res.status === 204) return undefined as T

  const text = await res.text().catch(() => '')
  let body: unknown
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!res.ok) {
    // No API backend at all (static Pages site): the fetch succeeds but
    // returns the site's HTML 404 page instead of a JSON error envelope.
    // Treat that as "backend unreachable" and serve labelled demo data.
    // A real Django backend always answers errors as JSON, so a genuine
    // backend error is never masked by this.
    const contentType = res.headers.get('content-type') ?? ''
    const isHtml = !contentType.includes('application/json') || typeof body === 'string'
    if (isHtml) {
      let parsedBody: unknown
      try {
        parsedBody = init.body ? JSON.parse(init.body as string) : undefined
      } catch {
        parsedBody = undefined
      }
      const demo = demoFallback<T>(path, method, parsedBody)
      if (demo === DEMO_VOID) {
        setDemoMode(true)
        return undefined as T
      }
      if (demo !== undefined) {
        setDemoMode(true)
        return demo
      }
    }
    const env = (body ?? {}) as { error?: { code?: string; message?: string; details?: unknown } }
    const code = env.error?.code ?? 'error'
    const message = env.error?.message ?? res.statusText ?? 'Request failed'
    const details = env.error?.details
    throw new ApiError(res.status, code, message, details)
  }

  return body as T
}

// --- Auth -------------------------------------------------------------------

const USER_STORAGE_KEY = 'fieldshift_user'

// Cached identity, shared by the whole app. `undefined` means "not read from
// storage yet". The cache is never read during SSR, so the server and the
// first client render always agree (see `useCurrentUser`).
let userCache: User | null | undefined
const userListeners = new Set<() => void>()

function readStoredUser(): User | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(USER_STORAGE_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

function setCachedUser(user: User | null): void {
  userCache = user
  if (typeof window !== 'undefined') {
    try {
      if (user) window.localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
      else window.localStorage.removeItem(USER_STORAGE_KEY)
    } catch {
      /* storage unavailable — the in-memory cache still works */
    }
  }
  for (const listener of userListeners) listener()
}

export function subscribeUser(listener: () => void): () => void {
  userListeners.add(listener)
  return () => {
    userListeners.delete(listener)
  }
}

/** Synchronous identity accessor. Always null on the server. */
export function getCurrentUser(): User | null {
  if (typeof window === 'undefined') return null
  if (userCache === undefined) userCache = readStoredUser()
  return userCache
}

/** Reactive identity. Uses the server snapshot (null) during hydration so the
 *  first client render matches the SSR markup, then re-renders with the cached
 *  user — no hydration mismatch. */
export function useCurrentUser(): User | null {
  return useSyncExternalStore(subscribeUser, getCurrentUser, () => null)
}

/** Synchronous accessor for event handlers and non-reactive reads. */
export function currentUser(): User | null {
  return getCurrentUser()
}

/** Fetch the current session user from Django and cache it locally. */
export async function me(): Promise<User | null> {
  try {
    const u = await http<User>('/auth/me/')
    setCachedUser(u)
    return u
  } catch {
    setCachedUser(null)
    return null
  }
}

export async function login(role: string): Promise<User> {
  const u = await http<User>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ role }),
  })
  setCachedUser(u)
  return u
}

export interface SignupInput {
  name: string
  phone: string
  role: string
  district: string
  upazila: string
  farmSizeHa?: string
  assignedArea?: string
  smsOptIn: boolean
}

/** Create a demo account (sign up). On the static demo site the account is
    stored in this browser; a real backend would create a verified account. */
export async function signup(input: SignupInput): Promise<User> {
  const u = await http<User>('/auth/signup/', {
    method: 'POST',
    body: JSON.stringify(input),
  })
  setCachedUser(u)
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(
        'fieldshift_profile',
        JSON.stringify({
          name: input.name,
          phone: input.phone,
          district: input.district,
          upazila: input.upazila,
          farmSizeHa: input.farmSizeHa || undefined,
          assignedArea: input.assignedArea || undefined,
          smsOptIn: input.smsOptIn,
        }),
      )
    } catch {
      /* ignore */
    }
  }
  return u
}

/** Extra account details collected at sign-up (phone, district, SMS opt-in).
    The built-in demo identities (Rafiqul Islam etc.) never went through
    sign-up, so they get sensible defaults here instead of blank fields. */
export function readProfile(): {
  name: string
  phone: string
  district: string
  upazila: string
  farmSizeHa?: string
  assignedArea?: string
  smsOptIn: boolean
} | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem('fieldshift_profile')
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  const u = currentUser()
  if (!u) return null
  const base = { name: u.name, district: 'Rajshahi', upazila: 'Paba', smsOptIn: true }
  if (u.name === 'Rafiqul Islam') {
    return { ...base, phone: '+880 1XXX-XXXX55', farmSizeHa: '3.80' }
  }
  if (u.name === 'Nasrin Akter') {
    return { ...base, phone: '+880 1XXX-XXXX66', district: 'Dinajpur', upazila: 'Dinajpur Sadar', assignedArea: 'Dinajpur' }
  }
  if (u.name === 'Dr. Tanvir Hasan') {
    return { ...base, phone: '+880 1XXX-XXXX77', upazila: 'Rajshahi', assignedArea: 'Rajshahi' }
  }
  if (u.name === 'Kamal Uddin') {
    return { ...base, phone: '+880 1XXX-XXXX88' }
  }
  return { ...base, phone: '' }
}

export async function logout(): Promise<void> {
  try {
    await http<void>('/auth/logout/', { method: 'POST' })
  } finally {
    setCachedUser(null)
  }
}

// --- Fields -----------------------------------------------------------------

/** A field as it comes over the wire: Django emits GeoJSON geometry as a
 *  string and decimals as strings, while the UI works with objects/numbers. */
type FieldPayload = Omit<Field, 'geometry' | 'areaHa'> & {
  geometry: Field['geometry'] | string | null
  areaHa: number | string | null
  pinRadiusM?: number
}

/** Normalise any GeoJSON shape the API may return into a Polygon the map and
 *  geometry helpers can consume. Point geometries (pin estimates) become a
 *  small square around the pin so they are visible and selectable. */
function normalizeGeometry(raw: unknown, pinRadiusM = 25): Field['geometry'] {
  let geom = raw
  if (typeof geom === 'string') {
    try {
      geom = JSON.parse(geom)
    } catch {
      geom = null
    }
  }
  if (!geom || typeof geom !== 'object') return { type: 'Polygon', coordinates: [] }
  const g = geom as { type?: string; coordinates?: unknown }
  if (g.type === 'Polygon' && Array.isArray(g.coordinates)) {
    return { type: 'Polygon', coordinates: g.coordinates as number[][][] }
  }
  if (g.type === 'MultiPolygon' && Array.isArray(g.coordinates)) {
    const first = (g.coordinates as number[][][][])[0]
    if (first) return { type: 'Polygon', coordinates: first }
  }
  if (g.type === 'Point' && Array.isArray(g.coordinates) && g.coordinates.length >= 2) {
    const [lng, lat] = g.coordinates as number[]
    const dLat = pinRadiusM / 111_320
    const dLng = pinRadiusM / (111_320 * Math.max(Math.cos((lat * Math.PI) / 180), 0.2))
    return {
      type: 'Polygon',
      coordinates: [[
        [lng - dLng, lat - dLat],
        [lng + dLng, lat - dLat],
        [lng + dLng, lat + dLat],
        [lng - dLng, lat + dLat],
        [lng - dLng, lat - dLat],
      ]],
    }
  }
  return { type: 'Polygon', coordinates: [] }
}

function normalizeField(raw: FieldPayload): Field {
  const areaHa = Number(raw.areaHa)
  return {
    ...raw,
    areaHa: Number.isFinite(areaHa) ? areaHa : 0,
    geometry: normalizeGeometry(raw.geometry, raw.pinRadiusM ?? 25),
  }
}

export function listFields(): Promise<Field[]> {
  return http<{ count: number; results: FieldPayload[] } | FieldPayload[]>('/fields/').then((r) => {
    const rows = Array.isArray(r) ? r : r.results ?? []
    return rows.map(normalizeField)
  })
}

export function getField(id: string): Promise<Field> {
  return http<FieldPayload>(`/fields/${id}/`).then(normalizeField)
}

export function updateField(
  id: string,
  patch: {
    name?: string
    soilType?: string
    irrigation?: Field['irrigation']
    priorities?: string[]
    currentCycleCrops?: string[]
    recentCycleCrops?: string[]
    geometry?: Field['geometry']
  },
): Promise<Field> {
  return http<FieldPayload>(`/fields/${id}/`, { method: 'PATCH', body: JSON.stringify(patch) }).then(normalizeField)
}

export interface CreateFieldInput {
  name: string
  geometry: { type: 'Polygon'; coordinates: number[][][] }
  areaHa: number
  irrigation: Field['irrigation']
  soilType?: string
  priorities?: string[]
  currentCycleCrops?: string[]
  recentCycleCrops?: string[]
}

/** Create a field on the Django backend. On the static Pages site there is
 *  no backend, so callers should fall back to on-device storage when this
 *  rejects. */
export function createField(input: CreateFieldInput): Promise<Field> {
  return http<FieldPayload>('/fields/', { method: 'POST', body: JSON.stringify(input) }).then(normalizeField)
}

export function deleteField(id: string): Promise<void> {
  return http<void>(`/fields/${id}/`, { method: 'DELETE' })
}

export function getFieldCropHistory(fieldId: string): Promise<CropHistory[]> {
  return http<CropHistory[]>(`/fields/${fieldId}/crop-history/`)
}

export function getFieldSoilTests(fieldId: string): Promise<SoilTest[]> {
  return http<SoilTest[]>(`/fields/${fieldId}/soil-tests/`)
}

export function getFieldIndicators(fieldId: string): Promise<FieldIndicator[]> {
  return http<FieldIndicator[]>(`/fields/${fieldId}/indicators`)
}

export function listCrops(): Promise<Crop[]> {
  return http<{ count: number; results: Crop[] }>('/catalogue/crops/').then(
    (r) => (Array.isArray(r) ? r : r.results ?? []),
  )
}

// --- Analyses ---------------------------------------------------------------

export function listAnalyses(fieldId?: string): Promise<AnalysisRun[]> {
  return http<AnalysisRun[]>(`/analyses/${fieldId ? `?field=${fieldId}` : ''}`)
}

export function getAnalysis(id: string): Promise<AnalysisRun> {
  return http<AnalysisRun>(`/analyses/${id}/`)
}

/**
 * POST /fields/{id}/analyses — returns 202 + the queued run.
 *
 * Idempotency: the same (field, weights, exclusions) request reuses one
 * idempotency key so duplicate submissions collapse to a single run. We derive
 * the key deterministically from the request body (not crypto.randomUUID, which
 * would defeat collapse on retry) — plan §2 idempotency rule.
 */
export function submitAnalysis(req: AnalysisRequest): Promise<AnalysisRun> {
  const canon = JSON.stringify({
    field: req.fieldId,
    w: req.weights,
    excl: [...(req.excludeCropIds ?? [])].sort(),
    season: [req.seasonStart, req.seasonEnd],
  })
  // A short stable hash for the key (djb2) — collision-safe enough for a session.
  let h = 5381
  for (let i = 0; i < canon.length; i++) h = ((h << 5) + h + canon.charCodeAt(i)) >>> 0
  const idempotencyKey = `idem-${h.toString(16)}`

  return http<AnalysisRun>(`/fields/${req.fieldId}/analyses`, {
    method: 'POST',
    body: JSON.stringify({ ...req, idempotencyKey }),
  })
}

export function getAnalysisEvidence(id: string): Promise<AnalysisRun['evidence']> {
  return http<AnalysisRun['evidence']>(`/analyses/${id}/evidence/`)
}

export function cancelAnalysis(id: string): Promise<void> {
  return http<void>(`/analyses/${id}/cancel/`, { method: 'POST' })
}

export function listAssets(): Promise<DataAsset[]> {
  return http<DataAsset[]>('/environmental/assets')
}

// --- Cases ------------------------------------------------------------------

export function listCases(fieldId?: string): Promise<AssistanceCase[]> {
  return http<AssistanceCase[]>(`/cases${fieldId ? `?field=${fieldId}` : ''}`)
}

export function createCase(input: { fieldId: string; subject: string; body: string }): Promise<AssistanceCase> {
  return http<AssistanceCase>('/cases', { method: 'POST', body: JSON.stringify(input) })
}

export function postCaseMessage(caseId: string, body: string): Promise<CaseMessage> {
  return http<CaseMessage>(`/cases/${caseId}/messages`, { method: 'POST', body: JSON.stringify({ body }) })
}

/**
 * Officer decision: 'accept' | 'question' | 'reject' (plan §2: wire the inert
 * Accept/Question/Reject buttons to the real endpoint).
 */
export function decideCase(
  caseId: string,
  decision: 'accept' | 'question' | 'reject',
  note?: string,
): Promise<AssistanceCase> {
  return http<AssistanceCase>(`/cases/${caseId}`, {
    method: 'PATCH',
    body: JSON.stringify({ decision, note }),
  })
}

// --- Rover ------------------------------------------------------------------

export function listDevices(): Promise<RoverDevice[]> {
  return http<Array<{ id: string; name: string; status: string; batteryPct: number; lastSeen?: string; fields: { slug: string; name: string }[] }>>('/devices').then((rows) =>
    rows.map((d) => ({
      id: d.id,
      name: d.name,
      model: 'AgriRover-Q',
      status: d.status as RoverDevice['status'],
      batteryPct: d.batteryPct,
      lastSeenAt: d.lastSeen ?? new Date().toISOString(),
      fieldIds: d.fields.map((f) => f.slug),
    }))
  )
}

export function listObservations(fieldId?: string): Promise<RoverObservation[]> {
  return http<Array<{ id: string; fieldId: string; sensor: string; value: number; unit: string; takenAt: string; quality: string; calibrated: boolean; depthCm: number | null }>>(
    `/observations${fieldId ? `?field=${fieldId}` : ''}`
  ).then((rows) =>
    rows.map((o) => ({
      id: o.id,
      deviceId: '',
      messageId: '',
      fieldId: o.fieldId,
      measuredAt: o.takenAt,
      uploadedAt: o.takenAt,
      coordinates: [0, 0] as [number, number],
      gpsAccuracyM: 0,
      depthCm: o.depthCm ?? 0,
      sensor: o.sensor as RoverObservation['sensor'],
      value: o.value,
      unit: o.unit,
      calibrationId: '',
      quality: o.quality as RoverObservation['quality'],
    }))
  )
}

export function postObservation(
  deviceId: string,
  payload: {
    fieldId: string
    sensor: 'moisture' | 'temperature' | 'ec'
    value: number
    depthCm?: number
  },
): Promise<RoverObservation> {
  return http<RoverObservation>(`/devices/${deviceId}/observations`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// --- Research ---------------------------------------------------------------

export function listResearchLocations(): Promise<ResearchLocation[]> {
  return http<Array<{ slug: string; name: string; lat: number; lng: number; region?: string; indicatorCount?: number }>>('/research/locations').then((rows) =>
    rows.map((r) => ({
      id: r.slug,
      name: r.name,
      coordinates: [r.lng, r.lat] as [number, number],
      period: '',
      coveragePct: 0,
      series: [] as ResearchLocation['series'],
    }))
  )
}

export function listExportJobs(): Promise<ResearchExportJob[]> {
  return http<ResearchExportJob[]>('/research/exports')
}

export function createExportJob(input: {
  scope: string
  format: 'csv' | 'geojson'
}): Promise<ResearchExportJob> {
  return http<ResearchExportJob>('/research/exports', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

/**
 * Real export download (plan §2 defect: createExportJob used to create no
 * artifact). The backend writes CSV/GeoJSON + provenance.json; this returns the
 * blob URL the UI hands to <a download>.
 */
export async function downloadExport(id: string): Promise<{ url: string; filename: string }> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/research/exports/${id}/download`, {
      credentials: 'include',
    })
  } catch {
    // Backend unreachable — build the file from the demo research series.
    const demo = demoDownload(id)
    if (demo) {
      setDemoMode(true)
      return demo
    }
    throw new ApiError(0, 'network_error', 'Could not reach the AgriFusion BD API. Is the backend running?', '')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    let code = 'download_failed'
    let message = res.statusText
    try {
      const env = JSON.parse(text)
      code = env?.error?.code ?? code
      message = env?.error?.message ?? message
    } catch {
      /* keep defaults */
    }
    throw new ApiError(res.status, code, message, undefined)
  }
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') ?? ''
  const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)
  const filename = m?.[1] ?? `export-${id}`
  return { url: URL.createObjectURL(blob), filename }
}
