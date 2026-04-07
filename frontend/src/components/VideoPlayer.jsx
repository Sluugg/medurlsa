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
//
// Jellyfin's simple audio transcoding endpoint does not reliably honour
// StartTimeTicks, so server-side seek restarts don't work.  Instead we stream
// the full transcoded output into the MSE buffer from the start and let the
// browser seek natively within whatever has been buffered.  FFmpeg transcodes
// audio well above real-time, so the buffer fills quickly; seeking ahead of
// the buffer causes a brief stall (not a restart) until data arrives.
//
// Setting MediaSource.duration from the stored item value makes the progress
// bar fully interactive even before the buffer reaches the end.

function mountTranscodedAudio(container, streamUrl, durationSeconds, savedVolume) {
  const audio = document.createElement('audio')
  audio.controls    = true
  audio.style.width = '100%'
  audio.className   = 'w-full rounded'
  if (savedVolume !== null) audio.volume = parseFloat(savedVolume)

  const ms        = new MediaSource()
  const objectUrl = URL.createObjectURL(ms)
  audio.src       = objectUrl
  container.appendChild(audio)

  let sb               = null
  let activeController = null

  // Wait for any in-progress SourceBuffer operation to complete.
  // Only listens for updateend — the error event delivers a DOM Event object
  // (not an Error), so mixing it here causes type confusion in callers.
  // SourceBuffer errors are caught instead via the ms.readyState guard below.
  function waitForSb() {
    return new Promise(resolve => {
      if (!sb || !sb.updating) return resolve()
      sb.addEventListener('updateend', resolve, { once: true })
    })
  }

  ms.addEventListener('sourceopen', async () => {
    if (durationSeconds) ms.duration = durationSeconds
    sb = ms.addSourceBuffer('audio/mpeg')

    activeController = new AbortController()
    try {
      const resp = await fetch(streamUrl, { signal: activeController.signal })
      if (!resp.ok) throw new Error(`upstream ${resp.status}`)

      const reader = resp.body.getReader()
      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          // The MSE spec truncates ms.duration to the highest buffered timestamp
          // when endOfStream() is called.  Only call it if the transcode delivered
          // the full expected content; otherwise leave the source open so the
          // progress bar retains the correct total duration even if Jellyfin's
          // FFmpeg exited early (corrupt frame, resource limit, etc.).
          const bufferedEnd = sb.buffered.length > 0
            ? sb.buffered.end(sb.buffered.length - 1)
            : 0
          if (!durationSeconds || bufferedEnd >= durationSeconds - 5) {
            ms.endOfStream()
          }
          break
        }

        await waitForSb()

        // A SourceBuffer error causes the MSE spec to call endOfStream("decode"),
        // transitioning readyState from "open" to "ended".  Attempting appendBuffer
        // on a non-open MediaSource throws InvalidStateError, so bail out here.
        if (activeController.signal.aborted || ms.readyState !== 'open') break

        let appended = false
        try {
          sb.appendBuffer(value)
          appended = true
        } catch (e) {
          if (e.name === 'QuotaExceededError') {
            // Evict already-played data and retry once
            const evictTo = audio.currentTime - 30
            if (evictTo > 0) {
              sb.remove(0, evictTo)
              await waitForSb()
              if (activeController.signal.aborted || ms.readyState !== 'open') break
              try { sb.appendBuffer(value); appended = true } catch { /* fall through */ }
            }
          }
          // Any unrecoverable error — stop buffering cleanly
          if (!appended) break
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') console.error('Transcode stream error:', e)
    }
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
