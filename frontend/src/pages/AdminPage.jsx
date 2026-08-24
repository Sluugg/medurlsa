import { useState, useEffect, useRef } from 'react'
import useConfig from '../hooks/useConfig'

// ── helpers ───────────────────────────────────────────────────────────────────

function authHeaders(token) {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
}

const UNREACHABLE_MSG = 'Could not reach the server — is the backend running?'

// Extracts a displayable message from a failed fetch response. FastAPI error
// responses are JSON with a `detail` string; a response that isn't valid JSON
// (e.g. the dev proxy's own error page when the backend is down) means we
// aren't actually talking to the API, so treat it the same as unreachable.
async function apiErrorMessage(r) {
  let body
  try {
    body = await r.json()
  } catch {
    return UNREACHABLE_MSG
  }
  return (body && typeof body.detail === 'string') ? body.detail : `Server error (${r.status}).`
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso + 'Z').toLocaleString()
}

function usageLabel(used, max) {
  return max == null ? `${used} / ∞` : `${used} / ${max}`
}

function linkStatus(link) {
  if (!link.is_active) return { label: 'Deactivated', color: 'text-gray-400' }
  if (link.expires_at && new Date(link.expires_at + 'Z') < new Date())
    return { label: 'Expired', color: 'text-red-400' }
  if (link.max_uses != null && link.use_count >= link.max_uses)
    return { label: 'Exhausted', color: 'text-yellow-400' }
  return { label: 'Active', color: 'text-green-400' }
}

