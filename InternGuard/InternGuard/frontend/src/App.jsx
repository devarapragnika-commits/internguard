import { useEffect, useState } from 'react'

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [message, setMessage] = useState('')
  const [apiState, setApiState] = useState('checking')
  const [notice, setNotice] = useState('')
  const [result, setResult] = useState(null)
  const [pending, setPending] = useState(false)

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

  async function onAnalyze(event) {
    event.preventDefault()
    const text = message.trim()
    setResult(null)
    if (!text) {
      setNotice('Paste a message before analyzing.')
      return
    }

    setPending(true)
    setNotice('')
    try {
      const response = await fetch(`${API_BASE}/analyze/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Analysis failed')
      }
      setResult(data)
    } catch {
      setNotice('Could not reach the API. Start it on port 8000 and try again.')
    } finally {
      setPending(false)
    }
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
          Paste a job or internship message. Analyze checks whether it asks for a fee or deposit.
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
            disabled={pending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
          >
            {pending ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>

        {notice ? (
          <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {notice}
          </p>
        ) : null}

        {result ? (
          <section className="rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800">
            <p className="font-medium text-slate-900">
              Financial request risk: {result.financial_request_risk}/{result.financial_request_cap}
            </p>
            <p className="mt-2">
              {result.flagged ? result.reason : 'No payment request found.'}
            </p>
          </section>
        ) : null}
      </form>
    </main>
  )
}

export default App
