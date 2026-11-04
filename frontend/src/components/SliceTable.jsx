export default function SliceTable({ rows }) {
  const total = rows.reduce((sum, row) => sum + row.points, 0)
  const cap = rows.reduce((sum, row) => sum + row.cap, 0)

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-72 text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            <th className="py-2 pr-4 font-medium">Slice</th>
            <th className="py-2 pr-4 text-right font-medium">Points</th>
            <th className="py-2 text-right font-medium">Cap</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-800">
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="py-2 pr-4">{row.label}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{row.points}</td>
              <td className="py-2 text-right tabular-nums text-slate-500">{row.cap}</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="border-t border-slate-200 font-medium text-slate-900">
          <tr>
            <td className="py-2 pr-4">Total, before scaling to 100</td>
            <td className="py-2 pr-4 text-right tabular-nums">{total}</td>
            <td className="py-2 text-right tabular-nums text-slate-500">{cap}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
