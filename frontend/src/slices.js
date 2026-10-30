// The roadmap slices, in roadmap order. Every slice is shown, including the
// ones that are still 0 because their channel does not exist yet.
export const SLICES = [
  { key: 'linguistic', label: 'Linguistic / text', cap: 25 },
  { key: 'financial_request', label: 'Financial request', cap: 25 },
  { key: 'url_domain', label: 'URL / domain', cap: 20 },
  { key: 'sender_authenticity', label: 'Sender authenticity', cap: 15 },
  { key: 'attachment', label: 'Attachment', cap: 10 },
  { key: 'company_verification', label: 'Company verification', cap: 15 },
]

export function sliceRows(slices) {
  return SLICES.map((slice) => {
    const value = slices?.[slice.key]
    const points = Number(value?.points) || 0
    const cap = Number(value?.cap) || slice.cap
    return { ...slice, points, cap }
  })
}

export function bandLabel(band) {
  if (band === 'high') {
    return 'HIGH RISK'
  }
  if (band === 'medium') {
    return 'MEDIUM RISK'
  }
  return 'LOW RISK'
}

export const BAND_COLORS = {
  low: '#059669',
  medium: '#d97706',
  high: '#dc2626',
}

export const CHANNEL_LABELS = {
  text: 'Pasted text',
  screenshot: 'Screenshot',
  email: 'Email',
}
