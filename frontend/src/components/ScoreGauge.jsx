import { BAND_COLORS, bandLabel } from '../slices.js'

const ARC = 'M 20 100 A 80 80 0 0 1 180 100'

export default function ScoreGauge({ score, band }) {
  const value = Math.max(0, Math.min(100, Math.round(Number(score) || 0)))
  const color = BAND_COLORS[band] ?? BAND_COLORS.low

  return (
    <figure className="flex flex-col items-center">
      <svg
        viewBox="0 0 200 118"
        className="w-full max-w-60"
        role="img"
        aria-label={`Risk score ${value} out of 100, ${bandLabel(band)}`}
      >
        <path
          d={ARC}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="16"
          strokeLinecap="round"
          pathLength="100"
        />
        {value > 0 ? (
          <path
            d={ARC}
            fill="none"
            stroke={color}
            strokeWidth="16"
            strokeLinecap="round"
            pathLength="100"
            strokeDasharray={`${value} 100`}
          />
        ) : null}
        <text x="100" y="90" textAnchor="middle" fontSize="40" fontWeight="600" fill="#0f172a">
          {value}
        </text>
        <text x="100" y="112" textAnchor="middle" fontSize="13" fill="#64748b">
          out of 100
        </text>
      </svg>
      <figcaption className="mt-1 text-sm font-semibold tracking-wide" style={{ color }}>
        {bandLabel(band)}
      </figcaption>
    </figure>
  )
}
