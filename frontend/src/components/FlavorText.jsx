/**
 * FlavorText — picks a random string from the pool, positions it in one of
 * four corner safe zones (avoiding the central player area), fades it in,
 * holds it, fades it out, then waits a random interval before repeating.
 *
 * Double-rAF before fade-in ensures the element paints at opacity 0 first
 * so the CSS transition actually fires.
 */
import { useEffect, useRef, useState } from 'react'

function rand(min, max) { return min + Math.random() * (max - min) }

// Corner zones: [top%, left%] ranges — avoid the center 40% of the screen
const ZONES = [
  { top: [5,  15], left: [3,  18] },   // top-left
  { top: [5,  15], left: [72, 87] },   // top-right
  { top: [78, 88], left: [3,  18] },   // bottom-left
  { top: [78, 88], left: [60, 75] },   // bottom-right
]

function randomPos() {
  const z = ZONES[Math.floor(Math.random() * ZONES.length)]
  return {
    top:  rand(z.top[0],  z.top[1])  + '%',
    left: rand(z.left[0], z.left[1]) + '%',
  }
}

const FADE_MS = 600

export default function FlavorText({ texts, timing }) {
  const [visible, setVisible] = useState(false)
  const [opacity, setOpacity] = useState(0)
  const [text, setText]       = useState('')
  const [pos, setPos]         = useState({ top: '5%', left: '5%' })
  const tid = useRef(null)

  const ft = timing?.flavor_text ?? {}

  useEffect(() => {
    if (!texts || texts.length === 0) return

    function schedule() {
      const delay = rand(
        (ft.interval_min_s ?? 12) * 1000,
        (ft.interval_max_s ?? 25) * 1000,
      )
      tid.current = setTimeout(() => {
        setText(texts[Math.floor(Math.random() * texts.length)])
        setPos(randomPos())
        setVisible(true)

        // Double rAF: let browser paint at opacity 0 before transitioning to 1
        requestAnimationFrame(() =>
          requestAnimationFrame(() => setOpacity(1))
        )

        const holdMs = ft.duration_ms ?? 4000
        tid.current = setTimeout(() => {
          setOpacity(0)
          tid.current = setTimeout(() => {
            setVisible(false)
            schedule()
          }, FADE_MS)
        }, holdMs)
      }, delay)
    }

    schedule()
    return () => clearTimeout(tid.current)
  }, [texts, ft.interval_min_s, ft.interval_max_s, ft.duration_ms])

  if (!visible) return null

  return (
    <div
      style={{
        position:    'fixed',
        top:         pos.top,
        left:        pos.left,
        opacity,
        transition:  `opacity ${FADE_MS}ms ease`,
        fontFamily:  "'VCROSDMono', 'Courier New', monospace",
        fontSize:    '0.7rem',
        color:       '#c0b8ff',
        textShadow:  '0 0 8px rgba(192, 184, 255, 0.7)',
        pointerEvents: 'none',
        userSelect:  'none',
        maxWidth:    '18vw',
        lineHeight:  '1.4',
        zIndex:      20,
      }}
      aria-hidden="true"
    >
      {text}
    </div>
  )
}
