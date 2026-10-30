const API_BASE = 'http://127.0.0.1:8000'
const listEl = document.getElementById('list')
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

function renderList(messages) {
  listEl.innerHTML = ''
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
      listEl.querySelectorAll('.row').forEach((node) => node.classList.remove('selected'))
      listEl.querySelectorAll('.detail').forEach((node) => {
        node.hidden = true
      })
      if (!wasOpen) {
        button.classList.add('selected')
        detail.hidden = false
      }
    })
    item.appendChild(button)
    item.appendChild(detail)
    listEl.appendChild(item)
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
    renderList(data.messages || [])
  })
  .catch(() => {
    statusEl.textContent = 'Start the InternGuard API on port 8000, then open this popup again.'
  })
