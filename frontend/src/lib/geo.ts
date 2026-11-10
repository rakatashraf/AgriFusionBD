// Geography helpers for the field map: geodesic area, centroid, unit
// conversion and on-device storage for farmer-drawn lands.
//
// Area uses the Chamberlain–Duquette spherical-excess formula, which is
// accurate to well under 1% for farm-size polygons. No extra dependency.
//
// Units (Bangladesh): 1 hectare = 10,000 m²; 1 acre = 4,046.86 m²;
// 1 bigha = 33 decimal = 14,400 sq ft = 1,337.8 m².

import type { Field } from './types'

export type LngLat = [number, number]

const EARTH_RADIUS_M = 6_378_137
const SQM_PER_HA = 10_000
const SQM_PER_ACRE = 4_046.8564224
const SQM_PER_BIGHA = 1_337.803

export interface AreaUnits {
  sqm: number
  ha: number
  acre: number
  bigha: number
}

export function areaUnits(sqm: number): AreaUnits {
  return {
    sqm,
    ha: sqm / SQM_PER_HA,
    acre: sqm / SQM_PER_ACRE,
    bigha: sqm / SQM_PER_BIGHA,
  }
}

/** Geodesic area (m²) of a polygon ring given as [lng, lat] pairs. The ring
 *  need not be closed; the first point is reused to close it. Returns 0
 *  when fewer than 3 distinct points are given. */
export function geodesicAreaSqM(ring: LngLat[]): number {
  if (ring.length < 3) return 0
  const pts = ring.slice()
  // Close the ring if the caller did not.
  if (pts[0][0] !== pts[pts.length - 1][0] || pts[0][1] !== pts[pts.length - 1][1]) {
    pts.push(pts[0])
  }
  let total = 0
  for (let i = 0; i < pts.length - 1; i++) {
    const [lng1, lat1] = pts[i]
    const [lng2, lat2] = pts[i + 1]
    const p1 = (lng2 - lng1) * (Math.PI / 180)
    const p2 = Math.sin((lat1 * Math.PI) / 180) + Math.sin((lat2 * Math.PI) / 180)
    total += p1 * p2
  }
  const area = Math.abs((total * EARTH_RADIUS_M * EARTH_RADIUS_M) / 2)
  return area
}

/** Planar centroid of a polygon ring ([lng, lat] pairs). Accurate enough
 *  for farm-size fields; used for the "exact location" readout. */
export function polygonCentroid(ring: LngLat[]): { lng: number; lat: number } {
  if (ring.length === 0) return { lng: 0, lat: 0 }
  if (ring.length < 3) {
    const lng = ring.reduce((s, p) => s + p[0], 0) / ring.length
    const lat = ring.reduce((s, p) => s + p[1], 0) / ring.length
    return { lng, lat }
  }
  const pts = ring.slice()
  if (pts[0][0] !== pts[pts.length - 1][0] || pts[0][1] !== pts[pts.length - 1][1]) {
    pts.push(pts[0])
  }
  let a = 0
  let cx = 0
  let cy = 0
  for (let i = 0; i < pts.length - 1; i++) {
    const [x1, y1] = pts[i]
    const [x2, y2] = pts[i + 1]
    const cross = x1 * y2 - x2 * y1
    a += cross
    cx += (x1 + x2) * cross
    cy += (y1 + y2) * cross
  }
  a /= 2
  if (Math.abs(a) < 1e-12) {
    const lng = ring.reduce((s, p) => s + p[0], 0) / ring.length
    const lat = ring.reduce((s, p) => s + p[1], 0) / ring.length
    return { lng, lat }
  }
  return { lng: cx / (6 * a), lat: cy / (6 * a) }
}

/** Bounding box of a ring: [[minLng, minLat], [maxLng, maxLat]]. */
export function ringBounds(ring: LngLat[]): [[number, number], [number, number]] {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const [x, y] of ring) {
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minY = Math.min(minY, y)
    maxY = Math.max(maxY, y)
  }
  return [
    [minX, minY],
    [maxX, maxY],
  ]
}

export function formatCoord(value: number): string {
  return value.toFixed(6)
}

export function formatAreaLine(sqm: number): string {
  const u = areaUnits(sqm)
  return `${u.ha.toFixed(2)} ha · ${u.acre.toFixed(2)} acre · ${u.bigha.toFixed(2)} bigha`
}

// --- On-device storage for farmer-drawn lands --------------------------------
// The live site is static (no backend), so lands drawn there are kept in the
// browser until the Django API is reachable. They are labelled "On this
// device" in the UI so a farmer never mistakes them for server-saved fields.

const LOCAL_FIELDS_KEY = 'fieldshift.local_fields.v1'

export function loadLocalFields(): Field[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(LOCAL_FIELDS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Field[]
    if (!Array.isArray(parsed)) return []
    return parsed.filter((f) => f && f.geometry && Array.isArray(f.geometry.coordinates))
  } catch {
    return []
  }
}

export function saveLocalField(field: Field): void {
  const existing = loadLocalFields().filter((f) => f.id !== field.id)
  existing.push(field)
  window.localStorage.setItem(LOCAL_FIELDS_KEY, JSON.stringify(existing))
}

export function deleteLocalField(id: string): void {
  const remaining = loadLocalFields().filter((f) => f.id !== id)
  window.localStorage.setItem(LOCAL_FIELDS_KEY, JSON.stringify(remaining))
}

export function isLocalField(field: Field): boolean {
  return field.farmId === 'local'
}

/** Build a Field record from a drawn ring. The caller supplies the name and
 *  irrigation; everything else (area, centroid, timestamps) is derived. */
export function fieldFromRing(
  ring: LngLat[],
  name: string,
  irrigation: Field['irrigation'],
): Field {
  const closed: LngLat[] = ring.slice()
  if (closed[0][0] !== closed[closed.length - 1][0] || closed[0][1] !== closed[closed.length - 1][1]) {
    closed.push(closed[0])
  }
  const areaSqM = geodesicAreaSqM(closed)
  return {
    id: `local-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e6).toString(36)}`,
    farmId: 'local',
    name,
    geometry: { type: 'Polygon', coordinates: [closed] },
    areaHa: Math.round((areaSqM / SQM_PER_HA) * 100) / 100,
    irrigation,
    priorities: [],
    status: 'active',
    updatedAt: new Date().toISOString(),
    isPinEstimate: false,
  }
}
