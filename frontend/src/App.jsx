import { useEffect, useState } from 'react'

import HistoryView from './components/HistoryView.jsx'
import ResultView from './components/ResultView.jsx'
import Inbox from './Inbox'
import { addEntry, clearHistory, createEntry, isHistoryKey, loadHistory } from './history.js'

const API_BASE = 'http://127.0.0.1:8000'
const TABS = ['analyze', 'inbox', 'history']

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
  const [imageFile, setImageFile] = useState(null)
  const [imageUrl, setImageUrl] = useState('')
  const [fromImage, setFromImage] = useState(false)
  const [emailSource, setEmailSource] = useState('')

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

  function remember(data, channel, source) {
    const entry = createEntry(data, channel, source)
    setHistory(addEntry(entry))
    setResult(data)
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
    setFromImage(false)
    try {
      const response = await fetch(`${API_BASE}/analyze/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const data = await response.json()
      if (!response.ok) {
        setNotice(typeof data.detail === 'string' ? data.detail : 'Analysis failed')
        return
      }
      remember(data, 'text', text)
    } catch {
      setNotice('Could not reach the API. Start it on port 8000 and try again.')
    } finally {
      setPending(false)
    }
  }

  function onImageChoice(event) {
    const file = event.target.files?.[0] || null
    setImageFile(file)
    setImageUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current)
      }
      return file ? URL.createObjectURL(file) : ''
    })
  }

  async function onAnalyzeImage(event) {
    event.preventDefault()
    setResult(null)
    if (!imageFile) {
      setNotice('Choose an image before analyzing.')
      return
    }

    setPending(true)
    setNotice('')
    setFromImage(true)
    try {
      const body = new FormData()
      body.append('file', imageFile)
      const response = await fetch(`${API_BASE}/analyze/image`, {
        method: 'POST',
        body,
      })
      const data = await response.json()
      if (!response.ok) {
        setNotice(typeof data.detail === 'string' ? data.detail : 'Analysis failed')
        return
      }
      remember(data, 'screenshot', data.text || imageFile.name)
    } catch {
      setNotice('Could not reach the API. Start it on port 8000 and try again.')
    } finally {
      setPending(false)
    }
  }

  async function onAnalyzeEmail(event) {
    event.preventDefault()
    const raw = emailSource.trim()
    setResult(null)
    if (!raw) {
      setNotice('Paste an email before analyzing.')
      return
    }

    setPending(true)
    setNotice('')
    setFromImage(false)
    try {
      const response = await fetch(`${API_BASE}/analyze/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw }),
      })
      const data = await response.json()
      if (!response.ok) {
        setNotice(
          response.status === 404
            ? 'Restart the API so the email route is loaded, then try again.'
            : typeof data.detail === 'string'
              ? data.detail
              : 'Analysis failed',
        )
        return
      }
      remember(data, 'email', raw)
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
            {tab === 'history' ? 'Past checks' : tab === 'inbox' ? 'Demo inbox' : 'Analyze a message'}
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
            href="#inbox"
            onClick={(event) => {
              event.preventDefault()
              goTo('inbox')
            }}
            aria-current={tab === 'inbox' ? 'page' : undefined}
            className={tabClass('inbox')}
          >
            Demo inbox
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
      ) : tab === 'inbox' ? (
        <div className="flex max-w-2xl flex-col gap-4">
          <p className="text-slate-600">
            Sandbox fixtures, not a personal account. Each unopened row shows a low, medium, or
            high badge from the sender and attachment scorer. Choose a row to see why.
          </p>
          <Inbox apiBase={API_BASE} apiState={apiState} />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <p className="text-slate-600">
            Paste a message, upload a screenshot, or paste a raw email. Each returns one risk
            score.
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

          <form onSubmit={onAnalyzeImage} className="flex flex-col gap-4">
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-800">
              Screenshot
              <input
                type="file"
                accept="image/*"
                onChange={onImageChoice}
                className="text-sm font-normal text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white"
              />
            </label>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={pending}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
              >
                {pending ? 'Analyzing…' : 'Analyze screenshot'}
              </button>
            </div>
          </form>

          <form onSubmit={onAnalyzeEmail} className="flex flex-col gap-4">
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-800">
              Raw email
              <textarea
                value={emailSource}
                onChange={(event) => setEmailSource(event.target.value)}
                rows={8}
                placeholder="Paste a full email, including headers"
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-base font-normal text-slate-900 outline-none focus:border-slate-500"
              />
            </label>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={pending}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-60"
              >
                {pending ? 'Analyzing…' : 'Analyze email'}
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

          {fromImage && imageUrl ? (
            <div className="relative w-fit max-w-full">
              <img
                src={imageUrl}
                alt="Screenshot being analyzed"
                className="max-w-full rounded-md border border-slate-300"
              />
              {result?.image_width && result.highlights
                ? result.highlights.map((box) => (
                    <span
                      key={`${box.x}-${box.y}-${box.width}-${box.height}`}
                      className="pointer-events-none absolute border-2 border-amber-700 bg-amber-400/30"
                      style={{
                        left: `${(box.x / result.image_width) * 100}%`,
                        top: `${(box.y / result.image_height) * 100}%`,
                        width: `${(box.width / result.image_width) * 100}%`,
                        height: `${(box.height / result.image_height) * 100}%`,
                      }}
                    />
                  ))
                : null}
            </div>
          ) : null}

          {fromImage && result?.text ? (
            <p className="text-sm text-slate-600">Read from image: {result.text}</p>
          ) : null}

          {result ? <ResultView result={result} /> : null}
        </div>
      )}
    </main>
  )
}

export default App
