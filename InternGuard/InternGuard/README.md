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
