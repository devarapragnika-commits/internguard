const scoredByKey = {}
const inflight = new Set()
let scanTimer = 0
let openDetail = null

function bandLabel(band) {
  if (band === 'high') {
    return 'HIGH RISK'
  }
  if (band === 'medium') {
    return 'MEDIUM RISK'
  }
  return 'LOW RISK'
}

function rowNodes() {
  return Array.from(document.querySelectorAll('tr.zA, div.zA, div[role="listitem"]')).filter((node) => {
    return Boolean(node.querySelector('[email], .bog, .bqe, .y2'))
  })
}

function cleanSnippet(text) {
  return String(text || '')
    .replace(/\u00a0/g, ' ')
    .replace(/\u200b/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^[\s.\-–—]+/, '')
    .trim()
}

function extractRow(row) {
  const emailEl = row.querySelector('[email]')
  const fromAddress = emailEl ? (emailEl.getAttribute('email') || '').trim() : ''
  const fromName = emailEl
    ? (emailEl.getAttribute('name') || emailEl.textContent || '').trim()
    : ''
  const subjectEl = row.querySelector('.bqe') || row.querySelector('.bog')
  const subject = subjectEl ? subjectEl.textContent.trim() : ''
  const snippetEl = row.querySelector('.y2')
  const snippet = cleanSnippet(snippetEl ? snippetEl.textContent : '')
  if (!subject && !snippet && !fromAddress) {
    return null
  }
  return {
    from_name: fromName,
    from_address: fromAddress,
    subject,
    snippet,
  }
}

function rowKey(meta) {
  return [meta.from_address, meta.subject, meta.snippet].join('\n')
}

function hideDetail() {
  if (openDetail) {
    openDetail.remove()
    openDetail = null
  }
}

function showDetail(badge, scored) {
  hideDetail()
  const pop = document.createElement('div')
  pop.className = 'internguard-detail'
  pop.setAttribute('role', 'dialog')
  const title = document.createElement('p')
  title.className = 'internguard-detail-title'
  title.textContent = `RISK SCORE: ${scored.score}/100 — ${bandLabel(scored.band)}`
  pop.appendChild(title)
  if (scored.reasons && scored.reasons.length) {
    const list = document.createElement('ul')
    scored.reasons.forEach((reason) => {
      const item = document.createElement('li')
      item.textContent = reason
      list.appendChild(item)
    })
    pop.appendChild(list)
  } else {
    const empty = document.createElement('p')
    empty.textContent = 'No risk flags found.'
    pop.appendChild(empty)
  }
  const rec = document.createElement('p')
  rec.textContent = scored.recommendation || ''
  pop.appendChild(rec)
  document.body.appendChild(pop)
  const rect = badge.getBoundingClientRect()
  const left = Math.min(Math.max(8, rect.left), window.innerWidth - 360)
  const top = rect.bottom + 6
  pop.style.left = `${left}px`
  pop.style.top = `${top}px`
  openDetail = pop
}

function stopGmailOpen(event) {
  event.preventDefault()
  event.stopPropagation()
}

function injectBadge(row, scored) {
  if (row.querySelector('.internguard-badge')) {
    return
  }
  const subjectEl = row.querySelector('.bqe') || row.querySelector('.bog')
  if (!subjectEl || !subjectEl.parentNode) {
    return
  }
  const badge = document.createElement('button')
  badge.type = 'button'
  badge.className = `internguard-badge ${scored.band}`
  badge.textContent = scored.band
  badge.setAttribute('aria-label', `InternGuard ${bandLabel(scored.band)}`)
  badge.title = `${bandLabel(scored.band)} ${scored.score}/100`
  ;['click', 'mousedown', 'mouseup', 'pointerdown', 'auxclick'].forEach((name) => {
    badge.addEventListener(name, stopGmailOpen, true)
  })
  badge.addEventListener(
    'click',
    (event) => {
      stopGmailOpen(event)
      if (openDetail) {
        hideDetail()
        return
      }
      showDetail(badge, scored)
    },
    true,
  )
  subjectEl.parentNode.insertBefore(badge, subjectEl)
}

function applyScores(messages) {
  const byKey = {}
  ;(messages || []).forEach((row) => {
    byKey[rowKey(row)] = row
    scoredByKey[rowKey(row)] = row
  })
  rowNodes().forEach((node) => {
    const meta = extractRow(node)
    if (!meta) {
      return
    }
    const scored = byKey[rowKey(meta)] || scoredByKey[rowKey(meta)]
    if (scored) {
      injectBadge(node, scored)
    }
  })
}

function scan() {
  const pending = []
  const seen = new Set()
  rowNodes().forEach((node) => {
    const meta = extractRow(node)
    if (!meta) {
      return
    }
    const key = rowKey(meta)
    if (scoredByKey[key] || inflight.has(key) || seen.has(key)) {
      if (scoredByKey[key]) {
        injectBadge(node, scoredByKey[key])
      }
      return
    }
    seen.add(key)
    pending.push(meta)
  })
  if (!pending.length) {
    return
  }
  pending.forEach((meta) => inflight.add(rowKey(meta)))
  chrome.runtime.sendMessage({ type: 'score-list', messages: pending }, (response) => {
    pending.forEach((meta) => inflight.delete(rowKey(meta)))
    if (chrome.runtime.lastError || !response || !response.ok) {
      return
    }
    applyScores((response.data && response.data.messages) || [])
  })
}

function scheduleScan() {
  if (scanTimer) {
    clearTimeout(scanTimer)
  }
  scanTimer = setTimeout(scan, 400)
}

document.addEventListener('click', (event) => {
  if (openDetail && !openDetail.contains(event.target) && !event.target.closest('.internguard-badge')) {
    hideDetail()
  }
})

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === 'get-gmail-rows') {
    sendResponse({ ok: true, messages: Object.values(scoredByKey) })
  }
})

const observer = new MutationObserver(scheduleScan)
observer.observe(document.documentElement, { childList: true, subtree: true })
scheduleScan()
