import { useEffect, useState } from 'react'

const API_BASE = 'http://127.0.0.1:8000'

function App() {
  const [message, setMessage] = useState('')
  const [apiState, setApiState] = useState('checking')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

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
    setError('')
    setResult(null)
    if (!message.trim()) {
      setError('Paste a message before analyzing.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/analyze/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: message }),
      })
      if (!response.ok) {
        throw new Error('Analysis failed')
      }
      setResult(await response.json())
    } catch {
      setError('The analysis request failed. Check that the API is running.')
    } finally {
      setLoading(false)
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
          Paste a job or internship message to see the risk score and why it was flagged.
        </p>
      </header>

      <form onSubmit={onAnalyze} className="flex flex-col gap-4">
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
            disabled={loading}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
          >
            {loading ? 'Analyzing…' : 'Analyze'}
          </button>
        </div>

        {error ? (
          <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {error}
          </p>
        ) : null}

        {result ? (
          <section className="rounded-md border border-slate-200 bg-white px-4 py-4">
            <p className="text-sm font-medium tracking-wide text-slate-500">Risk score</p>
            <p className="mt-1 text-3xl font-semibold text-slate-900">
              {result.score}/100
              <span className="ml-2 text-base font-medium uppercase text-slate-600">{result.band}</span>
            </p>
            <h2 className="mt-4 text-sm font-medium text-slate-800">Why it was flagged</h2>
            {result.reasons.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                {result.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm text-slate-700">No scam signals were flagged.</p>
            )}
            <h2 className="mt-4 text-sm font-medium text-slate-800">Recommendation</h2>
            <p className="mt-2 text-sm text-slate-700">{result.recommendation}</p>
          </section>
        ) : null}
      </form>
    </main>
  )
}

export default App
