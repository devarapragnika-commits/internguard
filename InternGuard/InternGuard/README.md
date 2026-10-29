# InternGuard

InternGuard scores job, internship, and email messages for scam risk. The Analyze page scores pasted text and explains the reasons.

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

`POST /analyze/text` accepts JSON `{"text": "..."}` and returns a 0–100 score, a band, the reasons, and a recommendation. Empty text is rejected. Company, URL, sender, and attachment points stay at 0 until those modules award points.

## Frontend

In a second terminal, from this folder:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL Vite prints, usually [http://localhost:5173](http://localhost:5173). Paste a message and click Analyze. The page shows the score, the reasons, and a recommendation when the API is running.

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
