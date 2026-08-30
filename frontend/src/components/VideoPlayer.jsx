/**
 * VideoPlayer — native HTML5 player with two streaming paths:
 *
 *   Static passthrough (needsTranscode=false, default):
 *     Plain <video> or <audio> element.  The browser drives seeking via HTTP
 *     Range headers which the proxy forwards to Jellyfin unchanged.
 *
 *   HLS transcoded (needsTranscode=true):
 *     hls.js fetches the rewritten m3u8 playlist from /api/hls/{uuid}/playlist.m3u8
 *     and loads each segment on demand.  Used for audio items with an
 *     incompatible codec (transcodes the whole stream to AAC) and for video
 *     items with an incompatible embedded audio codec, e.g. DTS/EAC3/TrueHD
 *     (remuxes with the video track copied untouched, only audio transcoded).
 *     Seeking is instant within cached segments and requires only a few
 *     seconds of new transcoding for uncached positions.  Buffer management
 *     is handled per-segment so no MSE quota issues arise regardless of length.
 *     Safari uses its native HLS support instead of hls.js.
 */
import { useEffect, useRef } from 'react'

// hls.js is only ever needed for the transcoded path below — a plain
// <video>/<audio> element handles every other case via direct Range-request
// passthrough. Dynamically imported so its ~30-40KB (gzipped) doesn't ship
// to every visitor, only the ones who actually hit a transcode-needed track.

// ── HLS player (transcoded path) ─────────────────────────────────────────────

async function mountHls(container, playlistUrl, savedVolume, isVideo) {
  const el = document.createElement(isVideo ? 'video' : 'audio')
  el.controls    = true
  el.style.width = '100%'
  if (isVideo) {
    el.style.maxHeight = '75vh'
    el.style.background = '#000'
    el.className = 'rounded-lg shadow-xl'
  } else {
    el.className = 'w-full rounded'
  }
  if (savedVolume !== null) el.volume = parseFloat(savedVolume)
  container.appendChild(el)

  let hls = null
  const { default: Hls } = await import('hls.js')

  if (Hls.isSupported()) {
    hls = new Hls({
      // Keep a modest back-buffer so recent seeks are instant without
      // holding the entire track in memory.
      backBufferLength: 60,
    })
    hls.loadSource(playlistUrl)
    hls.attachMedia(el)
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      el.play().catch(() => {})
    })
  } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
    // Safari supports HLS natively — no hls.js needed
    el.src = playlistUrl
    el.play().catch(() => {})
  }

  return function cleanup() {
    if (hls) {
      hls.destroy()
      hls = null
    }
    el.pause()
    el.src = ''
  }
}


// ── Component ─────────────────────────────────────────────────────────────────

export default function VideoPlayer({ streamUrl, isVideo, needsTranscode }) {
  const containerRef = useRef(null)
  const cleanupRef   = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return
    const container = containerRef.current

    // Tear down any existing player
    if (cleanupRef.current) {
      cleanupRef.current()
      cleanupRef.current = null
    }
    while (container.firstChild) container.removeChild(container.firstChild)

    const savedVolume = localStorage.getItem('player_volume')

    // ── HLS transcoded ────────────────────────────────────────────────────────
    // mountHls is async (dynamic hls.js import) — if this effect re-runs
    // again before it resolves, `torndown` lets the late-arriving mount clean
    // itself up immediately instead of clobbering whatever ran after it.
    if (needsTranscode) {
      let torndown = false
      mountHls(container, streamUrl, savedVolume, isVideo).then(cleanup => {
        if (torndown) { cleanup(); return }
        const el = container.querySelector(isVideo ? 'video' : 'audio')
        if (el) {
          el.addEventListener('volumechange', () =>
            localStorage.setItem('player_volume', String(el.volume))
          )
        }
        cleanupRef.current = cleanup
      })
      cleanupRef.current = () => { torndown = true }
      return
    }

    // ── Static passthrough ────────────────────────────────────────────────────
    const el = document.createElement(isVideo ? 'video' : 'audio')
    el.controls    = true
    el.autoplay    = true
    el.style.width = '100%'
    if (isVideo) {
      el.style.maxHeight = '75vh'
      el.style.background = '#000'
      el.className = 'rounded-lg shadow-xl'
    } else {
      el.className = 'w-full rounded'
    }
    if (savedVolume !== null) el.volume = parseFloat(savedVolume)
    el.addEventListener('volumechange', () =>
      localStorage.setItem('player_volume', String(el.volume))
    )
    el.src = streamUrl
    container.appendChild(el)
    el.play().catch(() => {})
    cleanupRef.current = () => { el.pause(); el.src = '' }
  }, [streamUrl, isVideo, needsTranscode])

  useEffect(() => {
    return () => { if (cleanupRef.current) cleanupRef.current() }
  }, [])

  return <div ref={containerRef} className="w-full" />
}
