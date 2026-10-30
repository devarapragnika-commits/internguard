import { sliceRows } from '../slices.js'
import ScoreGauge from './ScoreGauge.jsx'
import SliceChart from './SliceChart.jsx'
import SliceTable from './SliceTable.jsx'

export default function ResultView({ result }) {
  const rows = sliceRows(result.slices)

  return (
    <section className="flex flex-col gap-4" aria-label="Analysis result">
      <div className="grid gap-4 md:grid-cols-[minmax(0,15rem)_1fr]">
        <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
          <ScoreGauge score={result.score} band={result.band} />
        </div>
        <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
          <h2 className="mb-3 text-sm font-medium text-slate-900">Points by slice</h2>
          <SliceChart rows={rows} />
        </div>
      </div>

      <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
        <h2 className="text-sm font-medium text-slate-900">Why it was flagged</h2>
        {(result.reasons ?? []).length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {(result.reasons ?? []).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-700">No risk flags found.</p>
        )}
        <h2 className="mt-4 text-sm font-medium text-slate-900">Recommendation</h2>
        <p className="mt-2 text-sm text-slate-700">{result.recommendation}</p>
      </div>

      <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
        <h2 className="mb-2 text-sm font-medium text-slate-900">Slice breakdown</h2>
        <SliceTable rows={rows} />
      </div>
    </section>
  )
}
