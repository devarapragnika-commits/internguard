import { useEffect, useState } from 'react'

import HistoryView from './components/HistoryView.jsx'
import ResultView from './components/ResultView.jsx'
import { addEntry, clearHistory, createEntry, isHistoryKey, loadHistory } from './history.js'

const API_BASE = 'http://127.0.0.1:8000'
const TABS = ['analyze', 'history']

function tabFromHash() {
  const tab = window.location.hash.replace('#', '')
  return TABS.includes(tab) ? tab : 'analyze'
}

function App() {
  const [tab, setTab] = useState(tabFromHash)
  const [message, setMessage] = useState('')
  const [apiState, setApiState] = useState('checking')
  const [notice, setNotice] = useState('')
  const [result, setResult] = useState(null)
  const [pending, setPending] = useState(false)
  const [history, setHistory] = useState(loadHistory)

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

  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash())
    const onStorage = (event) => {
      if (isHistoryKey(event.key)) {
        setHistory(loadHistory())
      }
    }
    window.addEventListener('hashchange', onHashChange)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener('hashchange', onHashChange)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  function goTo(next) {
    window.location.hash = next
    setTab(next)
  }

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
      const entry = createEntry(data, 'text', text)
      setResult(entry)
      setHistory(addEntry(entry))
    } catch {
      setNotice('Could not reach the API. Start it on port 8000 and try again.')
    } finally {
      setPending(false)
    }
  }

  function onClearHistory() {
    setHistory(clearHistory())
  }

  const apiLabel =
    apiState === 'checking'
      ? 'Checking API…'
      : apiState === 'connected'
        ? 'API connected'
        : 'API unavailable'

  const tabClass = (name) =>
    `rounded-md px-3 py-1.5 text-sm font-medium ${
      tab === name ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-200'
    }`

  return (
    <main className="mx-auto flex min-h-svh max-w-4xl flex-col px-4 py-8 sm:py-10">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium tracking-wide text-slate-500">InternGuard</p>
          <h1 className="mt-1 text-3xl font-semibold text-slate-900">
            {tab === 'history' ? 'Past checks' : 'Analyze a message'}
          </h1>
        </div>
        <nav className="flex gap-2" aria-label="Pages">
          <a
            href="#analyze"
            onClick={(event) => {
              event.preventDefault()
              goTo('analyze')
            }}
            aria-current={tab === 'analyze' ? 'page' : undefined}
            className={tabClass('analyze')}
          >
            Analyze
          </a>
          <a
            href="#history"
            onClick={(event) => {
              event.preventDefault()
              goTo('history')
            }}
            aria-current={tab === 'history' ? 'page' : undefined}
            className={tabClass('history')}
          >
            History ({history.length})
          </a>
        </nav>
      </header>

      {tab === 'history' ? (
        <HistoryView
          history={history}
          onStart={() => goTo('analyze')}
          onClear={onClearHistory}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-slate-600">
            Paste a job or internship message. Analyze returns one risk score for the wording and
            any links.
          </p>

          <form onSubmit={onAnalyze} className="flex flex-col gap-4">
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-800">
              Message
              <textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                rows={8}
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
          </form>

          {notice ? (
            <p
              role="alert"
              className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"
            >
              {notice}
            </p>
          ) : null}

          {result ? <ResultView result={result} /> : null}
        </div>
      )}
    </main>
  )
}

export default App
