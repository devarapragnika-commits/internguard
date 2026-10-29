import { useEffect, useState } from 'react'

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [message, setMessage] = useState('')
  const [apiState, setApiState] = useState('checking')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    let cancelled = false

    fetch(`${API_BASE}/health`)
      .then((response) => {
        if (!response.ok) {
          throw new Error('Health check failed')
        }
        return response.json()
      })
      .then((data) => {
        if (!cancelled) {
          setApiState(data.status === 'ok' ? 'connected' : 'unavailable')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setApiState('unavailable')
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  function onAnalyze(event) {
    event.preventDefault()
    setNotice('Scoring is not connected yet. This page only confirms the app is running.')
  }

  const apiLabel =
    apiState === 'checking'
      ? 'Checking API…'
      : apiState === 'connected'
        ? 'API connected'
        : 'API unavailable'

  return (
    <main className="mx-auto flex min-h-svh max-w-2xl flex-col px-4 py-10">
      <header className="mb-8">
        <p className="text-sm font-medium tracking-wide text-slate-500">InternGuard</p>
        <h1 className="mt-1 text-3xl font-semibold text-slate-900">Analyze a message</h1>
        <p className="mt-2 text-slate-600">
          Paste a job or internship message. Risk scoring is not connected yet.
        </p>
      </header>

      <form onSubmit={onAnalyze} className="flex flex-1 flex-col gap-4">
        <label className="flex flex-col gap-2 text-sm font-medium text-slate-800">
          Message
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            rows={10}
            placeholder="Paste a WhatsApp, Telegram, LinkedIn, or email message"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-base font-normal text-slate-900 outline-none focus:border-slate-500"
          />
        </label>

        <div className="flex items-center justify-between gap-3">
          <p
            className={
              apiState === 'connected' ? 'text-sm text-emerald-700' : 'text-sm text-slate-500'
            }
          >
            {apiLabel}
          </p>
          <button
            type="submit"
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Analyze
          </button>
        </div>

        {notice ? (
          <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {notice}
          </p>
        ) : null}
      </form>
    </main>
  )
}

export default App
