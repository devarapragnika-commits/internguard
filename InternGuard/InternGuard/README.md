# InternGuard

InternGuard scores job, internship, and email messages for scam risk. This repository currently runs the API skeleton and a placeholder Analyze page. Scoring is not connected yet.

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

Open the URL Vite prints, usually [http://localhost:5173](http://localhost:5173). The Analyze page is a placeholder. The button does not score a message. If the API is running, the page shows "API connected".

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

`compare_claimed_company` in `backend/services/company_domain.py` compares the organization named in a message with the registrable domain of the link or sender. It does not use a verified-company list, and it does not check whether the TLD is suspicious.

A lookalike such as a Microsoft internship leading to `secure-login.tk` is flagged with "claimed company does not match link domain." A link on `microsoft.com` is not flagged. Text with no company name is not flagged.

Names shorter than 4 letters are ignored, including hp, ey, ge, ai, hr, it, and ibm. Generic words such as company, team, internship, and software are ignored too.

From this folder:

```powershell
python -m unittest test_company_domain -v
```
