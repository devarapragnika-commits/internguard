const CONTAINERS = [
  '#job-details',
  '.jobs-description__content',
  '.jobs-box__html-content',
  '#jobDescriptionText',
  '.jobsearch-JobComponent-description',
  '[data-testid="jobsearch-JobComponent-description"]',
]
const MESSAGES = '.msg-s-event-listitem__body, .msg-s-event-listitem__message-bubble'
const MAX_LISTING_CHARS = 15000
const MIN_BLOCK_CHARS = 40

function cleanText(value) {
  return String(value || '')
    .split(/\n+/)
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .join('\n')
    .trim()
}

function mergeTitle(title, body) {
  const heading = cleanText(title)
  const text = cleanText(body)
  if (heading && text) {
    if (text.toLowerCase().startsWith(heading.toLowerCase())) {
      return text
    }
    return `${heading}\n\n${text}`
  }
  return text || heading
}

function extractListingText() {
  const title = (document.querySelector('h1') && document.querySelector('h1').innerText) || ''
  for (let i = 0; i < CONTAINERS.length; i += 1) {
    const node = document.querySelector(CONTAINERS[i])
    const body = node ? node.innerText || '' : ''
    if (cleanText(body).length >= MIN_BLOCK_CHARS) {
      return mergeTitle(title, body).slice(0, MAX_LISTING_CHARS)
    }
  }
  const messages = Array.from(document.querySelectorAll(MESSAGES))
    .map((node) => cleanText(node.innerText || ''))
    .filter((text) => text.length >= 20)
  if (messages.length) {
    return mergeTitle(title, messages.join('\n\n')).slice(0, MAX_LISTING_CHARS)
  }
  const main = document.querySelector('main, [role="main"]')
  const fallback = main ? main.innerText || '' : ''
  if (cleanText(fallback).length >= MIN_BLOCK_CHARS) {
    return mergeTitle(title, fallback).slice(0, MAX_LISTING_CHARS)
  }
  return mergeTitle(title, '').slice(0, MAX_LISTING_CHARS)
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== 'get-listing-text') {
    return
  }
  sendResponse({ ok: true, text: extractListingText() })
})
