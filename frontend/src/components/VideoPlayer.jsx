/**
 * VideoPlayer — native HTML5 player adapted from the sigillist project.
 *
 * Uses a plain <video> or <audio> element with direct src pointing at our
 * /api/stream/{uuid} proxy endpoint.  The browser handles seeking natively
 * via Range requests; the backend forwards those to Jellyfin unchanged.
 */
import { useEffect, useRef } from 'react'

export default function VideoPlayer({ streamUrl, isVideo }) {
  const containerRef = useRef(null)
  const elementRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    // Create the media element once
    if (!elementRef.current) {
      const el = document.createElement(isVideo ? 'video' : 'audio')
      el.controls = true
      el.autoplay = true
      el.style.width = '100%'
      if (isVideo) {
        el.style.maxHeight = '75vh'
        el.style.background = '#000'
        el.className = 'rounded-lg shadow-xl'
      } else {
        el.className = 'w-full rounded'
      }

      const saved = localStorage.getItem('player_volume')
      if (saved !== null) el.volume = parseFloat(saved)
      el.addEventListener('volumechange', () =>
        localStorage.setItem('player_volume', String(el.volume))
      )

      el.src = streamUrl
      elementRef.current = el
      containerRef.current.appendChild(el)
      el.play().catch(() => {/* autoplay may be blocked — controls still work */})
    } else if (elementRef.current.src !== streamUrl) {
      elementRef.current.src = streamUrl
      elementRef.current.play().catch(() => {})
    }
  }, [streamUrl, isVideo])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (elementRef.current) {
        elementRef.current.pause()
        elementRef.current.src = ''
        elementRef.current = null
      }
    }
  }, [])

  return <div ref={containerRef} className="w-full" />
}
