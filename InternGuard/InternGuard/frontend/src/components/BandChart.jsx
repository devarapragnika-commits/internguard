import { BANDS } from '../history.js'
import { BAND_COLORS, bandLabel } from '../slices.js'

export default function BandChart({ counts }) {
  const largest = Math.max(1, ...BANDS.map((band) => counts[band]))

  return (
    <ul className="space-y-3" aria-label="Past checks by band">
      {BANDS.map((band) => (
        <li key={band} className="grid grid-cols-[7.5rem_1fr_2rem] items-center gap-3 text-sm">
          <span className="text-slate-700">{bandLabel(band)}</span>
          <div className="h-3 rounded-full bg-slate-100">
            <div
              className="h-3 rounded-full"
              style={{
                width: `${(counts[band] / largest) * 100}%`,
                backgroundColor: BAND_COLORS[band],
              }}
            />
          </div>
          <span className="text-right tabular-nums text-slate-600">{counts[band]}</span>
        </li>
      ))}
    </ul>
  )
}
