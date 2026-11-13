// Rover paths — the routes a rover follows to gauge a field and collect
// data. A professional creates a path in one of two ways: pick a field and
// the path is auto-generated as a lawnmower (serpentine) pattern across it,
// or click points on the map to draw a custom path. Paths are saved in this
// browser on the demo site (localStorage); a real backend would send the
// path to the rover.

import type { RoverPath, RoverRequest } from '#/lib/types'
import { geodesicAreaSqM, ringBounds, type LngLat } from '#/lib/geo'

const ROVER_PATHS_KEY = 'fieldshift.demo.rover_paths'
const ROVER_REQUESTS_KEY = 'fieldshift.demo.rover_requests'

function readPaths(): RoverPath[] {
  try {
    const raw = window.localStorage.getItem(ROVER_PATHS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as RoverPath[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function loadRoverPaths(): RoverPath[] {
  return readPaths()
}

export function saveRoverPath(path: RoverPath): RoverPath[] {
  const paths = readPaths()
  const next = [...paths.filter((p) => p.id !== path.id), path]
  window.localStorage.setItem(ROVER_PATHS_KEY, JSON.stringify(next))
  return next
}

export function deleteRoverPath(id: string): RoverPath[] {
  const next = readPaths().filter((p) => p.id !== id)
  window.localStorage.setItem(ROVER_PATHS_KEY, JSON.stringify(next))
  return next
}

export function updateRoverPathStatus(id: string, status: RoverPath['status']): RoverPath[] {
  const next = readPaths().map((p) => (p.id === id ? { ...p, status } : p))
  window.localStorage.setItem(ROVER_PATHS_KEY, JSON.stringify(next))
  // When a path is completed, the request it was made for is completed too.
  if (status === 'completed') {
    const reqs = readRequests().map((r) => (r.pathId === id ? { ...r, status: 'completed' as const } : r))
    window.localStorage.setItem(ROVER_REQUESTS_KEY, JSON.stringify(reqs))
  }
  return next
}

// --- Rover requests ---------------------------------------------------------

function readRequests(): RoverRequest[] {
  try {
    const raw = window.localStorage.getItem(ROVER_REQUESTS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as RoverRequest[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function loadRoverRequests(): RoverRequest[] {
  return readRequests()
}

export function saveRoverRequest(req: RoverRequest): RoverRequest[] {
  const reqs = readRequests()
  const next = [...reqs.filter((r) => r.id !== req.id), req]
  window.localStorage.setItem(ROVER_REQUESTS_KEY, JSON.stringify(next))
  return next
}

export function updateRoverRequest(id: string, patch: Partial<RoverRequest>): RoverRequest[] {
  const next = readRequests().map((r) => (r.id === id ? { ...r, ...patch } : r))
  window.localStorage.setItem(ROVER_REQUESTS_KEY, JSON.stringify(next))
  return next
}

export function deleteRoverRequest(id: string): RoverRequest[] {
  const next = readRequests().filter((r) => r.id !== id)
  window.localStorage.setItem(ROVER_REQUESTS_KEY, JSON.stringify(next))
  return next
}

/** The open (not completed) request for a field, if the farmer already
 *  asked for rover analysis on it. */
export function openRequestForField(fieldId: string): RoverRequest | undefined {
  return readRequests().find((r) => r.fieldId === fieldId && r.status !== 'completed')
}

/** When a path is saved for a field that has a pending request, link the
 *  request to the path and move it to "path assigned". */
export function linkPathToRequest(fieldId: string, pathId: string): RoverRequest[] {
  const next = readRequests().map((r) =>
    r.fieldId === fieldId && r.status === 'requested'
      ? { ...r, status: 'path_assigned' as const, pathId }
      : r,
  )
  window.localStorage.setItem(ROVER_REQUESTS_KEY, JSON.stringify(next))
  return next
}

// --- Geometry ---------------------------------------------------------------

/** Ray-casting point-in-polygon in lng/lat coordinates. */
function pointInRing(point: LngLat, ring: LngLat[]): boolean {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

const M_PER_DEG_LAT = 111_320

/** Geodesic distance between two [lng, lat] points, in metres. */
export function distanceM(a: LngLat, b: LngLat): number {
  const R = 6_371_000
  const dLat = ((b[1] - a[1]) * Math.PI) / 180
  const dLng = ((b[0] - a[0]) * Math.PI) / 180
  const lat1 = (a[1] * Math.PI) / 180
  const lat2 = (b[1] * Math.PI) / 180
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export function pathLengthM(points: LngLat[]): number {
  let total = 0
  for (let i = 1; i < points.length; i++) total += distanceM(points[i - 1], points[i])
  return total
}

/**
 * Generate a lawnmower (serpentine) path across a field polygon: parallel
 * passes spaced `spacingM` apart, alternating direction so the rover walks
 * one continuous route. Each pass runs from one edge of the field to the
 * other, so the rover gauges the whole field. Returns waypoints as
 * [lng, lat] pairs.
 */
export function generateSerpentinePath(ring: LngLat[], spacingM = 8): LngLat[] {
  if (ring.length < 3) return []
  const bounds = ringBounds(ring)
  const [[minLng, minLat], [maxLng, maxLat]] = bounds
  const centreLat = (minLat + maxLat) / 2
  const mPerDegLng = M_PER_DEG_LAT * Math.cos((centreLat * Math.PI) / 180)
  const latStep = spacingM / M_PER_DEG_LAT
  const lngStep = spacingM / mPerDegLng

  const waypoints: LngLat[] = []
  let row = 0
  // Inset half a spacing from the edges so the rover stays inside the field.
  for (let lat = minLat + latStep / 2; lat <= maxLat; lat += latStep, row++) {
    // Find the inside run(s) of this row by sampling across the bounds.
    const inside: number[] = []
    for (let lng = minLng; lng <= maxLng; lng += lngStep / 4) {
      if (pointInRing([lng, lat], ring)) inside.push(lng)
    }
    if (inside.length < 2) continue
    const left = inside[0]
    const right = inside[inside.length - 1]
    // Alternate direction each row so the path is one continuous walk.
    if (row % 2 === 0) waypoints.push([left, lat], [right, lat])
    else waypoints.push([right, lat], [left, lat])
  }
  return waypoints
}

/** A short human-readable length, e.g. "486 m" or "1.24 km". */
export function formatPathLength(lengthM: number): string {
  if (lengthM >= 1000) return `${(lengthM / 1000).toFixed(2)} km`
  return `${Math.round(lengthM)} m`
}

export { geodesicAreaSqM }
