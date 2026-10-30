export default function SliceChart({ rows }) {
  return (
    <ul className="space-y-3" aria-label="Points by slice">
      {rows.map((row) => {
        const percent = row.cap > 0 ? Math.min(100, (row.points / row.cap) * 100) : 0
        return (
          <li key={row.key}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="text-slate-700">{row.label}</span>
              <span className="tabular-nums text-slate-500">
                {row.points}/{row.cap}
              </span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-slate-800"
                style={{ width: `${percent}%` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
