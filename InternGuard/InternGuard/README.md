# InternGuard

InternGuard scores job, internship, and email messages for scam risk. The Analyze page accepts pasted text, a screenshot, and a raw email. Each call returns one 0–100 score, a band, the reasons, and a recommendation. The Demo inbox page lists fixture messages with a low, medium, or high badge before a row is opened.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer

## Backend

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` instead.

Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health). A running API returns:

```json
{"status": "ok"}
```

API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Frontend

In a second terminal, from this folder:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints, usually [http://localhost:5173](http://localhost:5173). Paste a message and choose Analyze, upload a screenshot, or paste a raw email. Choose Demo inbox (`#inbox`) to see pre-open badges on sandbox messages. The page shows a 0–100 gauge, points by slice, the reasons, and a recommendation when the API on port 8000 is running. If the API is running, the page also shows "API connected".

History is a second tab on the same page (`#history`). Each successful text, screenshot, or email check is saved in this browser only: score, band, reasons, recommendation, slices, and a short excerpt. The full message, screenshots, and raw emails are not stored. Refreshing the page keeps the list. An API failure shows an error and does not wipe history. An empty list shows a first-use message.

Screenshot reading needs the Tesseract program, not only the Python package. On Windows, install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and restart the API. The installer path `C:\Program Files\Tesseract-OCR\tesseract.exe` is picked up automatically. Set `TESSERACT_CMD` if it lives somewhere else.

## Baseline models

The labeled file must already exist at `data/messages.csv`. This command does not create messages. From this folder:

```powershell
python -m backend.ml.train_baselines
```

It trains TF-IDF plus Logistic Regression, Random Forest, and XGBoost with seed 42, then writes:

- `models/tfidf_logreg.joblib`
- `models/random_forest.joblib`
- `models/xgboost.joblib`
- `models/comparison.csv`
- `models/run_settings.json`

`comparison.csv` includes accuracy, macro F1, scam-class precision, scam-class recall, and the dataset version. If `data/messages.csv` is missing, the command stops and does not write a table.

## Optional OpenRouter check

The existing OpenRouter client is not the scam classifier. To smoke-test that client, copy `.env.example` to `.env`, put your key in `.env`, and run:

```powershell
python test_llm.py
```

Do not commit `.env`. `.env.example` contains names only, with a placeholder key.

## URL features

`extract_url_features` in `backend/services/url_features.py` checks a link on the server. The React page does not open it.

HTTPS, the suspicious-TLD check, and the subdomain count are computed locally. Edit `backend/data/suspicious_tlds.txt` to change which top-level domains count as suspicious. One domain per line.

These lookups can be unknown instead of failing the call:

- `domain_age` when WHOIS times out, the host has no domain, or WHOIS has no creation date
- `redirects` when the check times out, the URL is not http(s), or the host is not a public address
- `virustotal` stays off unless `VIRUSTOTAL_API_KEY` is set. If that lookup times out or fails, its status is unknown

From this folder:

```powershell
python -m unittest test_url_features -v
```

## Claimed company and domain

`compare_claimed_company` in `backend/services/company_domain.py` compares the organization named in a message with the registrable domain of the link or sender. It does not read the verified-company list, and it does not check whether the TLD is suspicious. Abbreviations such as TCS are handled by the list below.

A lookalike such as a Microsoft internship leading to `secure-login.tk` is flagged with "claimed company does not match link domain." A link on `microsoft.com` is not flagged. Text with no company name is not flagged.

Names shorter than 4 letters are ignored, including hp, ey, ge, ai, hr, it, and ibm. Generic words such as company, team, internship, and software are ignored too.

From this folder:

```powershell
python -m unittest test_company_domain -v
```

## Verified company domains

`check_verified_company` in `backend/services/company_list.py` reads `backend/data/verified_companies.csv`. Edit that file to add an employer. There is no company API.

Columns are `company`, `aliases`, and `domains`. Put extra aliases or domains in the same cell, separated by semicolons. A domain is the registrable domain, such as `tcs.com`, not a full link.

