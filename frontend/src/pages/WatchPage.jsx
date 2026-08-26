import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import VideoPlayer   from '../components/VideoPlayer'
import Background    from '../components/Background'
import TitleBanner   from '../components/TitleBanner'
import FlavorText    from '../components/FlavorText'
import LogoFlash     from '../components/LogoFlash'
import useConfig     from '../hooks/useConfig'

const STATUS_MESSAGES = {
  not_found:    'This link does not exist.',
  deactivated:  'This link has been deactivated.',
  expired:      'This link has expired.',
  exhausted:    'This link has reached its maximum number of views.',
  client_limit: 'This link is no longer accepting new viewers.',
  error:        'Something went wrong. Please try again later.',
}

function getOrCreateClientId() {
  let id = localStorage.getItem('share_client_id')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('share_client_id', id)
  }
  return id
}

function formatExpiry(expiresAt) {
  if (!expiresAt) return null
  return new Date(expiresAt + 'Z').toLocaleString()
}

function pickBackground(mediaBackground, availableBackgrounds) {
  if (mediaBackground) return mediaBackground
  if (!availableBackgrounds || availableBackgrounds.length === 0) return null
  return availableBackgrounds[Math.floor(Math.random() * availableBackgrounds.length)]
}

export default function WatchPage() {
  const { uuid }              = useParams()
  const [phase, setPhase]     = useState('loading')
  const [media, setMedia]     = useState(null)
  const [clientId]            = useState(getOrCreateClientId)
  const [bgFile, setBgFile]   = useState(null)
  const { config }            = useConfig()

  useEffect(() => {
    fetch(`/api/links/${uuid}/register`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ client_id: clientId }),
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'ok') {
          setMedia(data)
          setPhase('ok')
        } else {
          setPhase(data.status ?? 'error')
        }
      })
      .catch(() => setPhase('error'))
  }, [uuid, clientId])

  // Pick background once we have both media info and the available list
  useEffect(() => {
    if (media && config) {
      setBgFile(pickBackground(media.background, config.available_backgrounds))
    }
  }, [media, config])

  // Flavor text: link-level override wraps in array, else use global pool
  const flavorTexts    = media?.flavor_text ? [media.flavor_text] : config.flavor_texts
  // The deployment-wide switch is a hard override — per-link flavor_enabled
  // only has effect when the deployment has the flavor system on at all.
  const flavorEnabled  = config.animations_enabled && (media?.flavor_enabled ?? false)

  // ── Loading ────────────────────────────────────────────────────────────────
  if (phase === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400 animate-pulse">Loading…</p>
      </div>
    )
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (phase !== 'ok') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <p className="text-xl text-red-400 font-semibold text-center">
          {STATUS_MESSAGES[phase] ?? STATUS_MESSAGES.error}
        </p>
      </div>
    )
  }

  // ── Player ─────────────────────────────────────────────────────────────────
  const isVideo        = media.item_type !== 'Audio'
  const needsTranscode = !isVideo && (media.needs_transcode ?? false)

  // Transcoded audio uses the HLS playlist endpoint; everything else uses the
  // direct stream proxy which forwards Range headers for native seeking.
  const streamUrl = needsTranscode
    ? `/api/hls/${uuid}/playlist.m3u8?client_id=${encodeURIComponent(clientId)}`
    : `/api/stream/${uuid}?client_id=${encodeURIComponent(clientId)}`
  const expiry    = formatExpiry(media.expires_at)

  return (
    <div className="min-h-screen relative">

      {/* z-0 — fullscreen background */}
      {flavorEnabled && <Background filename={bgFile} />}

      {/* z-10 — content card */}
      <div className="relative z-10 flex flex-col items-center justify-start px-4 py-8 min-h-screen">
        <div
          className="w-full max-w-4xl space-y-4 rounded-xl p-4"
          style={{
            backgroundColor: 'rgba(5, 2, 18, 0.75)',
            backdropFilter:  'blur(6px)',
            border:          '1px solid rgba(80, 40, 120, 0.35)',
          }}
        >
          {/* Title banner with glitch + color cycle */}
          <TitleBanner
            siteTitle={config.site_title}
            timing={config.timing}
            fonts={config.fonts}
            animationsEnabled={config.animations_enabled}
          />

          {/* Media title */}
          <div className="space-y-0.5">
            <h1 className="text-2xl font-bold text-white truncate">{media.item_title}</h1>
            {media.item_artist && (
              <p className="text-sm text-gray-400 truncate">{media.item_artist}</p>
            )}
          </div>

          {/* Album art — audio only */}
          {!isVideo && (
            <div className="flex justify-center">
              <img
                src={`/api/image/${uuid}`}
                alt="Cover art"
                className="w-64 h-64 object-cover rounded-lg shadow-xl"
                onError={e => { e.target.style.display = 'none' }}
              />
            </div>
          )}

          {/* Player */}
          <VideoPlayer
            streamUrl={streamUrl}
            isVideo={isVideo}
            needsTranscode={needsTranscode}
          />

          {/* Expiry notice */}
          {expiry && (
            <p className="text-sm text-gray-500 text-center">
              This link expires on {expiry}.
            </p>
          )}
        </div>
      </div>

      {/* z-20 — floating flavor overlays (flavor_enabled only) */}
      {flavorEnabled && (
        <>
          <FlavorText texts={flavorTexts}     timing={config.timing} fonts={config.fonts} />
          <LogoFlash  hasLogo={config.has_logo} timing={config.timing} />
        </>
      )}
    </div>
  )
}
