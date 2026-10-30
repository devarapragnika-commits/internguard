import { useState } from 'react'

import { bandCounts } from '../history.js'
import { BAND_COLORS, bandLabel, CHANNEL_LABELS } from '../slices.js'
import BandChart from './BandChart.jsx'
import ResultView from './ResultView.jsx'

export default function HistoryView({ history, onStart, onClear }) {
  const [openId, setOpenId] = useState(null)
  const open = history.find((entry) => entry.id === openId) ?? null

  if (history.length === 0) {
    return (
      <section className="rounded-md border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
        <h2 className="text-lg font-semibold text-slate-900">No checks yet</h2>
        <p className="mt-2 text-sm text-slate-600">
          Analyze a message to see it here. History stays in this browser and keeps only a short
          excerpt, the score, and the reasons.
        </p>
        <button
          type="button"
          onClick={onStart}
          className="mt-5 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Analyze a message
        </button>
      </section>
    )
  }

  function onClearClick() {
    if (window.confirm('Delete all past checks from this browser?')) {
      setOpenId(null)
      onClear()
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-medium text-slate-900">
            Past checks by band ({history.length})
          </h2>
          <button
            type="button"
            onClick={onClearClick}
            className="text-sm text-slate-500 underline-offset-2 hover:text-slate-800 hover:underline"
          >
            Clear history
          </button>
        </div>
        <BandChart counts={bandCounts(history)} />
      </div>

      <ul className="divide-y divide-slate-100 rounded-md border border-slate-200 bg-white">
        {history.map((entry) => {
          const selected = entry.id === openId
          return (
            <li key={entry.id}>
              <button
                type="button"
                onClick={() => setOpenId(selected ? null : entry.id)}
                aria-expanded={selected}
                className={`flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-slate-50 sm:flex-row sm:items-center sm:gap-4 ${
                  selected ? 'bg-slate-50' : ''
                }`}
              >
                <span className="flex shrink-0 items-baseline gap-2 sm:w-36">
                  <span className="text-lg font-semibold tabular-nums text-slate-900">
                    {entry.score}
                  </span>
                  <span
                    className="text-xs font-semibold tracking-wide"
                    style={{ color: BAND_COLORS[entry.band] }}
                  >
                    {bandLabel(entry.band)}
                  </span>
                </span>
                <span className="min-w-0 flex-1 truncate text-sm text-slate-700">
                  {entry.excerpt || '(empty message)'}
                </span>
                <span className="shrink-0 text-xs text-slate-500">
                  {CHANNEL_LABELS[entry.channel] ?? entry.channel} ·{' '}
                  {new Date(entry.createdAt).toLocaleString()}
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      {open ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-slate-600">
            Check from {new Date(open.createdAt).toLocaleString()}: “{open.excerpt}”
          </p>
          <ResultView result={open} />
        </div>
      ) : null}
    </section>
  )
}
