import { useEffect, useMemo, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Field } from '#/lib/types'

interface Props {
  fields: Field[]
  selectedId?: string
  onSelect?: (id: string) => void
  /** When set, the map centers on this field and disables panning off it. */
  focusId?: string
  className?: string
}

// OSM raster tiles for the pilot. A licensed basemap provider should be
// configured in production (report §4); OSM is the neutral default.
const STYLE: { version: 8; sources: Record<string, { type: 'raster'; tiles: string[]; tileSize: number; attribution: string }>; layers: Array<{ id: string; type: string; source?: string; paint?: Record<string, string | number> }> } = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: [
        'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#0a1418' } },
    { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.85 } },
  ],
}

function boundsOf(field: Field) {
  const ring = field.geometry.coordinates[0]
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const [x, y] of ring) {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x)
    minY = Math.min(minY, y); maxY = Math.max(maxY, y)
  }
  return [[minX, minY], [maxX, maxY]]
}

export default function FieldMap({ fields, selectedId, onSelect, focusId, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const srcRef = useRef<string>('fieldshift-fields')

  const focus = focusId ? fields.find((f) => f.id === focusId) : undefined

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE as never,
      center: [88.61, 25.34],
      zoom: 11.5,
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => {
      map.addSource(srcRef.current, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })
      map.addLayer({ id: 'field-fill', type: 'fill', source: srcRef.current, paint: { 'fill-color': '#4fb8b2', 'fill-opacity': 0.28 } })
      map.addLayer({ id: 'field-line', type: 'line', source: srcRef.current, paint: { 'line-color': '#2f6a4a', 'line-width': 2 } })
    })
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

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

  useEffect(() => {
    const map = mapRef.current
    if (!map || !focus) return
    const b = boundsOf(focus)
    map.fitBounds(b as never, { padding: 60, duration: 800 })
  }, [focus])

  // Click handling: select the topmost field under the cursor.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const handler = (e: maplibregl.MapMouseEvent) => {
      const feats = map.queryRenderedFeatures(e.point, { layers: ['field-fill'] })
      const id = feats[0]?.id as string | undefined
      if (id && onSelect) onSelect(id)
    }
    map.on('click', 'field-fill', handler as never)
    return () => { map.off('click', 'field-fill', handler as never) }
  }, [onSelect])

  return (
    <div
      ref={containerRef}
      className={
        'relative h-full w-full overflow-hidden rounded-xl border border-border ' +
        (className ?? '')
      }
      role="application"
      aria-label="Field map"
    />
  )
}
