import { useEffect, useState } from 'react'

/**
 * Full-screen loading screen — cream screen with the AgriFusion BD logo,
 * matching the splash on the original agri-fusion-bd site.
 * Uses the static logo mark (lime circle with dark sprout) with a gentle
 * pulse. The logo-animation video is widescreen and starts on a blank
 * frame, so it does not read as a logo in a small circle — the static
 * mark is the reliable loading graphic.
 */
export default function LoadingScreen() {
  const [visible, setVisible] = useState(true)
  const [fading, setFading] = useState(false)

  useEffect(() => {
    const t1 = window.setTimeout(() => setFading(true), 2100)
    const t2 = window.setTimeout(() => setVisible(false), 2600)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
    }
  }, [])

  if (!visible) return null

  return (
    <div
      role="status"
      aria-label="Loading AgriFusion BD"
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center gap-5 bg-white transition-opacity duration-500 ${fading ? 'opacity-0' : 'opacity-100'}`}
    >
      <img
        src={`${import.meta.env.BASE_URL}agrifusion-logo.png`}
        alt="AgriFusion BD logo"
        className="size-40 animate-pulse rounded-full shadow-lg sm:size-48"
      />
      <div className="flex flex-col items-center gap-1">
        <span className="text-xl font-semibold tracking-tight text-[#1d3a2a]">AgriFusion BD</span>
        <span className="text-sm text-[#6e7c72]">Agricultural Decision Support</span>
      </div>
    </div>
  )
}
