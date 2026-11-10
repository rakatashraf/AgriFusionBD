import { useEffect, useRef, useState } from 'react'

/**
 * Full-screen loading screen that plays the AgriFusion BD logo animation
 * once when the app first loads, then fades out to reveal the app.
 * Uses the 2-second logo-animation cut (the same animation as the
 * solution logo animation, concise for a loading screen).
 */
export default function LoadingScreen() {
  const [visible, setVisible] = useState(true)
  const [fading, setFading] = useState(false)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  useEffect(() => {
    // Fallback: hide even if the video fails to play or end.
    const fallback = window.setTimeout(() => {
      setFading(true)
      window.setTimeout(() => setVisible(false), 450)
    }, 2600)
    return () => window.clearTimeout(fallback)
  }, [])

  if (!visible) return null

  const finish = () => {
    setFading(true)
    window.setTimeout(() => setVisible(false), 450)
  }

  return (
    <div
      role="status"
      aria-label="Loading AgriFusion BD"
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center gap-5 bg-background transition-opacity duration-500 ${fading ? 'opacity-0' : 'opacity-100'}`}
    >
      <video
        ref={videoRef}
        src={`${import.meta.env.BASE_URL}logo-animation.mp4`}
        autoPlay
        muted
        playsInline
        onEnded={finish}
        onError={finish}
        className="size-44 rounded-full object-cover sm:size-56"
      />
      <div className="flex flex-col items-center gap-1">
        <span className="text-xl font-semibold tracking-tight">AgriFusion BD</span>
        <span className="text-sm text-muted-foreground">Agricultural Decision Support</span>
      </div>
    </div>
  )
}
