import { useState, useEffect, useRef } from 'react'

// ── helpers ───────────────────────────────────────────────────────────────────

function authHeaders(token) {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }
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

// ── sub-components ────────────────────────────────────────────────────────────

function LoginForm({ onLogin }) {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    const r = await fetch('/api/admin/links', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (r.ok) {
      sessionStorage.setItem('admin_token', token)
      onLogin(token)
    } else {
      setError('Invalid token.')
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

function CreateLinkModal({ item, token, onCreated, onClose }) {
  const [expiresAt, setExpiresAt] = useState('')
  const [maxUses, setMaxUses]     = useState('')
  const [maxClients, setMaxClients] = useState('')
  const [notes, setNotes]         = useState('')
  const [result, setResult]       = useState(null)
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const body = {
      item_id:     item.id,
      expires_at:  expiresAt || null,
      max_uses:    maxUses    ? parseInt(maxUses)    : null,
      max_clients: maxClients ? parseInt(maxClients) : null,
      notes:       notes || null,
    }
    const r = await fetch('/api/admin/links', {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify(body),
    })
    setLoading(false)
    if (r.ok) {
      const data = await r.json()
      setResult(data)
      onCreated()
    } else {
      const err = await r.json().catch(() => ({}))
      setError(err.detail ?? 'Failed to create link.')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4" onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md space-y-4" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-bold text-white">Create Share Link</h2>
        <p className="text-gray-300 text-sm">{item.title} <span className="text-gray-500">({item.type}{item.year ? `, ${item.year}` : ''})</span></p>

        {!result ? (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Expires at (leave blank for no expiry)</label>
              <input type="datetime-local" value={expiresAt} onChange={e => setExpiresAt(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Max total views (leave blank for unlimited)</label>
              <input type="number" min="1" value={maxUses} onChange={e => setMaxUses(e.target.value)} placeholder="e.g. 10"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Max unique viewers (leave blank for unlimited)</label>
              <input type="number" min="1" value={maxClients} onChange={e => setMaxClients(e.target.value)} placeholder="e.g. 3"
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Notes (optional)</label>
              <input type="text" value={notes} onChange={e => setNotes(e.target.value)}
                className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
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
  const [token, setToken]       = useState(() => sessionStorage.getItem('admin_token') ?? '')
  const [links, setLinks]       = useState([])
  const [searchQuery, setQuery] = useState('')
  const [results, setResults]   = useState([])
  const [searching, setSearching] = useState(false)
  const [selectedItem, setSelected] = useState(null)
  const searchTimer = useRef(null)

  const isLoggedIn = !!token

  async function loadLinks(t = token) {
    const r = await fetch('/api/admin/links', { headers: authHeaders(t) })
    if (r.ok) setLinks(await r.json())
  }

  useEffect(() => { if (isLoggedIn) loadLinks() }, [isLoggedIn])

  // Debounced Jellyfin search
  useEffect(() => {
    if (!searchQuery.trim()) { setResults([]); return }
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      const r = await fetch(`/api/admin/search?q=${encodeURIComponent(searchQuery)}`,
        { headers: authHeaders(token) })
      setSearching(false)
      if (r.ok) setResults(await r.json())
    }, 350)
    return () => clearTimeout(searchTimer.current)
  }, [searchQuery, token])

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
        {searching && <p className="text-gray-500 text-sm">Searching…</p>}
        {results.length > 0 && (
          <ul className="divide-y divide-gray-800 rounded-lg overflow-hidden border border-gray-700">
            {results.map(item => (
              <li key={item.id} className="flex items-center justify-between px-4 py-3 bg-gray-800 hover:bg-gray-750">
                <div>
                  <span className="text-white text-sm font-medium">{item.title}</span>
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
                        <div className="text-xs text-gray-500">{link.item_type}</div>
                        {link.notes && <div className="text-xs text-gray-600 italic">{link.notes}</div>}
                      </td>
                      <td className={`py-3 pr-4 font-medium ${color}`}>{label}</td>
                      <td className="py-3 pr-4 text-gray-400">{formatDate(link.expires_at)}</td>
                      <td className="py-3 pr-4 text-gray-300">{usageLabel(link.use_count, link.max_uses)}</td>
                      <td className="py-3 pr-4 text-gray-300">{usageLabel(link.client_count, link.max_clients)}</td>
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
          onCreated={() => { loadLinks(); setQuery(''); setResults([]) }}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}
