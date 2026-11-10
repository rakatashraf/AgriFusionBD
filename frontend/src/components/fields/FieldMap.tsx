import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Search, Satellite, Map as MapIcon, Undo2, Check, X, Crosshair } from 'lucide-react'
import type { Field } from '#/lib/types'
import { geodesicAreaSqM, formatAreaLine, formatCoord, type LngLat } from '#/lib/geo'

export interface DrawPreview {
  points: LngLat[]
  areaSqM: number
  cursor: { lng: number; lat: number } | null
}

interface Props {
  fields: Field[]
  selectedId?: string
  onSelect?: (id: string) => void
  /** When set, the map centers on this field and disables panning off it. */
  focusId?: string
  className?: string
  /** When true, clicks draw a land boundary instead of selecting a field. */
  drawMode?: boolean
  /** Live drawing state: points so far, current area, cursor position. */
  onDrawPreview?: (preview: DrawPreview) => void
  /** Fired when the user closes a boundary (double-click or Finish). */
  onDrawComplete?: (ring: LngLat[]) => void
  /** Fired when the user cancels drawing (Cancel button or Escape). */
  onDrawCancel?: () => void
}

type Basemap = 'satellite' | 'streets'

// Satellite imagery: Esri World Imagery (free, no key) — the clearest
// satellite tiles available without an API key. This is the latest imagery
// the provider has published, not a real-time live feed.
const ESRI_SAT_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
]
const ESRI_REF_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
]
const OSM_TILES = [
  'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
  'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
  'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
]

const STYLE = {
  version: 8,
  sources: {
    sat: {
      type: 'raster',
      tiles: ESRI_SAT_TILES,
      tileSize: 256,
      // Esri has no imagery beyond ~z18 in this region; capping the source
      // (and the map) stops the grey "Map data not yet available" tiles
      // that appear when a user zooms in further.
      maxzoom: 18,
      attribution: 'Esri, Maxar, Earthstar Geographics',
    },
    satRef: {
      type: 'raster',
      tiles: ESRI_REF_TILES,
      tileSize: 256,
      attribution: 'Esri',
    },
    osm: {
      type: 'raster',
      tiles: OSM_TILES,
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#0a1418' } },
    { id: 'sat', type: 'raster', source: 'sat', paint: { 'raster-opacity': 1 } },
    { id: 'sat-ref', type: 'raster', source: 'satRef', paint: { 'raster-opacity': 0.9 } },
    { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-opacity': 1 }, layout: { visibility: 'none' } },
  ],
} as never

function boundsOf(field: Field) {
  const ring = field.geometry.coordinates[0]
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const [x, y] of ring) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x)
    minY = Math.min(minY, y); maxY = Math.max(maxY, y)
  }
  return [[minX, minY], [maxX, maxY]]
}

// --- Screen-pixel geometry for precise corner / edge picking ------------------
// Drawing works by clicking the land's real corners and edges in the
// satellite view. A click is matched in screen pixels (not degrees) so the
// tolerance feels the same at any zoom: near a corner it grabs that corner
// (drag to move it), near an edge it drops a new point onto that edge.

type Pt = { x: number; y: number }

function distToSegment(p: Pt, a: Pt, b: Pt): { d: number; t: number } {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len2 = dx * dx + dy * dy
  let t = len2 === 0 ? 0 : ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2
  t = Math.max(0, Math.min(1, t))
  const cx = a.x + t * dx
  const cy = a.y + t * dy
  return { d: Math.hypot(p.x - cx, p.y - cy), t }
}

// Ray-casting point-in-polygon test in screen pixels, for selecting a
// field by clicking it on the map (the GeoJSON layer click no longer
// exists — field outlines are drawn as an SVG overlay, see below).
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

