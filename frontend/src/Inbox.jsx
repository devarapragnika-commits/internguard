import { useEffect, useState } from 'react'
import { ResultCard } from './ResultCard'

function badgeClass(band) {
  if (band === 'high') {
    return 'bg-red-100 text-red-800'
  }
  if (band === 'medium') {
    return 'bg-amber-100 text-amber-900'
  }
  return 'bg-emerald-100 text-emerald-800'
}

function Inbox({ apiBase, apiState }) {
  const [notice, setNotice] = useState('')
  const [messages, setMessages] = useState([])
  const [pending, setPending] = useState(true)
  const [selectedId, setSelectedId] = useState('')

  useEffect(() => {
    let cancelled = false

    setPending(true)
    setNotice('')
    fetch(`${apiBase}/inbox`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Inbox request failed')
        }
        return response.json()
      })
      .then((data) => {
        if (cancelled) {
          return
        }
        setMessages(data.messages || [])
        setPending(false)
      })
      .catch(() => {
        if (cancelled) {
          return
        }
        setPending(false)
        setNotice('Could not reach the API. Start it on port 8000 and try again.')
      })

    return () => {
      cancelled = true
    }
  }, [apiBase])

  const apiLabel =
    apiState === 'checking'
      ? 'Checking API…'
      : apiState === 'connected'
        ? 'API connected'
        : 'API unavailable'

  return (
    <>
      <p
        className={
          apiState === 'connected' ? 'mb-4 text-sm text-emerald-700' : 'mb-4 text-sm text-slate-500'
        }
      >
        {apiLabel}
      </p>

      {pending ? <p className="text-sm text-slate-600">Loading sandbox inbox…</p> : null}

      {notice ? (
        <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {notice}
        </p>
      ) : null}

      {!pending && !notice ? (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-md border border-slate-200 bg-white">
          {messages.map((row) => (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => setSelectedId(row.id === selectedId ? '' : row.id)}
                className={
                  row.id === selectedId
                    ? 'flex w-full items-start gap-3 bg-slate-50 px-4 py-3 text-left'
                    : 'flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-slate-50'
                }
              >
                <span
                  className={`mt-0.5 shrink-0 rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${badgeClass(row.band)}`}
                >
                  {row.band}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-slate-900">{row.subject}</span>
                  <span className="mt-0.5 block truncate text-sm text-slate-600">
                    {row.from_name ? `${row.from_name} <${row.from_address}>` : row.from_address}
                  </span>
                  {row.attachments.length > 0 ? (
                    <span className="mt-0.5 block truncate text-xs text-slate-500">
                      {row.attachments.join(', ')}
                    </span>
                  ) : null}
                </span>
              </button>
              {row.id === selectedId ? (
                <ResultCard
                  nested
                  result={row}
                  extra={
                    row.snippet ? (
                      <p className="mt-3 text-slate-600">Preview: {row.snippet}</p>
                    ) : null
                  }
                />
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {!pending && !notice && !selectedId ? (
        <p className="mt-6 text-sm text-slate-600">Choose a row to see why it was flagged.</p>
      ) : null}
    </>
  )
}

export default Inbox
