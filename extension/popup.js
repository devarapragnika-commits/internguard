const API_BASE = 'http://127.0.0.1:8000'
const listEl = document.getElementById('list')
const gmailListEl = document.getElementById('gmail-list')
const gmailHeadingEl = document.getElementById('gmail-heading')
const listingResultEl = document.getElementById('listing-result')
const listingDetailEl = document.getElementById('listing-detail')
const statusEl = document.getElementById('status')

function bandLabel(band) {
  if (band === 'high') {
    return 'HIGH RISK'
  }
  if (band === 'medium') {
    return 'MEDIUM RISK'
  }
  return 'LOW RISK'
}

function escapeText(value) {
  const node = document.createElement('div')
  node.textContent = value == null ? '' : String(value)
  return node.innerHTML
}

function detailHtml(row) {
  const reasons =
    row.reasons && row.reasons.length
      ? `<ul>${row.reasons.map((reason) => `<li>${escapeText(reason)}</li>`).join('')}</ul>`
      : '<p>No risk flags found.</p>'
  return `
    <h2>RISK SCORE: ${escapeText(row.score)}/100 — ${escapeText(bandLabel(row.band))}</h2>
    ${reasons}
    <p>${escapeText(row.recommendation)}</p>
  `
}

function renderList(messages, target) {
  target.innerHTML = ''
  messages.forEach((row) => {
    const item = document.createElement('li')
    const button = document.createElement('button')
    const detail = document.createElement('section')
    button.type = 'button'
    button.className = 'row'
    button.innerHTML = `
      <span class="badge ${escapeText(row.band)}">${escapeText(row.band)}</span>
      <span>
        <span class="subject">${escapeText(row.subject)}</span>
        <span class="from">${escapeText(row.from_name ? `${row.from_name} <${row.from_address}>` : row.from_address)}</span>
        ${row.attachments && row.attachments.length ? `<span class="files">${escapeText(row.attachments.join(', '))}</span>` : ''}
      </span>
    `
    detail.className = 'detail'
    detail.hidden = true
    detail.innerHTML = detailHtml(row)
    button.addEventListener('click', () => {
      const wasOpen = !detail.hidden
      target.querySelectorAll('.row').forEach((node) => node.classList.remove('selected'))
      target.querySelectorAll('.detail').forEach((node) => {
        node.hidden = true
      })
      if (!wasOpen) {
        button.classList.add('selected')
        detail.hidden = false
      }
    })
    item.appendChild(button)
    item.appendChild(detail)
    target.appendChild(item)
  })
}

function isListingUrl(url) {
  if (!url) {
    return false
  }
  return url.includes('linkedin.com') || url.includes('indeed.com')
}

function showListingScore(scored) {
  listingResultEl.hidden = false
  listingDetailEl.innerHTML = detailHtml(scored)
  statusEl.textContent =
    'This listing was scored from the text already on the page. It is not stored.'
}

function scoreListingText(text) {
  const message = (text || '').trim()
  if (!message) {
    statusEl.textContent = 'Open a job listing or message, then click InternGuard again.'
    return
  }
  fetch(`${API_BASE}/analyze/text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: message }),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error('Listing request failed')
      }
      return response.json()
    })
    .then((data) => {
      showListingScore(data)
    })
    .catch(() => {
      statusEl.textContent = 'Start the InternGuard API on port 8000, then open this popup again.'
    })
}

function loadActiveTab() {
  if (typeof chrome === 'undefined' || !chrome.tabs) {
    return
  }
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs && tabs[0]
    if (!tab || !tab.id) {
      return
    }
    const url = tab.url || ''
    if (url.includes('mail.google.com')) {
      chrome.tabs.sendMessage(tab.id, { type: 'get-gmail-rows' }, (response) => {
        if (chrome.runtime.lastError || !response || !response.ok) {
          return
        }
        const messages = response.messages || []
        if (!messages.length) {
          return
        }
        gmailHeadingEl.hidden = false
        renderList(messages, gmailListEl)
        statusEl.textContent =
          'Gmail badges use subject, sender, and snippet already on the page. Opening a row here shows the same score and reasons.'
      })
    }
    if (isListingUrl(url)) {
      chrome.tabs.sendMessage(tab.id, { type: 'get-listing-text' }, (response) => {
        if (chrome.runtime.lastError || !response || !response.ok) {
          statusEl.textContent = 'Open a job listing or message, then click InternGuard again.'
          return
        }
        scoreListingText(response.text)
      })
    }
  })
}

fetch(`${API_BASE}/inbox`)
  .then((response) => {
    if (!response.ok) {
      throw new Error('Inbox request failed')
    }
    return response.json()
  })
  .then((data) => {
    statusEl.textContent = 'Sandbox inbox. Choose a row to see why it was flagged.'
    renderList(data.messages || [], listEl)
    loadActiveTab()
  })
  .catch(() => {
    statusEl.textContent = 'Start the InternGuard API on port 8000, then open this popup again.'
    loadActiveTab()
  })
