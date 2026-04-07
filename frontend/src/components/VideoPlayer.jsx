/**
 * VideoPlayer — native HTML5 player with two streaming paths:
 *
 *   Static passthrough (default):
 *     Plain <video> or <audio> element. The browser drives seeking via HTTP
 *     Range headers which the proxy forwards to Jellyfin unchanged.
 *
 *   Transcoded audio (needsTranscode=true):
 *     Uses the MediaSource Extensions API to feed raw ADTS AAC chunks from
 *     Jellyfin's transcoding endpoint into an <audio> element.  Because ADTS
 *     has no embedded timestamps, we control placement via SourceBuffer
 *     timestampOffset — on seek we abort the active fetch, clear the buffer,
 *     and start a new fetch from the sought position with StartTimeTicks,
 *     setting timestampOffset to the seek time so the browser timeline stays
 *     correct.  durationSeconds (stored at link-creation time) is applied to
 *     MediaSource.duration so the progress bar is fully interactive.
 */
import { useEffect, useRef } from 'react'

// ── MSE transcoded-audio player ──────────────────────────────────────────────

function mountTranscodedAudio(container, streamBaseUrl, durationSeconds, savedVolume) {
  const audio = document.createElement('audio')
  audio.controls     = true
  audio.style.width  = '100%'
  audio.className    = 'w-full rounded'
  if (savedVolume !== null) audio.volume = parseFloat(savedVolume)

  const ms        = new MediaSource()
  const objectUrl = URL.createObjectURL(ms)
  audio.src       = objectUrl
  container.appendChild(audio)

  let sb               = null
  let activeController = null
  let seekVersion      = 0

  function waitForSb() {
    return new Promise(resolve => {
      if (!sb || !sb.updating) return resolve()
      sb.addEventListener('updateend', resolve, { once: true })
    })
  }

  async function fetchAndAppend(startTicks, timeOffset, version) {
    if (activeController) activeController.abort()
    const ctrl = new AbortController()
    activeController = ctrl

    const url = `${streamBaseUrl}&start_ticks=${startTicks}`
    try {
      const resp = await fetch(url, { signal: ctrl.signal })
      if (!resp.ok) throw new Error(`upstream ${resp.status}`)

      sb.timestampOffset = timeOffset
      const reader = resp.body.getReader()

      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          if (!ctrl.signal.aborted && version === seekVersion) ms.endOfStream()
          break
        }
        await waitForSb()
        if (ctrl.signal.aborted || version !== seekVersion) break
        sb.appendBuffer(value)
      }
    } catch (e) {
      if (e.name !== 'AbortError') console.error('Transcode stream error:', e)
    }
  }

  ms.addEventListener('sourceopen', () => {
    if (durationSeconds) ms.duration = durationSeconds
    sb = ms.addSourceBuffer('audio/aac')

    audio.addEventListener('seeking', async () => {
      const version  = ++seekVersion
      const seekTime = audio.currentTime

      if (activeController) activeController.abort()
      await waitForSb()
      if (version !== seekVersion) return

      sb.abort()
      const end = isFinite(ms.duration) ? ms.duration : Number.MAX_SAFE_INTEGER
      if (sb.buffered.length > 0) {
        sb.remove(0, end)
        await waitForSb()
      }
      if (version !== seekVersion) return

      const ticks = Math.round(seekTime * 10_000_000)
      await fetchAndAppend(ticks, seekTime, version)
    })

    fetchAndAppend(0, 0, seekVersion)
  }, { once: true })

  return function cleanup() {
    if (activeController) activeController.abort()
    audio.pause()
    audio.src = ''
    URL.revokeObjectURL(objectUrl)
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function VideoPlayer({ streamUrl, isVideo, needsTranscode, durationSeconds }) {
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

    // ── Transcoded audio path ─────────────────────────────────────────────────
    if (!isVideo && needsTranscode) {
      const cleanup = mountTranscodedAudio(
        container, streamUrl, durationSeconds, savedVolume,
      )
      // volume persistence is set inside mountTranscodedAudio via the element ref;
      // wire volumechange here so we can get it from the appended child
      const el = container.querySelector('audio')
      if (el) {
        el.addEventListener('volumechange', () =>
          localStorage.setItem('player_volume', String(el.volume))
        )
        el.play().catch(() => {})
      }
      cleanupRef.current = cleanup
      return
    }

    // ── Static passthrough path ───────────────────────────────────────────────
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
  }, [streamUrl, isVideo, needsTranscode, durationSeconds])

  // Cleanup on unmount
  useEffect(() => {
    return () => { if (cleanupRef.current) cleanupRef.current() }
  }, [])

  return <div ref={containerRef} className="w-full" />
}
