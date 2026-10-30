# InternGuard

InternGuard scores job, internship, and email messages for scam risk. The Analyze page sends one pasted message to `POST /analyze/text` and shows one 0–100 score, a band, the reasons, and a recommendation.

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

Open the URL Vite prints, usually [http://localhost:5173](http://localhost:5173). Paste a message and choose Analyze. The page shows a 0–100 gauge, points by slice, the reasons, and a recommendation when the API on port 8000 is running. If the API is running, the page also shows "API connected".

History is a second tab on the same page (`#history`). Each successful check is saved in this browser only: score, band, reasons, recommendation, slices, and a short excerpt. The full message, screenshots, and raw emails are not stored. Refreshing the page keeps the list. An API failure shows an error and does not wipe history. An empty list shows a first-use message. Screenshot and email results can use the same history later by saving with a different `channel`.

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
- Sender authenticity (cap 15) and attachment risk (cap 10) stay at 0

Bands are 0–19 low, 20–49 medium, and 50–100 high. A message with no link leaves URL risk at 0. If a URL lookup fails, the text score is kept and the reasons include "URL check was unavailable." Unknown domain age, redirects, and VirusTotal are not treated as risky.

From this folder:

```powershell
python -m unittest test_risk -v
```

## Payment requests

`detect_payment_request` in `backend/services/payment.py` scores only the financial-request slice. A fee, deposit, gift card, crypto payment, or a demand to pay for an offer letter or laptop sets that score to 25. A message with no payment demand leaves it at 0. "No registration fee" does not count.

From this folder:

```powershell
python -m unittest test_payment -v
```
