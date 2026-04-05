/**
 * TitleBanner — displays the site title with two independent timed effects:
 *
 *   Glitch:      CSS vhsGlitch animation, triggered at random intervals.
 *                Hard RGB channel-separation + clip-path horizontal tears.
 *
 *   Color cycle: CSS colorCycle animation for smooth gradated color shifting,
 *                triggered at random intervals and running for duration_ms.
 *
 * Font family, size, and weight are driven by the fonts.title config.
 * The border fits the text width rather than spanning the full parent.
 */
import { useEffect, useState } from 'react'

function rand(min, max) {
  return min + Math.random() * (max - min)
}

export default function TitleBanner({ siteTitle, timing, fonts }) {
  const [glitching, setGlitching] = useState(false)
  const [isCycling, setIsCycling] = useState(false)

  const gt = timing?.glitch      ?? {}
  const ct = timing?.color_cycle ?? {}
  const tf = fonts?.title        ?? {}

  // ── Glitch loop ─────────────────────────────────────────────────────────────
  useEffect(() => {
    let tid
    function schedule() {
      const delay = rand(
        (gt.interval_min_s ?? 8)  * 1000,
        (gt.interval_max_s ?? 20) * 1000,
      )
      tid = setTimeout(() => {
        setGlitching(true)
        tid = setTimeout(() => {
          setGlitching(false)
          schedule()
        }, gt.duration_ms ?? 400)
      }, delay)
    }
    schedule()
    return () => clearTimeout(tid)
  }, [gt.interval_min_s, gt.interval_max_s, gt.duration_ms])

  // ── Color cycle loop ─────────────────────────────────────────────────────────
  // Uses CSS colorCycle animation for smooth gradated shifts — no JS color stepping.
  useEffect(() => {
    let tid
    function schedule() {
      const delay = rand(
        (ct.interval_min_s ?? 15) * 1000,
        (ct.interval_max_s ?? 40) * 1000,
      )
      tid = setTimeout(() => {
        setIsCycling(true)
        tid = setTimeout(() => {
          setIsCycling(false)
          schedule()
        }, ct.duration_ms ?? 3000)
      }, delay)
    }
    schedule()
    return () => clearTimeout(tid)
  }, [ct.interval_min_s, ct.interval_max_s, ct.duration_ms])

  const glitchDuration = gt.duration_ms ?? 400
  const cycleDuration  = ct.duration_ms ?? 3000

  // Build animation string: glitch and cycle are independent — both can be active.
  const animations = [
    glitching ? `vhsGlitch ${glitchDuration}ms steps(1) forwards` : null,
    isCycling ? `colorCycle ${cycleDuration}ms linear forwards`    : null,
  ].filter(Boolean).join(', ') || 'none'

  return (
    <div className="w-full flex justify-center">
      <div
        className="inline-block rounded px-4 py-2"
        style={{
          border:          '3px solid rgba(191, 95, 255, 0.5)',
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
        }}
      >
        <div
          style={{
            fontFamily:    tf.family ?? "'VCROSDMono', 'Courier New', monospace",
            fontSize:      tf.size   ?? '1.25rem',
            fontWeight:    tf.weight ?? 'bold',
            letterSpacing: '0.15em',
            userSelect:    'none',
            color:         isCycling ? undefined : '#ffffff',
            animation:     animations,
          }}
        >
          {siteTitle ?? 'dopelink'}
        </div>
      </div>
    </div>
  )
}