When the message names a company on the list:

- A link or sender domain on that company's list adds no company-verification points. The fuzzy mismatch is not added for that domain, so Tata Consultancy Services can use `tcs.com`.
- Any other domain adds 5 points, capped at 15. The reason says the company requires verification. It does not call the offer a scam.
- A company that is not in the CSV adds no list points. The fuzzy check still runs.
- A listed company with no link and no sender is not a list failure.

From this folder:

```powershell
python -m unittest test_company_list -v
```

## Combined score

`score_message` in `backend/services/risk.py` is what `POST /analyze/text` returns. One call runs the linguistic features, the payment detector, the http(s) links in the message, the URL feature extractor, the claimed-company check, and the verified-company list.

Each slice is capped the way `Roadmap.txt` specifies, then divided by 110 and multiplied by 100:

- Linguistic signals score 4 points each, at most 20, cap 25
- A payment demand scores 25, cap 25
- URL and domain signals score up to 20: company mismatch 6, suspicious TLD 5, domain younger than 90 days 4, VirusTotal 4, two or more subdomains 3, two or more redirects 3, and a non-HTTPS link 2
- A listed company whose link or sender domain is not on its verified list scores 5, cap 15
- Sender authenticity scores up to 15: SPF fail 5, DKIM fail 5, DMARC fail 5, a company display name on a free mailbox 6, and a Reply-To mismatch 4
- Attachment risk scores up to 10: a double extension such as pdf.exe 6, a dangerous extension 5, a macro-enabled Office file 4, and an extension that does not match the declared type 4

Bands are 0–19 low, 20–49 medium, and 50–100 high. A message with no link leaves URL risk at 0. If a URL lookup fails, the text score is kept and the reasons include "URL check was unavailable." Unknown domain age, redirects, and VirusTotal are not treated as risky.

From this folder:

```powershell
python -m unittest test_risk -v
```

## Email headers and attachments

`POST /analyze/email` accepts a raw RFC 822 message, or headers plus a snippet and attachment filenames. HTML is not rendered, remote images are not loaded, and attachments are not opened. The subject and snippet go through the same linguistic and payment checks. Links in the raw source go through the URL checks. Sender and attachment points are added in `score_message`, still divided by 110.

If the headers cannot be read, the text score is kept and the reasons include "Sender check was unavailable." Tests use fixture headers and filenames. They do not open a mailbox.

From this folder:

```powershell
python -m unittest test_mail -v
```

## Demo inbox

`GET /inbox` scores three local fixture messages from headers, a snippet, and attachment filenames. It does not open a Gmail account, fetch a message body, or load remote images. Each row already has a band from `score_message` (0–19 low, 20–49 medium, 50–100 high). Opening a row shows the same score, reasons, and recommendation under that row.

The Demo inbox tab on the React page lists those rows. A Chrome Manifest V3 extension in `extension/` shows the same sandbox list. It requests no send or modify scopes. Load it unpacked from `extension/` in `chrome://extensions` with Developer mode on. The API on port 8000 must be running.

From this folder:

```powershell
python -m unittest test_inbox -v
```

## Screenshots

`POST /analyze/image` accepts one image. Tesseract reads it on the server. The text is cleaned (a word split across a line, a digit between letters, spaced-out letters, and spaces inside a link) and then passed to `score_message`. The response is the same score, band, reasons, and recommendation, plus highlight boxes for the phrases that fired.

An empty file, a non-image, or a failed read returns a clear error and no score. Tests do not call Tesseract or a paid API.

From this folder:

```powershell
python -m unittest test_ocr -v
```

## Payment requests

`detect_payment_request` in `backend/services/payment.py` scores only the financial-request slice. A fee, deposit, gift card, crypto payment, or a demand to pay for an offer letter or laptop sets that score to 25. A message with no payment demand leaves it at 0. "No registration fee" does not count.

From this folder:

```powershell
python -m unittest test_payment -v
```
