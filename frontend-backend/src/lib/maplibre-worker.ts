import { setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// Vite pre-bundles maplibre-gl, so the worker URL MapLibre derives from
// `import.meta.url` points at the optimized dependency chunk — which has no
// sibling worker file, causing "Worker failed to load". Point it at the real
// worker asset emitted by Vite instead (valid in dev and production builds).
setWorkerUrl(workerUrl)