export default function FieldMap({
  fields,
  selectedId,
  onSelect,
  focusId,
  className,
  drawMode = false,
  onDrawPreview,
  onDrawComplete,
  onDrawCancel,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  const [basemap, setBasemap] = useState<Basemap>('satellite')
  const [points, setPoints] = useState<LngLat[]>([])
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  // True once the map style has loaded and the GeoJSON sources/layers exist.
  // The data-setting effects below depend on this so they re-run (and actually
  // push data into the sources) once the map is ready — otherwise a fetch
  // that resolves before the map loads leaves every polygon invisible.
  const [mapLoaded, setMapLoaded] = useState(false)
  // Bumps on every map move/pan/zoom so the SVG overlay (which projects
  // geographic coordinates to screen pixels) re-renders in step.
  const [mapTick, setMapTick] = useState(0)

  const pointsRef = useRef<LngLat[]>([])
  const drawModeRef = useRef(drawMode)
  drawModeRef.current = drawMode
  // Which corner is being dragged (index into points), or -1.
  const dragIndexRef = useRef(-1)
  // Screen position where the current press started (to tell a click from a pan).
  const downPosRef = useRef<Pt | null>(null)
  const previewRef = useRef(onDrawPreview)
  previewRef.current = onDrawPreview
  const completeRef = useRef(onDrawComplete)
  completeRef.current = onDrawComplete
  const cancelRef = useRef(onDrawCancel)
  cancelRef.current = onDrawCancel

  const focus = focusId ? fields.find((f) => f.id === focusId) : undefined
  const drawAreaSqM = useMemo(() => geodesicAreaSqM(points), [points])

  const setDrawPoints = useCallback((next: LngLat[]) => {
    pointsRef.current = next
    setPoints(next)
  }, [])

  const clearDrawing = useCallback(() => {
    setDrawPoints([])
    setCursor(null)
  }, [setDrawPoints])

  const finishDrawing = useCallback(() => {
    const pts = pointsRef.current
    if (pts.length < 3) return
    const ring = pts.slice()
    clearDrawing()
    completeRef.current?.(ring)
  }, [clearDrawing])

  const cancelDrawing = useCallback(() => {
    clearDrawing()
    cancelRef.current?.()
  }, [clearDrawing])

  // --- Map setup (once) ------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [88.61, 25.34],
      zoom: 11.5,
      // Keep the user inside the zoom range where satellite imagery exists.
      // Beyond ~z18 Esri returns blank "not yet available" tiles.
      maxZoom: 18,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
        showUserLocation: true,
      }),
      'top-right',
    )
    map.on('load', () => {
      // Field outlines and the draw preview are drawn as an SVG overlay
      // (see the overlay memo below), not as MapLibre GeoJSON layers:
      // the GeoJSON layers never painted on this site although the data
      // was correct, so the overlay bypasses that renderer entirely.
      setMapLoaded(true)
    })
    // Re-project the SVG overlay on every pan / zoom / rotate.
    map.on('move', () => setMapTick((t) => t + 1))
    // Fallback: if the 'load' event is ever missed (inline style racing
    // the handler), poll until the style is loaded and mark the map
    // loaded then. Without this, every data effect gated on mapLoaded
    // would never run and no polygon would ever render.
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

  // --- Basemap toggle --------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const apply = () => {
      if (basemap === 'satellite') {
        map.setLayoutProperty('sat', 'visibility', 'visible')
        map.setLayoutProperty('sat-ref', 'visibility', 'visible')
        map.setLayoutProperty('osm', 'visibility', 'none')
      } else {
        map.setLayoutProperty('sat', 'visibility', 'none')
        map.setLayoutProperty('sat-ref', 'visibility', 'none')
        map.setLayoutProperty('osm', 'visibility', 'visible')
      }
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [basemap])

  // --- SVG overlay: saved fields + draw preview ---------------------------
  // The map's GeoJSON layers never painted on this site (data was correct,
  // sources/layers existed, setData ran — yet nothing rendered, through
  // five fix rounds). So field outlines and the draw preview are drawn as
  // a plain SVG overlay positioned over the map container, projecting
  // geographic coordinates to screen pixels with map.project(). This is
  // ordinary DOM — it cannot fail the way the layer renderer did. It
  // re-projects on every map move via mapTick.
  const closedRings = useMemo(() => {
    return fields.map((f) => {
      const ring = f.geometry.coordinates[0] as LngLat[]
      const closed =
        ring.length > 0 &&
        (ring[0][0] !== ring[ring.length - 1][0] ||
          ring[0][1] !== ring[ring.length - 1][1])
          ? [...ring, ring[0]]
          : ring
      return { id: f.id, ring: closed }
    })
  }, [fields])

  const overlay = useMemo(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return null
    const project = (lngLat: LngLat): string => {
      const p = map.project(lngLat as never)
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`
    }
    const fieldEls = closedRings.map(({ id, ring }) => {
      const pts = ring.map(project).join(' ')
      const isSel = id === selectedId
      return (
        <polygon
          key={id}
          points={pts}
          fill={isSel ? 'rgba(50,143,151,0.45)' : 'rgba(79,184,178,0.28)'}
          stroke={isSel ? '#1d3a2a' : '#2f6a4a'}
          strokeWidth={isSel ? 3 : 2}
          strokeLinejoin="round"
        />
      )
    })
    const drawEls: ReactNode[] = []
    if (points.length >= 3) {
      const closed = [...points, points[0]]
      drawEls.push(
        <polygon
          key="draw-fill"
          points={closed.map(project).join(' ')}
          fill="rgba(245,158,11,0.25)"
          stroke="#f59e0b"
          strokeWidth={3}
          strokeLinejoin="round"
        />,
      )
    }
    if (points.length > 0 && cursor) {
      const line = [...points, [cursor.lng, cursor.lat] as LngLat]
      drawEls.push(
        <polyline
          key="draw-line"
          points={line.map(project).join(' ')}
          fill="none"
          stroke="#f59e0b"
          strokeWidth={3}
          strokeLinejoin="round"
        />,
      )
    }
    points.forEach((pt, i) => {
      const p = map.project(pt as never)
      drawEls.push(
        <circle key={`draw-pt-${i}`} cx={p.x} cy={p.y} r={7} fill="#ffffff" stroke="#f59e0b" strokeWidth={2.5} />,
      )
    })
    return (
      <>
        {fieldEls}
        {drawEls}
      </>
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closedRings, selectedId, points, cursor, mapLoaded, mapTick])

  // --- Live preview callback (area + cursor) ---------------------------------
  useEffect(() => {
    previewRef.current?.({ points, areaSqM: drawAreaSqM, cursor })
  }, [points, drawAreaSqM, cursor])

  // --- Focus on one field ----------------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !focus) return
    const b = boundsOf(focus)
    map.fitBounds(b as never, { padding: 60, duration: 800 })
  }, [focus])

  // --- Click handling: select the topmost field under the cursor. -----------
  // Point-in-polygon in screen pixels (the SVG overlay has no layer to
  // query). Only when not drawing.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const handler = (e: maplibregl.MapMouseEvent) => {
      if (drawModeRef.current) return
      const click: Pt = { x: e.point.x, y: e.point.y }
      for (const f of fields) {
        const ring = f.geometry.coordinates[0] as LngLat[]
        const pts = ring.map(([lng, lat]) => {
          const p = map.project([lng, lat] as never)
          return { x: p.x, y: p.y }
        })
        if (pointInPolygon(click, pts)) {
          if (onSelect) onSelect(f.id)
          return
        }
      }
    }
    map.on('click', handler)
    return () => { map.off('click', handler) }
  }, [fields, onSelect])

  // --- Drawing interactions --------------------------------------------------
  // Click a corner of the land to place it. Click on an edge to drop a new
  // point onto that edge. Drag a corner to move it exactly where it belongs.
  // A press that moves is a map pan, not a point — so tracing a boundary
  // never drops stray corners while panning.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (!drawMode) {
      map.doubleClickZoom.enable()
      map.getCanvas().style.cursor = ''
      return
    }
    map.doubleClickZoom.disable()
    map.getCanvas().style.cursor = 'crosshair'

    const GRAB_PX = 14 // how close a click must be to a corner / edge to grab it
    const CLICK_PX = 6 // a press that moves less than this is a click, not a pan

    const onMouseDown = (e: maplibregl.MapMouseEvent) => {
      downPosRef.current = { x: e.point.x, y: e.point.y }
      // Grab a corner: the nearest vertex within GRAB_PX starts a drag.
      const pts = pointsRef.current
      let best = -1
      let bestD = GRAB_PX
      for (let i = 0; i < pts.length; i++) {
        const s = map.project(pts[i] as never)
        const d = Math.hypot(s.x - e.point.x, s.y - e.point.y)
        if (d < bestD) {
          bestD = d
          best = i
        }
      }
      if (best >= 0) {
        dragIndexRef.current = best
        map.dragPan.disable()
        map.getCanvas().style.cursor = 'grabbing'
      }
    }

    const onMouseMove = (e: maplibregl.MapMouseEvent) => {
      if (dragIndexRef.current >= 0) {
        const pts = pointsRef.current.slice()
        pts[dragIndexRef.current] = [e.lngLat.lng, e.lngLat.lat]
        setDrawPoints(pts)
        return
      }
      setCursor({ lng: e.lngLat.lng, lat: e.lngLat.lat })
    }

    const onMouseUp = (e: maplibregl.MapMouseEvent) => {
      if (dragIndexRef.current >= 0) {
        dragIndexRef.current = -1
        map.dragPan.enable()
        map.getCanvas().style.cursor = 'crosshair'
        return
      }
      const down = downPosRef.current
      downPosRef.current = null
      if (!down) return
      // A press that moved is a pan — do not drop a point.
      if (Math.hypot(e.point.x - down.x, e.point.y - down.y) > CLICK_PX) return
      const pts = pointsRef.current
      const click: Pt = { x: e.point.x, y: e.point.y }
      // Click on an edge: drop a new point onto the nearest edge segment.
      if (pts.length >= 2) {
        let bestEdge = -1
        let bestD = GRAB_PX
        let bestT = 0
        for (let i = 0; i < pts.length; i++) {
          const a = map.project(pts[i] as never)
          const b = map.project(pts[(i + 1) % pts.length] as never)
          const { d, t } = distToSegment(click, a, b)
          if (d < bestD) {
            bestD = d
            bestEdge = i
            bestT = t
          }
        }
        // Only insert on an edge when the click is clearly on the edge and
        // not on top of an existing corner (corners are handled by drag).
        if (bestEdge >= 0 && bestT > 0.02 && bestT < 0.98) {
          const a = pts[bestEdge]
          const b = pts[(bestEdge + 1) % pts.length]
          const inserted: LngLat = [
            a[0] + (b[0] - a[0]) * bestT,
            a[1] + (b[1] - a[1]) * bestT,
          ]
          const next = pts.slice()
          next.splice(bestEdge + 1, 0, inserted)
          setDrawPoints(next)
          return
        }
      }
      // Otherwise this click places a new corner exactly where it landed.
      setDrawPoints([...pts, [e.lngLat.lng, e.lngLat.lat] as LngLat])
    }

    const onDblClick = (e: maplibregl.MapMouseEvent) => {
      e.preventDefault()
      finishDrawing()
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancelDrawing()
      if (e.key === 'Enter' && pointsRef.current.length >= 3) finishDrawing()
    }
    map.on('mousedown', onMouseDown)
    map.on('mousemove', onMouseMove)
    map.on('mouseup', onMouseUp)
    map.on('dblclick', onDblClick)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      map.off('mousedown', onMouseDown)
      map.off('mousemove', onMouseMove)
      map.off('mouseup', onMouseUp)
      map.off('dblclick', onDblClick)
      window.removeEventListener('keydown', onKeyDown)
      dragIndexRef.current = -1
      downPosRef.current = null
      map.dragPan.enable()
      map.doubleClickZoom.enable()
      map.getCanvas().style.cursor = ''
    }
  }, [drawMode, finishDrawing, cancelDrawing, setDrawPoints])

  // Reset the sketch whenever draw mode is switched off from outside.
  useEffect(() => {
    if (!drawMode) {
      setDrawPoints([])
      setCursor(null)
    }
  }, [drawMode, setDrawPoints])

  // --- Place search (Nominatim, biased to Bangladesh) ------------------------
  const runSearch = async () => {
    const q = searchQuery.trim()
    if (!q || searching) return
    setSearching(true)
    setSearchError(null)
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=bd&q=${encodeURIComponent(q)}`,
        { headers: { Accept: 'application/json' } },
      )
      if (!res.ok) throw new Error(`search failed (${res.status})`)
      const results = (await res.json()) as Array<{ lat: string; lon: string; display_name: string }>
      if (!results.length) {
        setSearchError('Place not found. Try a village, upazila or district name.')
        return
      }
      const map = mapRef.current
      if (!map) return
      map.flyTo({
        center: [Number(results[0].lon), Number(results[0].lat)],
        zoom: 15,
        duration: 1200,
      })
    } catch {
      setSearchError('Search is unavailable right now. Pan and zoom the map instead.')
    } finally {
      setSearching(false)
    }
  }

  const undoPoint = () => {
    setDrawPoints(pointsRef.current.slice(0, -1))
  }

  return (
    <div
      ref={containerRef}
      className={
        'relative h-full w-full overflow-hidden rounded-xl border border-border ' +
        (className ?? '')
      }
      role="application"
      aria-label="Field map"
    >
      {/* SVG overlay: field outlines + draw preview (plain DOM, always paints). */}
      <svg
        className="pointer-events-none absolute inset-0 z-[5] h-full w-full"
        aria-hidden="true"
      >
        {overlay}
      </svg>

      {/* Top-left toolbar: place search + basemap switch. */}
      <div className="pointer-events-none absolute left-3 top-3 z-10 flex flex-col gap-2">
        <form
          className="pointer-events-auto flex items-center gap-1 rounded-lg border border-border bg-card/95 p-1 shadow-sm backdrop-blur"
          onSubmit={(e) => {
            e.preventDefault()
            void runSearch()
          }}
        >
          <Search className="ml-1 size-4 shrink-0 text-muted-foreground" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search village / upazila…"
            aria-label="Search for a place"
            className="w-44 bg-transparent text-sm outline-none placeholder:text-muted-foreground sm:w-56"
          />
          <button
            type="submit"
            disabled={searching}
            className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground disabled:opacity-50"
          >
            {searching ? '…' : 'Go'}
          </button>
        </form>
        {searchError && (
          <p className="pointer-events-auto max-w-64 rounded-lg border border-destructive/40 bg-card/95 px-2 py-1 text-xs text-destructive shadow-sm">
            {searchError}
          </p>
        )}
        <div className="pointer-events-auto flex w-fit overflow-hidden rounded-lg border border-border bg-card/95 shadow-sm backdrop-blur">
          <button
            type="button"
            onClick={() => setBasemap('satellite')}
            aria-pressed={basemap === 'satellite'}
            className={
              'flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium ' +
              (basemap === 'satellite' ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-accent')
            }
          >
            <Satellite className="size-3.5" /> Satellite
          </button>
          <button
            type="button"
            onClick={() => setBasemap('streets')}
            aria-pressed={basemap === 'streets'}
            className={
              'flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium ' +
              (basemap === 'streets' ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-accent')
            }
          >
            <MapIcon className="size-3.5" /> Streets
          </button>
        </div>
        {basemap === 'satellite' && (
          <p className="pointer-events-none max-w-64 rounded-lg bg-black/55 px-2 py-1 text-[11px] leading-snug text-white">
            Satellite view — latest imagery from the provider. Zoom in close to see field edges clearly.
          </p>
        )}
      </div>

      {/* Drawing overlay: live readout + controls. */}
      {drawMode && (
        <>
          <div className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[calc(100%-1.5rem)] rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-sm backdrop-blur">
            <p className="font-medium text-foreground">
              Click each corner of your land to mark it
              {points.length > 0 ? ` — ${points.length} corner${points.length === 1 ? '' : 's'} placed` : ''}
            </p>
            <p className="mt-0.5 text-muted-foreground">
              Click on an edge to add a point there · Drag a corner to move it
            </p>
            <p className="mt-0.5 text-muted-foreground">
              Double-click or press Enter to finish · Esc to cancel
            </p>
            {points.length >= 3 && (
              <p className="mt-1 font-medium text-foreground">{formatAreaLine(drawAreaSqM)}</p>
            )}
            {cursor && (
              <p className="mt-0.5 tabular-nums text-muted-foreground">
                {formatCoord(cursor.lat)}, {formatCoord(cursor.lng)}
              </p>
            )}
          </div>
          <div className="pointer-events-auto absolute bottom-3 right-3 z-10 flex gap-2">
            <button
              type="button"
              onClick={undoPoint}
              disabled={points.length === 0}
              className="flex items-center gap-1 rounded-lg border border-border bg-card/95 px-2.5 py-1.5 text-xs font-medium shadow-sm backdrop-blur disabled:opacity-40"
            >
              <Undo2 className="size-3.5" /> Undo corner
            </button>
            <button
              type="button"
              onClick={cancelDrawing}
              className="flex items-center gap-1 rounded-lg border border-border bg-card/95 px-2.5 py-1.5 text-xs font-medium shadow-sm backdrop-blur"
            >
              <X className="size-3.5" /> Cancel
            </button>
            <button
              type="button"
              onClick={finishDrawing}
              disabled={points.length < 3}
              className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-sm disabled:opacity-40"
            >
              <Check className="size-3.5" /> Finish land
            </button>
          </div>
        </>
      )}

      {/* Hint to recenter on the user's own location (Geolocate control sits top-right). */}
      {!drawMode && (
        <p className="pointer-events-none absolute bottom-3 left-3 z-10 hidden items-center gap-1 rounded-lg bg-black/55 px-2 py-1 text-[11px] text-white sm:flex">
          <Crosshair className="size-3" /> Use the search box to jump to a village, or the target button (top-right) for your location
        </p>
      )}
    </div>
  )
}
