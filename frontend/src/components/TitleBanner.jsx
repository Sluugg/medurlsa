/**
 * TitleBanner — displays the site title in VCR OSD Mono with two independent
 * timed effects driven by content_config timing values:
 *
 *   Glitch:      CSS vhsGlitch animation, triggered at random intervals.
 *                Hard RGB channel-separation + clip-path horizontal tears.
 *
 *   Color cycle: JS setInterval stepping through the synthwave palette,
 *                triggered at random intervals and running for duration_ms.
 */
import { useEffect, useRef, useState } from 'react'

const PALETTE = ['#ff00ff', '#00ffff', '#ff6ec7', '#ffff00', '#bf00ff', '#ffffff']

function rand(min, max) {
  return min + Math.random() * (max - min)
}

export default function TitleBanner({ siteTitle, timing }) {
  const [glitching, setGlitching]   = useState(false)
  const [cycleColor, setCycleColor] = useState(null)

  const gt = timing?.glitch      ?? {}
  const ct = timing?.color_cycle ?? {}

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
  useEffect(() => {
    let tid, iid
    function schedule() {
      const delay = rand(
        (ct.interval_min_s ?? 15) * 1000,
        (ct.interval_max_s ?? 40) * 1000,
      )
      tid = setTimeout(() => {
        let idx = 0
        iid = setInterval(() => {
          setCycleColor(PALETTE[idx % PALETTE.length])
          idx++
        }, ct.rate_ms ?? 300)

        tid = setTimeout(() => {
          clearInterval(iid)
          setCycleColor(null)
          schedule()
        }, ct.duration_ms ?? 3000)
      }, delay)
    }
    schedule()
    return () => { clearTimeout(tid); clearInterval(iid) }
  }, [ct.interval_min_s, ct.interval_max_s, ct.duration_ms, ct.rate_ms])

  const glitchDuration = gt.duration_ms ?? 400

  return (
    <div
      className="w-full rounded px-4 py-2 text-center"
      style={{
        border:          '1px solid rgba(191, 95, 255, 0.5)',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
      }}
    >
      <div
        style={{
          fontFamily: "'VCROSDMono', 'Courier New', monospace",
          fontSize:   '1.25rem',
          fontWeight: 'bold',
          letterSpacing: '0.15em',
          userSelect: 'none',
          color:      cycleColor ?? '#ffffff',
          animation:  glitching
            ? `vhsGlitch ${glitchDuration}ms steps(1) forwards`
            : 'none',
        }}
      >
        {siteTitle ?? 'dopelink'}
      </div>
    </div>
  )
}
