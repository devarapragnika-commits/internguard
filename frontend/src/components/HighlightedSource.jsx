export default function HighlightedSource({ source, highlights, activeReason, onSelectReason }) {
  const marks = Array.isArray(highlights) ? [...highlights].sort((a, b) => a.start - b.start) : []
  if (!source) {
    return null
  }

  const pieces = []
  let cursor = 0
  marks.forEach((mark, index) => {
    const start = Math.max(0, Math.min(source.length, mark.start))
    const end = Math.max(start, Math.min(source.length, mark.end))
    if (start < cursor) {
      return
    }
    if (start > cursor) {
      pieces.push(<span key={`t-${cursor}`}>{source.slice(cursor, start)}</span>)
    }
    const selected = activeReason && mark.reason === activeReason
    pieces.push(
      <mark
        key={`h-${index}-${start}`}
        id={`text-highlight-${index}`}
        data-reason={mark.reason}
        className={
          selected
            ? 'rounded-sm bg-amber-400/80 ring-2 ring-amber-700'
            : 'rounded-sm bg-amber-400/40'
        }
      >
        {source.slice(start, end)}
      </mark>,
    )
    cursor = end
  })
  if (cursor < source.length) {
    pieces.push(<span key={`t-${cursor}`}>{source.slice(cursor)}</span>)
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-4">
      <h2 className="text-sm font-medium text-slate-900">Flagged phrases</h2>
      {marks.length === 0 ? (
        <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{source}</p>
      ) : (
        <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{pieces}</p>
      )}
      {onSelectReason ? (
        <p className="mt-2 text-xs text-slate-500">Choose a reason below to jump to the phrase.</p>
      ) : null}
    </div>
  )
}

export function scrollToReason(highlights, reason) {
  const marks = Array.isArray(highlights) ? highlights : []
  const index = marks.findIndex((item) => item.reason === reason)
  if (index < 0) {
    return
  }
  const node = document.getElementById(`text-highlight-${index}`)
  node?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
