import { defineConfig } from 'vite'
import { devtools } from '@tanstack/devtools-vite'

import { tanstackStart } from '@tanstack/react-start/plugin/vite'

import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { nitro } from 'nitro/vite'

// GitHub Pages static build: set PAGES_BUILD=true to build the frontend as a
// prerendered static SPA (no Node server, no Django backend) served from
// https://<user>.github.io/AgriFusionBD/. Normal (server) builds are unaffected.
const isPages = process.env.PAGES_BUILD === 'true'

const config = defineConfig({
  base: isPages ? '/AgriFusionBD/' : '/',
  resolve: { tsconfigPaths: true },
  server: {
    port: 3000,
    proxy: {
      // Dev: same-origin /api hits the Django backend (plan §5).
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  plugins: [
    devtools(),
    nitro({ rollupConfig: { external: [/^@sentry\//] } }),
    tailwindcss(),
    tanstackStart(
      isPages
        ? {
            // Serve the SPA from the /AgriFusionBD/ subpath on GitHub Pages.
            router: { basepath: '/AgriFusionBD' },
            spa: {
              enabled: true,
              prerender: { enabled: true, crawlLinks: true },
            },
          }
        : undefined,
    ),
    viteReact(),
  ],
})

export default config
