import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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

const DRAW_SOURCE = 'fieldshift-draw'

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
  const srcRef = useRef<string>('fieldshift-fields')

  const [basemap, setBasemap] = useState<Basemap>('satellite')
  const [points, setPoints] = useState<LngLat[]>([])
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  const pointsRef = useRef<LngLat[]>([])
  const drawModeRef = useRef(drawMode)
  drawModeRef.current = drawMode
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
      map.addSource(srcRef.current, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'field-fill', type: 'fill', source: srcRef.current, paint: { 'fill-color': '#4fb8b2', 'fill-opacity': 0.28 } })
      map.addLayer({ id: 'field-line', type: 'line', source: srcRef.current, paint: { 'line-color': '#2f6a4a', 'line-width': 2 } })
      // Drawing preview: live boundary line, translucent fill, vertex dots.
      map.addSource(DRAW_SOURCE, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'draw-fill', type: 'fill', source: DRAW_SOURCE, paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.25 } })
      map.addLayer({ id: 'draw-line', type: 'line', source: DRAW_SOURCE, paint: { 'line-color': '#f59e0b', 'line-width': 3 } })
      map.addLayer({ id: 'draw-points', type: 'circle', source: DRAW_SOURCE, paint: { 'circle-radius': 5, 'circle-color': '#ffffff', 'circle-stroke-color': '#f59e0b', 'circle-stroke-width': 2 } })
    })
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

  // --- Render saved fields ---------------------------------------------------
  const features = useMemo(() => {
    return fields.map((f) => ({
      type: 'Feature' as const,
      id: f.id,
      properties: { selected: f.id === selectedId },
      geometry: { type: 'Polygon', coordinates: f.geometry.coordinates },
    }))
  }, [fields, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getSource(srcRef.current)) return
    ;(map.getSource(srcRef.current) as unknown as maplibregl.GeoJSONSource)?.setData({ type: 'FeatureCollection', features } as never)
    if (selectedId) {
      const f = fields.find((x) => x.id === selectedId)
      if (f) {
        map.setPaintProperty('field-fill', 'fill-color', f.id === selectedId ? '#328f97' : '#4fb8b2')
        map.setPaintProperty('field-line', 'line-color', '#2f6a4a')
      }
    }
  }, [features, fields, selectedId])

  // --- Render drawing preview -----------------------------------------------
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.getSource(DRAW_SOURCE)) return
    const lineCoords: LngLat[] = cursor && points.length > 0 ? [...points, [cursor.lng, cursor.lat]] : points
    const feats: Array<Record<string, unknown>> = []
    if (points.length >= 3) {
      const closed = [...points, points[0]]
      feats.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [closed] }, properties: {} })
    }
    if (lineCoords.length >= 2) {
      feats.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: lineCoords }, properties: {} })
    }
    if (points.length > 0) {
      feats.push({ type: 'Feature', geometry: { type: 'MultiPoint', coordinates: points }, properties: {} })
    }
    ;(map.getSource(DRAW_SOURCE) as unknown as maplibregl.GeoJSONSource)?.setData({ type: 'FeatureCollection', features: feats } as never)
  }, [points, cursor])

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
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const handler = (e: maplibregl.MapMouseEvent) => {
      if (drawModeRef.current) return
      const feats = map.queryRenderedFeatures(e.point, { layers: ['field-fill'] })
      const id = feats[0]?.id as string | undefined
      if (id && onSelect) onSelect(id)
    }
    map.on('click', 'field-fill', handler as never)
    return () => { map.off('click', 'field-fill', handler as never) }
  }, [onSelect])

  // --- Drawing interactions --------------------------------------------------
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

    const onClick = (e: maplibregl.MapMouseEvent) => {
      const next = [...pointsRef.current, [e.lngLat.lng, e.lngLat.lat] as LngLat]
      setDrawPoints(next)
    }
    const onMouseMove = (e: maplibregl.MapMouseEvent) => {
      setCursor({ lng: e.lngLat.lng, lat: e.lngLat.lat })
    }
    const onDblClick = (e: maplibregl.MapMouseEvent) => {
      e.preventDefault()
      finishDrawing()
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancelDrawing()
      if (e.key === 'Enter' && pointsRef.current.length >= 3) finishDrawing()
    }
    map.on('click', onClick)
    map.on('mousemove', onMouseMove)
    map.on('dblclick', onDblClick)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      map.off('click', onClick)
      map.off('mousemove', onMouseMove)
      map.off('dblclick', onDblClick)
      window.removeEventListener('keydown', onKeyDown)
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
