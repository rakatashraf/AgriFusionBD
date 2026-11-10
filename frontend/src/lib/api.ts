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

export function currentUser(): User | null {
  // Synchronous accessor for layout rendering. The authoritative identity is
  // the Django session; `me()` below refreshes it from GET /auth/me/. This
  // returns a best-effort local cache so the shell renders immediately.
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem('fieldshift_user')
    if (raw) return JSON.parse(raw) as User
  } catch {
    /* ignore */
  }
  return null
}

/** Fetch the current session user from Django and cache it locally. */
export async function me(): Promise<User | null> {
  try {
    const u = await http<User>('/auth/me/')
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem('fieldshift_user', JSON.stringify(u))
      } catch {
        /* ignore */
      }
    }
    return u
  } catch {
    return null
  }
}

export async function login(role: string): Promise<User> {
  const u = await http<User>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ role }),
  })
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem('fieldshift_user', JSON.stringify(u))
    } catch {
      /* ignore */
    }
  }
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
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem('fieldshift_user', JSON.stringify(u))
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

/** Extra account details collected at sign-up (phone, district, SMS opt-in). */
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
  return null
}

export async function logout(): Promise<void> {
  await http<void>('/auth/logout/', { method: 'POST' })
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.removeItem('fieldshift_user')
    } catch {
      /* ignore */
    }
  }
}

// --- Fields -----------------------------------------------------------------

export function listFields(): Promise<Field[]> {
  return http<Field[]>('/fields')
}

export function getField(id: string): Promise<Field> {
  return http<Field>(`/fields/${id}`)
}

export interface CreateFieldInput {
  name: string
  geometry: { type: 'Polygon'; coordinates: number[][][] }
  areaHa: number
  irrigation: Field['irrigation']
}

/** Create a field on the Django backend. On the static Pages site there is
 *  no backend, so callers should fall back to on-device storage when this
 *  rejects. */
export function createField(input: CreateFieldInput): Promise<Field> {
  return http<Field>('/fields', { method: 'POST', body: JSON.stringify(input) })
}

export function deleteField(id: string): Promise<void> {
  return http<void>(`/fields/${id}`, { method: 'DELETE' })
}

export function getFieldCropHistory(fieldId: string): Promise<CropHistory[]> {
  return http<CropHistory[]>(`/fields/${fieldId}/crop-history`)
}

export function getFieldSoilTests(fieldId: string): Promise<SoilTest[]> {
  return http<SoilTest[]>(`/fields/${fieldId}/soil-tests`)
}

export function getFieldIndicators(fieldId: string): Promise<FieldIndicator[]> {
  return http<FieldIndicator[]>(`/fields/${fieldId}/indicators`)
}

export function listCrops(): Promise<Crop[]> {
  return http<Crop[]>('/catalogue/crops')
}

// --- Analyses ---------------------------------------------------------------

export function listAnalyses(fieldId?: string): Promise<AnalysisRun[]> {
  return http<AnalysisRun[]>(`/analyses${fieldId ? `?field=${fieldId}` : ''}`)
}

export function getAnalysis(id: string): Promise<AnalysisRun> {
  return http<AnalysisRun>(`/analyses/${id}`)
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
  return http<AnalysisRun['evidence']>(`/analyses/${id}/evidence`)
}

export function cancelAnalysis(id: string): Promise<void> {
  return http<void>(`/analyses/${id}/cancel`, { method: 'POST' })
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
  return http<RoverDevice[]>('/devices')
}

export function listObservations(fieldId?: string): Promise<RoverObservation[]> {
  return http<RoverObservation[]>(`/observations${fieldId ? `?field=${fieldId}` : ''}`)
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
  return http<ResearchLocation[]>('/research/locations')
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
