const API_BASE = 'http://127.0.0.1:8000'

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== 'score-list') {
    return
  }
  fetch(`${API_BASE}/analyze/list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: message.messages || [] }),
  })
    .then(async (response) => {
      const data = await response.json().catch(() => ({}))
      sendResponse({ ok: response.ok, data })
    })
    .catch(() => {
      sendResponse({ ok: false, data: { detail: 'Start the InternGuard API on port 8000.' } })
    })
  return true
})
