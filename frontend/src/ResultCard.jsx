function bandLabel(band) {
  if (band === 'high') {
    return 'HIGH RISK'
  }
  if (band === 'medium') {
    return 'MEDIUM RISK'
  }
  return 'LOW RISK'
}

function ResultCard({ result, extra = null, nested = false }) {
  if (!result) {
    return null
  }

  return (
    <section
      className={
        nested
          ? 'border-t border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800'
          : 'mt-6 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800'
      }
    >
      <p className="font-medium text-slate-900">
        RISK SCORE: {result.score}/100 — {bandLabel(result.band)}
      </p>
      <p className="mt-2 text-slate-600">
        Linguistic {result.slices.linguistic.points}/{result.slices.linguistic.cap}
        {' · '}
        Financial request {result.slices.financial_request.points}/{result.slices.financial_request.cap}
        {' · '}
        URL/domain {result.slices.url_domain.points}/{result.slices.url_domain.cap}
        {' · '}
        Sender {result.slices.sender_authenticity.points}/{result.slices.sender_authenticity.cap}
        {' · '}
        Attachment {result.slices.attachment.points}/{result.slices.attachment.cap}
        {' · '}
        Company verification {result.slices.company_verification.points}/
        {result.slices.company_verification.cap}
      </p>
      {result.reasons.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5">
          {result.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-3">No risk flags found.</p>
      )}
      {extra}
      <p className="mt-3">{result.recommendation}</p>
    </section>
  )
}

export { bandLabel, ResultCard }
