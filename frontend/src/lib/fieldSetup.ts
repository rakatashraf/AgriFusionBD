// Field setup + local observations — demo storage (this browser only).
// The guide's field-setup screen (crop history, planting dates, soil,
// irrigation, priorities) and local observations (soil test, irrigation,
// crop outcome, photo note) are kept in localStorage on the static demo
// site; a real backend would store them in Django/PostGIS.

export interface FieldOverride {
  name?: string
  soilType?: string
  irrigation?: 'rainfed' | 'canal' | 'pump' | 'tubewell'
  priorities?: string[]
}

export interface LocalCropHistory {
  year: number
  cropName: string
  plantingDate?: string
  harvestDate?: string
  yieldT?: number
  notes?: string
}

export type ObservationKind = 'soil_test' | 'irrigation' | 'crop_outcome' | 'photo_note'

export interface LocalObservation {
  id: string
  fieldId: string
  kind: ObservationKind
  date: string
  note: string
  detail?: string
}

const K_OVERRIDES = 'fieldshift.demo.field_overrides'
const K_HISTORY = 'fieldshift.demo.extra_crop_history'
const K_OBS = 'fieldshift.demo.local_observations'

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw) return JSON.parse(raw) as T
  } catch {
    /* ignore */
  }
  return fallback
}

function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}

export function loadFieldOverrides(): Record<string, FieldOverride> {
  if (typeof window === 'undefined') return {}
  return readJson<Record<string, FieldOverride>>(K_OVERRIDES, {})
}

export function saveFieldOverride(fieldId: string, o: FieldOverride): void {
  const all = loadFieldOverrides()
  all[fieldId] = { ...(all[fieldId] ?? {}), ...o }
  writeJson(K_OVERRIDES, all)
}

export function loadExtraCropHistory(fieldId: string): LocalCropHistory[] {
  if (typeof window === 'undefined') return []
  const all = readJson<Record<string, LocalCropHistory[]>>(K_HISTORY, {})
  return all[fieldId] ?? []
}

export function addExtraCropHistory(fieldId: string, entry: LocalCropHistory): void {
  const all = readJson<Record<string, LocalCropHistory[]>>(K_HISTORY, {})
  all[fieldId] = [...(all[fieldId] ?? []), entry]
  writeJson(K_HISTORY, all)
}

export function loadLocalObservations(fieldId: string): LocalObservation[] {
  if (typeof window === 'undefined') return []
  const all = readJson<Record<string, LocalObservation[]>>(K_OBS, {})
  return all[fieldId] ?? []
}

export function addLocalObservation(obs: LocalObservation): void {
  const all = readJson<Record<string, LocalObservation[]>>(K_OBS, {})
  all[obs.fieldId] = [obs, ...(all[obs.fieldId] ?? [])]
  writeJson(K_OBS, all)
}

export function deleteLocalObservation(fieldId: string, id: string): void {
  const all = readJson<Record<string, LocalObservation[]>>(K_OBS, {})
  all[fieldId] = (all[fieldId] ?? []).filter((o) => o.id !== id)
  writeJson(K_OBS, all)
}

export const OBSERVATION_KINDS: Array<{ value: ObservationKind; en: string; bn: string }> = [
  { value: 'soil_test', en: 'Soil test', bn: 'মাটির পরীক্ষা' },
  { value: 'irrigation', en: 'Irrigation', bn: 'সেচ' },
  { value: 'crop_outcome', en: 'Crop outcome', bn: 'ফসলের ফলাফল' },
  { value: 'photo_note', en: 'Photo note', bn: 'ছবির নোট' },
]