const VIDEO_EXTS = new Set(['.webm', '.mp4', '.mov', '.avi'])
function fileExt(name) {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

const MEDIA_TYPES = [
  { value: 'Movie',      label: 'Movies' },
  { value: 'Episode',    label: 'Episodes' },
  { value: 'Audio',      label: 'Music' },
  { value: 'MusicVideo', label: 'Music Videos' },
]

// ── LibraryFilter ─────────────────────────────────────────────────────────────
// Collapsed multi-select: libraries vary in number/name per server, so they're
// tucked behind a dropdown instead of always-visible chips like media type.

function LibraryFilter({ libraries, selected, onToggle }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const label =
    selected.size === 0 ? 'All libraries'
    : selected.size === 1 ? (libraries.find(l => l.id === [...selected][0])?.name ?? '1 library')
    : `${selected.size} libraries`

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 bg-gray-800 border border-gray-600 rounded-full px-3 py-1 text-xs text-gray-300 hover:border-gray-400"
      >
        {label}
        <span className="text-gray-500">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-56 max-h-60 overflow-y-auto bg-gray-800 border border-gray-600 rounded shadow-lg p-1">
          {libraries.length === 0 && (
            <p className="text-xs text-gray-500 px-2 py-1.5">No libraries found.</p>
          )}
          {libraries.map(lib => (
            <label
              key={lib.id}
              className="flex items-center gap-2 px-2 py-1.5 text-sm text-gray-300 hover:bg-gray-700 rounded cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selected.has(lib.id)}
                onChange={() => onToggle(lib.id)}
                className="rounded accent-purple-500"
              />
              {lib.name}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

// ── BackgroundThumb ───────────────────────────────────────────────────────────

function BackgroundThumb({ filename, selected, onSelect }) {
  const src     = `/api/backgrounds/${encodeURIComponent(filename)}`
  const isVideo = VIDEO_EXTS.has(fileExt(filename))
  const vidRef  = useRef(null)

  return (
    <button
      type="button"
      onClick={onSelect}
      onMouseEnter={() => isVideo && vidRef.current?.play().catch(() => {})}
      onMouseLeave={() => {
        if (isVideo && vidRef.current) {
          vidRef.current.pause()
          vidRef.current.currentTime = 0
        }
      }}
      className={`aspect-video rounded border-2 overflow-hidden relative
        ${selected ? 'border-blue-500' : 'border-gray-600 hover:border-gray-400'}`}
      title={filename}
    >
      {isVideo ? (
        <video
          ref={vidRef}
          src={src}
          muted
          loop
          playsInline
          preload="metadata"
          className="w-full h-full object-cover"
        />
      ) : (
        <img src={src} alt={filename} className="w-full h-full object-cover" />
      )}
      <span className="absolute bottom-0 left-0 right-0 text-[9px] text-white bg-black/60 px-1 truncate leading-4">
        {filename}
      </span>
    </button>
  )
}

// ── LoginForm ─────────────────────────────────────────────────────────────────

function LoginForm({ onLogin }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    let r
    try {
      r = await fetch('/api/admin/links', {
        headers: { Authorization: `Bearer ${token}` },
      })
    } catch {
      setError(UNREACHABLE_MSG)
      return
    }
    if (r.ok) {
      sessionStorage.setItem('admin_token', token)
      onLogin(token)
    } else {
      setError(await apiErrorMessage(r))
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-700 rounded-xl p-8 w-full max-w-sm space-y-4">
        <h1 className="text-xl font-bold text-white">Admin Login</h1>
        <input
          type="password"
          value={token}
          onChange={e => setToken(e.target.value)}
          placeholder="Admin token"
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button type="submit" className="w-full bg-blue-600 hover:bg-blue-700 rounded py-2 text-white font-medium">
          Sign in
        </button>
      </form>
    </div>
  )
}

// ── CreateLinkModal ───────────────────────────────────────────────────────────

// Formats a Date as the local value a <input type="datetime-local"> expects (YYYY-MM-DDTHH:mm).
function toDatetimeLocal(date) {
  const pad = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const DEFAULT_EXPIRES_AT  = toDatetimeLocal(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000))
const DEFAULT_MAX_USES    = '15'
const DEFAULT_MAX_CLIENTS = '5'

function CreateLinkModal({ item, token, availableBackgrounds, onCreated, onClose }) {
  const [expiresAt, setExpiresAt]           = useState(DEFAULT_EXPIRES_AT)
  const [neverExpires, setNeverExpires]     = useState(false)
  const [maxUses, setMaxUses]               = useState(DEFAULT_MAX_USES)
  const [unlimitedUses, setUnlimitedUses]   = useState(false)
  const [maxClients, setMaxClients]         = useState(DEFAULT_MAX_CLIENTS)
  const [unlimitedClients, setUnlimitedClients] = useState(false)
  const [notes, setNotes]                   = useState('')
  const [flavorEnabled, setFlavorEnabled]   = useState(true)
  const [background, setBackground]         = useState('')     // '' = random
  const [customFlavorText, setCustomFlavor] = useState('')     // '' = pool
  const [result, setResult]                 = useState(null)
  const [error, setError]                   = useState('')
  const [loading, setLoading]               = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const body = {
      item_id:        item.id,
      expires_at:     (!neverExpires && expiresAt) ? expiresAt : null,
      max_uses:       (!unlimitedUses && maxUses)     ? parseInt(maxUses)    : null,
      max_clients:    (!unlimitedClients && maxClients) ? parseInt(maxClients) : null,
      notes:          notes || null,
      flavor_enabled: flavorEnabled,
      background:     background || null,
      flavor_text:    customFlavorText || null,
    }
    let r
    try {
      r = await fetch('/api/admin/links', {
        method:  'POST',
        headers: authHeaders(token),
        body:    JSON.stringify(body),
      })
    } catch {
      setLoading(false)
      setError(UNREACHABLE_MSG)
      return
    }
    setLoading(false)
    if (r.ok) {
      setResult(await r.json())
      onCreated()
    } else {
      setError(await apiErrorMessage(r))
    }
  }

  const inputCls = 'w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500'
  const labelCls = 'block text-xs text-gray-400 mb-1'

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4 overflow-y-auto py-4" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg space-y-4 my-auto" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-white">Create Share Link</h2>
        <p className="text-gray-300 text-sm">
          {item.title}
          <span className="text-gray-500"> ({item.type}{item.year ? `, ${item.year}` : ''})</span>
        </p>

        {!result ? (
          <form onSubmit={handleSubmit} className="space-y-3">

            {/* Standard fields */}
            <div>
              <label className={labelCls}>Expires at</label>
              <input
                type="datetime-local"
                value={expiresAt}
                onChange={e => setExpiresAt(e.target.value)}
                disabled={neverExpires}
                className={`${inputCls} disabled:opacity-50`}
              />
              <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mt-2">
                <input
                  type="checkbox"
                  checked={neverExpires}
                  onChange={e => setNeverExpires(e.target.checked)}
                  className="rounded accent-purple-500"
                />
                No expiration
              </label>
            </div>
            <div>
              <label className={labelCls}>Max total views</label>
              <input
                type="number"
                min="1"
                value={maxUses}
                onChange={e => setMaxUses(e.target.value)}
                placeholder="e.g. 10"
                disabled={unlimitedUses}
                className={`${inputCls} disabled:opacity-50`}
              />
              <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mt-2">
                <input
                  type="checkbox"
                  checked={unlimitedUses}
                  onChange={e => setUnlimitedUses(e.target.checked)}
                  className="rounded accent-purple-500"
                />
                Unlimited
              </label>
            </div>
            <div>
              <label className={labelCls}>Max unique viewers</label>
              <input
                type="number"
                min="1"
                value={maxClients}
                onChange={e => setMaxClients(e.target.value)}
                placeholder="e.g. 3"
                disabled={unlimitedClients}
                className={`${inputCls} disabled:opacity-50`}
              />
              <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mt-2">
                <input
                  type="checkbox"
                  checked={unlimitedClients}
                  onChange={e => setUnlimitedClients(e.target.checked)}
                  className="rounded accent-purple-500"
                />
                Unlimited
              </label>
            </div>
            <div>
              <label className={labelCls}>Notes (optional)</label>
              <input type="text" value={notes} onChange={e => setNotes(e.target.value)} className={inputCls} />
            </div>

            {/* Divider */}
            <div className="border-t border-gray-700 pt-2">
              <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">Visual flavor</p>

              {/* Flavor enabled toggle */}
              <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mb-3">
                <input
                  type="checkbox"
                  checked={flavorEnabled}
                  onChange={e => setFlavorEnabled(e.target.checked)}
                  className="rounded accent-purple-500"
                />
                Enable background, flavor text &amp; logo effects
              </label>

              {/* Background selector */}
              {flavorEnabled && availableBackgrounds.length > 0 && (
                <div className="mb-3">
                  <label className={labelCls}>Background (leave unselected for random)</label>
                  <div className="grid grid-cols-3 gap-2 max-h-44 overflow-y-auto rounded border border-gray-700 p-2 bg-gray-800">
                    {/* "Random" tile */}
                    <button
                      type="button"
                      onClick={() => setBackground('')}
                      className={`aspect-video rounded border-2 flex items-center justify-center text-xs text-gray-400
                        ${background === '' ? 'border-blue-500 bg-gray-700' : 'border-gray-600 hover:border-gray-400'}`}
                    >
                      Random
                    </button>
                    {availableBackgrounds.map(fname => (
                      <BackgroundThumb
                        key={fname}
                        filename={fname}
                        selected={background === fname}
                        onSelect={() => setBackground(fname)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Custom flavor text */}
              {flavorEnabled && (
                <div>
                  <label className={labelCls}>Custom flavor text (leave blank to use global pool)</label>
                  <input
                    type="text"
                    value={customFlavorText}
                    onChange={e => setCustomFlavor(e.target.value)}
                    placeholder="e.g. this one is just for you"
                    className={inputCls}
                  />
                </div>
              )}
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={onClose} className="flex-1 bg-gray-700 hover:bg-gray-600 rounded py-2 text-white text-sm">Cancel</button>
              <button type="submit" disabled={loading} className="flex-1 bg-blue-600 hover:bg-blue-700 rounded py-2 text-white text-sm font-medium disabled:opacity-50">
                {loading ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-3">
            <p className="text-green-400 text-sm font-medium">Link created!</p>
            <div className="flex items-center gap-2 bg-gray-800 rounded px-3 py-2">
              <span className="flex-1 text-xs text-gray-300 truncate">{result.url}</span>
              <button onClick={() => navigator.clipboard.writeText(result.url)}
                className="text-xs text-blue-400 hover:text-blue-300 whitespace-nowrap">Copy</button>
            </div>
            <button onClick={onClose} className="w-full bg-gray-700 hover:bg-gray-600 rounded py-2 text-white text-sm">Done</button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── main admin page ───────────────────────────────────────────────────────────

export default function AdminPage() {
  const [token, setToken]           = useState(() => sessionStorage.getItem('admin_token') ?? '')
  const [links, setLinks]           = useState([])
  const [searchQuery, setQuery]     = useState('')
  const [results, setResults]       = useState([])
  const [searching, setSearching]   = useState(false)
  const [selectedItem, setSelected] = useState(null)
  const [libraries, setLibraries]   = useState([])
  const [selectedTypes, setSelectedTypes]         = useState(() => new Set(MEDIA_TYPES.map(t => t.value)))
  const [selectedLibraries, setSelectedLibraries] = useState(() => new Set())
  const searchTimer                 = useRef(null)
  const { config }                  = useConfig()

  const isLoggedIn = !!token

  async function loadLinks(t = token) {
    const r = await fetch('/api/admin/links', { headers: authHeaders(t) })
    if (r.ok) setLinks(await r.json())
  }

  useEffect(() => { if (isLoggedIn) loadLinks() }, [isLoggedIn])

  useEffect(() => {
    if (!isLoggedIn) return
    fetch('/api/admin/libraries', { headers: authHeaders(token) })
      .then(r => r.ok ? r.json() : [])
      .then(setLibraries)
      .catch(() => {})
  }, [isLoggedIn])

  function toggleType(value) {
    setSelectedTypes(prev => {
      const next = new Set(prev)
      next.has(value) ? next.delete(value) : next.add(value)
      return next
    })
  }

  function toggleLibrary(id) {
    setSelectedLibraries(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // Debounced Jellyfin search. Aborts any still-in-flight request whenever the
  // query/filters change again, so a slow, now-stale response can never land
  // after (and overwrite) a faster, more recent one.
  useEffect(() => {
    if (!searchQuery.trim()) { setResults([]); return }
    clearTimeout(searchTimer.current)
    const controller = new AbortController()
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      const params = new URLSearchParams({ q: searchQuery })
      if (selectedTypes.size > 0)     params.set('item_types',  [...selectedTypes].join(','))
      if (selectedLibraries.size > 0) params.set('library_ids', [...selectedLibraries].join(','))
      try {
        const r = await fetch(`/api/admin/search?${params}`, {
          headers: authHeaders(token),
          signal:  controller.signal,
        })
        if (r.ok) setResults(await r.json())
      } catch (err) {
        if (err.name !== 'AbortError') throw err
      } finally {
        if (!controller.signal.aborted) setSearching(false)
      }
    }, 350)
    return () => {
      clearTimeout(searchTimer.current)
      controller.abort()
    }
  }, [searchQuery, token, selectedTypes, selectedLibraries])

  async function handleDelete(uuid) {
    if (!confirm('Delete this link permanently?')) return
    await fetch(`/api/admin/links/${uuid}`, { method: 'DELETE', headers: authHeaders(token) })
    loadLinks()
  }

  async function handleToggle(uuid) {
    await fetch(`/api/admin/links/${uuid}/toggle`, { method: 'PATCH', headers: authHeaders(token) })
    loadLinks()
  }

  function handleLogout() {
    sessionStorage.removeItem('admin_token')
    setToken('')
    setLinks([])
  }

  if (!isLoggedIn) {
    return <LoginForm onLogin={t => { setToken(t); loadLinks(t) }} />
  }

  return (
    <div className="min-h-screen px-4 py-8 max-w-5xl mx-auto space-y-8">

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Share Admin</h1>
        <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-white">Sign out</button>
      </div>

      {/* Search Jellyfin */}
      <section className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
        <h2 className="text-lg font-semibold text-white">Create New Share</h2>
        <input
          type="text"
          value={searchQuery}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search Jellyfin library…"
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />

        {/* Search filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-gray-500 mr-0.5">Type:</span>
            {MEDIA_TYPES.map(t => (
              <button
                key={t.value}
                type="button"
                onClick={() => toggleType(t.value)}
                className={`text-xs rounded-full px-3 py-1 border transition-colors
                  ${selectedTypes.has(t.value)
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-400'}`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-500 mr-0.5">Library:</span>
            <LibraryFilter libraries={libraries} selected={selectedLibraries} onToggle={toggleLibrary} />
          </div>
        </div>

        {searching && <p className="text-gray-500 text-sm">Searching…</p>}
        {results.length > 0 && (
          <ul className="divide-y divide-gray-800 rounded-lg overflow-hidden border border-gray-700">
            {results.map(item => (
              <li key={item.id} className="flex items-center justify-between px-4 py-3 bg-gray-800 hover:bg-gray-750">
                <div>
                  <span className="text-white text-sm font-medium">{item.title}</span>
                  {item.artist && (
                    <span className="ml-2 text-xs text-gray-400">{item.artist}</span>
                  )}
                  <span className="ml-2 text-xs text-gray-500">
                    {item.type}{item.year ? ` · ${item.year}` : ''}
                    {item.duration_seconds ? ` · ${Math.round(item.duration_seconds / 60)} min` : ''}
                  </span>
                </div>
                <button
                  onClick={() => setSelected(item)}
                  className="ml-4 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1 whitespace-nowrap"
                >
                  + Share
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Links table */}
      <section className="bg-gray-900 border border-gray-700 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Active Shares</h2>
          <button onClick={() => loadLinks()} className="text-xs text-gray-400 hover:text-white">Refresh</button>
        </div>

        {links.length === 0 ? (
          <p className="text-gray-500 text-sm">No links yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-700">
                  <th className="pb-2 pr-4">Title</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Expires</th>
                  <th className="pb-2 pr-4">Views</th>
                  <th className="pb-2 pr-4">Viewers</th>
                  <th className="pb-2 pr-2">Flavor</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {links.map(link => {
                  const { label, color } = linkStatus(link)
                  return (
                    <tr key={link.uuid} className="align-middle">
                      <td className="py-3 pr-4">
                        <div className="font-medium text-white">{link.item_title}</div>
                        {link.item_artist && (
                          <div className="text-xs text-gray-400">{link.item_artist}</div>
                        )}
                        <div className="text-xs text-gray-500">{link.item_type}</div>
                        {link.notes && <div className="text-xs text-gray-600 italic">{link.notes}</div>}
                      </td>
                      <td className={`py-3 pr-4 font-medium ${color}`}>{label}</td>
                      <td className="py-3 pr-4 text-gray-400">{formatDate(link.expires_at)}</td>
                      <td className="py-3 pr-4 text-gray-300">{usageLabel(link.use_count, link.max_uses)}</td>
                      <td className="py-3 pr-4 text-gray-300">{usageLabel(link.client_count, link.max_clients)}</td>
                      <td className="py-3 pr-2">
                        <span className={`text-xs ${link.flavor_enabled ? 'text-purple-400' : 'text-gray-600'}`}>
                          {link.flavor_enabled ? 'On' : 'Off'}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex gap-2 flex-wrap">
                          <button
                            onClick={() => navigator.clipboard.writeText(link.url)}
                            className="text-xs bg-gray-700 hover:bg-gray-600 text-white rounded px-2 py-1"
                          >Copy URL</button>
                          <button
                            onClick={() => handleToggle(link.uuid)}
                            className="text-xs bg-gray-700 hover:bg-gray-600 text-white rounded px-2 py-1"
                          >{link.is_active ? 'Deactivate' : 'Reactivate'}</button>
                          <button
                            onClick={() => handleDelete(link.uuid)}
                            className="text-xs bg-red-800 hover:bg-red-700 text-white rounded px-2 py-1"
                          >Delete</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Create link modal */}
      {selectedItem && (
        <CreateLinkModal
          item={selectedItem}
          token={token}
          availableBackgrounds={config.available_backgrounds}
          onCreated={() => { loadLinks(); setQuery(''); setResults([]) }}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
