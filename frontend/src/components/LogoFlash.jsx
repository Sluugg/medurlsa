/**
 * LogoFlash — fades the site logo in and out at random intervals in corner
 * safe zones. Independent timer from FlavorText — overlap is fine.
 * Only rendered when has_logo is true (logo_path configured and file exists).
 */
import { useEffect, useRef, useState } from 'react'

function rand(min, max) { return min + Math.random() * (max - min) }

const ZONES = [
  { top: [5,  12], left: [3,  12] },   // top-left
  { top: [5,  12], left: [80, 88] },   // top-right
  { top: [80, 88], left: [3,  12] },   // bottom-left
  { top: [80, 88], left: [80, 88] },   // bottom-right
]

function randomPos() {
  const z = ZONES[Math.floor(Math.random() * ZONES.length)]
  return {
    top:  rand(z.top[0],  z.top[1])  + '%',
    left: rand(z.left[0], z.left[1]) + '%',
  }
}

const FADE_MS = 700

export default function LogoFlash({ hasLogo, timing }) {
  const [visible, setVisible] = useState(false)
  const [opacity, setOpacity] = useState(0)
  const [pos, setPos]         = useState({ top: '5%', left: '5%' })
  const tid = useRef(null)

  const lf = timing.logo_flash

  useEffect(() => {
    if (!hasLogo) return

    function schedule() {
      const delay = rand(
        lf.interval_min_s * 1000,
        lf.interval_max_s * 1000,
      )
      tid.current = setTimeout(() => {
        setPos(randomPos())
        setVisible(true)
        requestAnimationFrame(() =>
          requestAnimationFrame(() => setOpacity(1))
        )

        tid.current = setTimeout(() => {
          setOpacity(0)
          tid.current = setTimeout(() => {
            setVisible(false)
            schedule()
          }, FADE_MS)
        }, lf.duration_ms)
      }, delay)
    }

    schedule()
    return () => clearTimeout(tid.current)
  }, [hasLogo, lf.interval_min_s, lf.interval_max_s, lf.duration_ms])

  if (!hasLogo) return null

  return (
    <img
      src="/api/logo"
      alt=""
      aria-hidden="true"
      style={{
        position:    'fixed',
        top:         pos.top,
        left:        pos.left,
        opacity,
        transition:  `opacity ${FADE_MS}ms ease`,
        maxWidth:    '72px',
        maxHeight:   '72px',
        objectFit:   'contain',
        pointerEvents: 'none',
        filter:      'drop-shadow(0 0 6px rgba(191, 0, 255, 0.65))',
        zIndex:      20,
        visibility:  visible ? 'visible' : 'hidden',
      }}
    />
  )
}
