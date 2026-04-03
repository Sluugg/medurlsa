import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import VideoPlayer from '../components/VideoPlayer'

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
  const d = new Date(expiresAt + 'Z') // treat stored value as UTC
  return d.toLocaleString()
}

export default function WatchPage() {
  const { uuid } = useParams()
  const [phase, setPhase] = useState('loading') // loading | ok | <error-status>
  const [media, setMedia] = useState(null)
  const [clientId] = useState(getOrCreateClientId)

  useEffect(() => {
    fetch(`/api/watch/${uuid}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId }),
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

  if (phase === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-400 animate-pulse">Loading…</p>
      </div>
    )
  }

  if (phase !== 'ok') {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center space-y-2">
          <p className="text-2xl text-red-400 font-semibold">
            {STATUS_MESSAGES[phase] ?? STATUS_MESSAGES.error}
          </p>
        </div>
      </div>
    )
  }

  const streamUrl = `/api/stream/${uuid}?client_id=${encodeURIComponent(clientId)}`
  const isVideo = media.item_type !== 'Audio'
  const expiry = formatExpiry(media.expires_at)

  return (
    <div className="min-h-screen flex flex-col items-center justify-start px-4 py-8 max-w-4xl mx-auto w-full">
      <div className="w-full space-y-4">
        {/* Title */}
        <h1 className="text-2xl font-bold text-white truncate">{media.item_title}</h1>

        {/* Player */}
        <VideoPlayer streamUrl={streamUrl} isVideo={isVideo} />

        {/* Expiry notice */}
        {expiry && (
          <p className="text-sm text-gray-500 text-center">
            This link expires on {expiry}.
          </p>
        )}
      </div>
    </div>
  )
}
