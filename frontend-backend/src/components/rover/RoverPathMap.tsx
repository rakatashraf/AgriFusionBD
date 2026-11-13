// Map for building a rover path. The professional either clicks a field
// (the path is auto-generated across it) or clicks points on the map to
// draw a custom path. Field outlines and the path are drawn as an SVG
// overlay (the same approach as FieldMap — MapLibre GeoJSON layers never
// painted on this site), projected with map.project() and re-projected on
// every map move.
import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import '#/lib/maplibre-worker'

import type { Field } from '#/lib/types'
import { polygonCentroid, type LngLat } from '#/lib/geo'

interface Props {
  fields: Field[]
  selectedFieldId?: string
  points: LngLat[]
  onFieldClick?: (id: string) => void
  onMapClick?: (lngLat: LngLat) => void
  className?: string
}

const ESRI_SAT_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
]
const ESRI_REF_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
]

const STYLE = {
  version: 8,
  sources: {
    sat: { type: 'raster', tiles: ESRI_SAT_TILES, tileSize: 256, maxzoom: 18, attribution: 'Esri, Maxar, Earthstar Geographics' },
    satRef: { type: 'raster', tiles: ESRI_REF_TILES, tileSize: 256, attribution: 'Esri' },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#0a1418' } },
    { id: 'sat', type: 'raster', source: 'sat', paint: { 'raster-opacity': 1 } },
    { id: 'sat-ref', type: 'raster', source: 'satRef', paint: { 'raster-opacity': 0.9 } },
  ],
} as never

type Pt = { x: number; y: number }

function pointInPolygon(p: Pt, poly: Pt[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y
    const xj = poly[j].x, yj = poly[j].y
    const intersect = yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/** Outer ring of a field's polygon, or an empty array for missing geometry. */
function ringOf(f: Field): LngLat[] {
  const coords = f.geometry?.coordinates
  const ring = Array.isArray(coords) ? coords[0] : undefined
  return Array.isArray(ring) ? (ring as LngLat[]) : []
}

export default function RoverPathMap({ fields, selectedFieldId, points, onFieldClick, onMapClick, className }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [mapTick, setMapTick] = useState(0)
  const fieldClickRef = useRef(onFieldClick)
  fieldClickRef.current = onFieldClick
  const mapClickRef = useRef(onMapClick)
  mapClickRef.current = onMapClick
  const fieldsRef = useRef(fields)
  fieldsRef.current = fields

  // --- Map setup (once) ---
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [88.5685, 24.4471],
      zoom: 13,
      maxZoom: 18,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => setMapLoaded(true))
    map.on('move', () => setMapTick((t) => t + 1))
    const loadPoll = window.setInterval(() => {
      if (map.isStyleLoaded()) {
        setMapLoaded(true)
        window.clearInterval(loadPoll)
      }
    }, 400)
    window.setTimeout(() => window.clearInterval(loadPoll), 15000)
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // --- Click: a field under the cursor selects it; empty map adds a point. ---
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const handler = (e: maplibregl.MapMouseEvent) => {
      const click: Pt = { x: e.point.x, y: e.point.y }
      for (const f of fieldsRef.current) {
        const ring = ringOf(f)
        if (ring.length === 0) continue
        const pts = ring.map(([lng, lat]) => {
          const p = map.project([lng, lat] as never)
          return { x: p.x, y: p.y }
        })
        if (pointInPolygon(click, pts)) {
          fieldClickRef.current?.(f.id)
          return
        }
      }
      mapClickRef.current?.([e.lngLat.lng, e.lngLat.lat])
    }
    map.on('click', handler)
    return () => { map.off('click', handler) }
  }, [])

  // --- Focus the selected field ---
  useEffect(() => {
    const map = mapRef.current
    if (!map || !selectedFieldId) return
    const f = fields.find((x) => x.id === selectedFieldId)
    if (!f) return
    const ring = ringOf(f)
    if (ring.length === 0) return
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const [x, y] of ring) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x)
      minY = Math.min(minY, y); maxY = Math.max(maxY, y)
    }
    map.fitBounds([[minX, minY], [maxX, maxY]] as never, { padding: 80, duration: 800 })
  }, [selectedFieldId, fields])

  // --- SVG overlay: field outlines + path polyline + numbered waypoints ---
  const overlay = useMemo(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return null
    const project = (lngLat: LngLat): string => {
      const p = map.project(lngLat as never)
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`
    }
    const fieldEls = fields.map((f) => {
      const ring = ringOf(f)
      if (ring.length === 0) return null
      const closed =
        ring.length > 0 && (ring[0][0] !== ring[ring.length - 1][0] || ring[0][1] !== ring[ring.length - 1][1])
          ? [...ring, ring[0]]
          : ring
      const pts = closed.map(project).join(' ')
      const isSel = f.id === selectedFieldId
      const centre = polygonCentroid(ring)
      const cp = map.project(centre as never)
      return (
        <g key={f.id}>
          <polygon
            points={pts}
            fill={isSel ? 'rgba(50,143,151,0.45)' : 'rgba(79,184,178,0.28)'}
            stroke={isSel ? '#f1d46a' : '#ffffff'}
            strokeWidth={isSel ? 3 : 2.5}
            strokeLinejoin="round"
          />
          <circle cx={cp.x} cy={cp.y} r={5} fill="#ffffff" stroke="#1d3a2a" strokeWidth={2} />
        </g>
      )
    })
    const pathEls = []
    if (points.length > 1) {
      pathEls.push(
        <polyline
          key="path-line"
          points={points.map(project).join(' ')}
          fill="none"
          stroke="#f59e0b"
          strokeWidth={3.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />,
      )
    }
    points.forEach((pt, i) => {
      const p = map.project(pt as never)
      pathEls.push(
        <g key={`wp-${i}`}>
          <circle cx={p.x} cy={p.y} r={10} fill="#f59e0b" stroke="#ffffff" strokeWidth={2} />
          <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize={10} fontWeight={700} fill="#ffffff">
            {i + 1}
          </text>
        </g>,
      )
    })
    return (
      <>
        {fieldEls}
        {pathEls}
      </>
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields, selectedFieldId, points, mapLoaded, mapTick])

  return (
    <div className={'relative h-full w-full overflow-hidden rounded-xl ' + (className ?? '')}>
      <div ref={containerRef} className="h-full w-full" />
      <svg className="pointer-events-none absolute inset-0 z-[5] h-full w-full">{overlay}</svg>
      <div className="pointer-events-none absolute bottom-2 left-2 z-10 rounded-md bg-black/60 px-2 py-1 text-[11px] text-white">
        Click a field to select it · click empty map to add a path point
      </div>
    </div>
  )
}
