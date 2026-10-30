// Past checks stay in this browser's localStorage. Only the score, band,
// reasons, recommendation, slices, and a short excerpt are kept. The full
// message, screenshots, and raw emails are never stored.

const STORAGE_KEY = 'internguard.history.v1'
const MAX_ENTRIES = 200
const EXCERPT_LENGTH = 120

export const BANDS = ['low', 'medium', 'high']

export function loadHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter(isEntry) : []
  } catch {
    return []
  }
}

export function createEntry(result, channel, message) {
  return {
    id: newId(),
    createdAt: new Date().toISOString(),
    channel,
    excerpt: makeExcerpt(message),
    score: result.score,
    band: result.band,
    reasons: Array.isArray(result.reasons) ? result.reasons : [],
    recommendation: result.recommendation ?? '',
    slices: result.slices ?? {},
  }
}

export function addEntry(entry) {
  const next = [entry, ...loadHistory()].slice(0, MAX_ENTRIES)
  writeHistory(next)
  return next
}

export function clearHistory() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage is unavailable. The in-memory list is still cleared.
  }
  return []
}

export function bandCounts(history) {
  const counts = { low: 0, medium: 0, high: 0 }
  for (const entry of history) {
    counts[entry.band] += 1
  }
  return counts
}

export function makeExcerpt(message) {
  const flat = String(message ?? '').replace(/\s+/g, ' ').trim()
  return flat.length > EXCERPT_LENGTH ? `${flat.slice(0, EXCERPT_LENGTH - 1)}…` : flat
}

function writeHistory(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Storage is full or blocked. The check is still shown on screen.
  }
}

function isEntry(value) {
  return (
    value !== null &&
    typeof value === 'object' &&
    typeof value.id === 'string' &&
    typeof value.createdAt === 'string' &&
    typeof value.score === 'number' &&
    BANDS.includes(value.band)
  )
}

function newId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function isHistoryKey(key) {
  return key === null || key === STORAGE_KEY
}
