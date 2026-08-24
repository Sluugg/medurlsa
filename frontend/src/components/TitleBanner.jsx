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
  const [glitching,   setGlitching]   = useState(false)
  const [isCycling,   setIsCycling]   = useState(false)
  const [jitterPhase, setJitterPhase] = useState(0)

  const gt = timing.glitch
  const ct = timing.color_cycle
  const jt = timing.jitter
  const pb = timing.pearl_border
  const tf = fonts.title

  // ── Glitch loop ─────────────────────────────────────────────────────────────
  useEffect(() => {
    let tid
    function schedule() {
      const delay = rand(
        gt.interval_min_s * 1000,
        gt.interval_max_s * 1000,
      )
      tid = setTimeout(() => {
        setGlitching(true)
        tid = setTimeout(() => {
          setGlitching(false)
          schedule()
        }, gt.duration_ms)
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
        ct.interval_min_s * 1000,
        ct.interval_max_s * 1000,
      )
      tid = setTimeout(() => {
        setIsCycling(true)
        tid = setTimeout(() => {
          setIsCycling(false)
          schedule()
        }, ct.duration_ms)
      }, delay)
    }
    schedule()
    return () => clearTimeout(tid)
  }, [ct.interval_min_s, ct.interval_max_s, ct.duration_ms])

  const glitchDuration    = gt.duration_ms
  const cycleDuration     = ct.duration_ms
  const jitterDelayMs     = jt.delay_ms
  const jitterDistPx      = jt.distance_px
  const pearlCycleRate    = pb.cycle_rate_s
  const pearlBorderWidth  = pb.border_width_px

  // ── Jitter loop ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const iid = setInterval(
      () => setJitterPhase(p => 1 - p),
      jitterDelayMs,
    )
    return () => clearInterval(iid)
  }, [jitterDelayMs])

  // Build animation string: glitch and cycle are independent — both can be active.
  const animations = [
    glitching ? `vhsGlitch ${glitchDuration}ms steps(1) forwards` : null,
    isCycling ? `colorCycle ${cycleDuration}ms linear forwards`    : null,
  ].filter(Boolean).join(', ') || 'none'

  return (
    <div className="w-full flex justify-center">
      <div
        className="pearl-border inline-block rounded px-4 py-2"
        style={{
          backgroundColor:       'rgba(5, 2, 18, 0.85)',
          '--pearl-border-width': `${pearlBorderWidth}px`,
          '--pearl-cycle-rate':   `${pearlCycleRate}s`,
        }}
      >
        <div
          style={{
            fontFamily:    tf.family,
            fontSize:      tf.size,
            fontWeight:    tf.weight,
            letterSpacing: '0.15em',
            userSelect:    'none',
            color:         isCycling ? undefined : '#ffffff',
            animation:     animations,
          }}
        >
          {[...siteTitle].map((char, i) => (
            <span
              key={i}
              style={{
                display:   'inline-block',
                transform: char === ' '
                  ? undefined
                  : `translateY(${jitterPhase * jitterDistPx * (i % 2 === 0 ? -1 : 1)}px)`,
              }}
            >
              {char === ' ' ? '\u00A0' : char}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
