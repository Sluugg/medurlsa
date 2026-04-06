/**
 * Fetches /api/public/config once per page load.
 * Module-level cache means multiple components share a single request.
 */
import { useEffect, useState } from 'react'

const DEFAULT_CONFIG = {
  site_title:            'dopelink',
  has_logo:              false,
  flavor_texts:          [],
  available_backgrounds: [],
  timing: {
    pearl_border: { cycle_rate_s: 8, border_width_px: 2 },
    jitter:       { delay_ms: 300, distance_px: 4 },
    glitch:      { interval_min_s: 8,  interval_max_s: 20, duration_ms: 400 },
    color_cycle: { interval_min_s: 15, interval_max_s: 40, duration_ms: 3000, rate_ms: 300 },
    flavor_text: { interval_min_s: 12, interval_max_s: 25, duration_ms: 4000 },
    logo_flash:  { interval_min_s: 20, interval_max_s: 60, duration_ms: 3000 },
  },
  fonts: {
    title:       { family: "'VCROSDMono', 'Courier New', monospace", size: '1.25rem', weight: 'bold' },
    flavor_text: { family: "'VCROSDMono', 'Courier New', monospace", size: '0.7rem',  weight: 'normal' },
  },
}

let _cache   = null
let _promise = null

export default function useConfig() {
  const [config, setConfig]   = useState(_cache ?? DEFAULT_CONFIG)
  const [loading, setLoading] = useState(!_cache)

  useEffect(() => {
    if (_cache) return

    if (!_promise) {
      _promise = fetch('/api/public/config')
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(data => { _cache = data; return data })
        .catch(() => { _cache = DEFAULT_CONFIG; return DEFAULT_CONFIG })
    }

    _promise.then(data => {
      setConfig(data)
      setLoading(false)
    })
  }, [])

  return { config, loading }
}
