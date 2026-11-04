# InternGuard demo report

Numbers in this file come from `models/evaluation.csv` and `demos/last_run.json`. Regenerate them with:

```powershell
python -m backend.ml.train_baselines
python -m backend.ml.evaluate_scorer
python -m backend.ml.run_demo
```

Dataset version: **sha256:e08a9a505a4b:rows:348**. Seed 42. Stratified 80/20 split.

## 1. Problem

Students get internship and job offers on WhatsApp, Telegram, LinkedIn, email, and screenshots. Many of those offers ask for a fee, a gift card, or a lookalike link. A binary "scam / not scam" label is not enough. InternGuard returns one 0–100 score, a band, the flags that fired, and a recommendation, using the same rubric for pasted text, a screenshot, a link inside the message, and a raw email.

The live product is that rubric. The three TF-IDF models are a baseline for the report, not the score shown in the app.

## 2. Related detectors

Gmail and Outlook already show phishing banners. VirusTotal scores domains. Generic spam filters look for bulk mail. They rarely explain a polite joining fee, a company name that does not match the link, or a `pdf.exe` attachment. InternGuard combines linguistic, payment, URL, company-list, sender, and attachment checks into one explainable score.

## 3. Architecture

```text
paste / screenshot / URL-in-text / raw email
        -> features
        -> rubric (caps sum to 110, then scaled to 0-100)
        -> score, band, reasons, recommendation
```

| Slice | Cap |
|---|---|
| Linguistic / text | 25 |
| Financial request | 25 |
| URL / domain | 20 |
| Sender authenticity | 15 |
| Attachment | 10 |
| Company verification | 15 |

Bands: 0–19 low, 20–49 medium, 50–100 high.

Pasted text and screenshot OCR both call `score_message`. Email adds sender and attachment points in `score_email` without rendering the message.

## 4. Dataset

`data/messages.csv` has 348 rows: 247 legitimate, 20 suspicious, 81 scam.

- Hand-written rows, including the original 15 and 25 added for this evaluation (`source=hand-written`, `is_synthetic=true`).
- Unique contract texts from `job_contract_scam_dataset.csv` (`source=job_contract_scam_dataset`, `is_synthetic=true`).

Suspicious is no longer five rows. The file is still mostly templated contract language, which is a limitation.

## 5. Results

### 5.1 Comparison table

From `models/evaluation.csv`. Scam precision and recall are for the **scam** class only. Legitimate false-positive rate is the share of **legitimate** test rows predicted as scam. For the rubric, low maps to legitimate, medium to suspicious, and high to scam.

| Method | Accuracy | Macro F1 | Scam precision | Scam recall | Legit → scam FP rate |
|---|---|---|---|---|---|
| TF-IDF + Logistic Regression | 0.9857 | 0.9491 | 1.0000 | 1.000 | 0.0 |
| Random Forest | 0.9571 | 0.9044 | 1.0000 | 0.875 | 0.0 |
| XGBoost | 0.9429 | 0.7978 | 0.9333 | 0.875 | 0.0 |
| Rubric (live product) | 0.7286 | 0.3516 | 0.0000 | 0.000 | 0.0 |

The models look strong because many contract rows repeat the same templates across train and test. The rubric does not memorize those templates. On this split, **none of the 16 held-out scam contracts reached band high** (8 scored medium, 8 scored low). None of the 50 held-out legitimate rows were called scam. That is why rubric scam precision and recall are 0.0 while the legitimate false-positive rate stays 0.0.

The demo messages below use fee language and lookalike links, which is what the product is built to catch.

### 5.2 Three-message demo

Expected bands are in `demos/expected.json`. Screenshot scoring was skipped here because Tesseract is not installed on the machine that wrote `demos/last_run.json`. The same wording still runs on text, link (URL inside the message), and email.

**Legitimate** (expected **low**)

> Our campus internship is unpaid. Apply on the company careers page. There is no fee.

| Channel | Score | Band | Reasons |
|---|---|---|---|
| Text | 0/100 | low | none |
| Link | 0/100 | low | none |
| Screenshot | skipped | | Tesseract is not installed |
| Email | 0/100 | low | none |

**Obvious scam** (expected **high**)

> Congratulations, you are selected. Pay the registration fee today only. Guaranteed internship. Do not share this. Send your bank account number. Act now. Apply at http://microsoft.secure-login.tk/offer

| Channel | Score | Band | Reasons |
|---|---|---|---|
| Text | 53/100 | high | urgency, registration fee, bank account, guaranteed internship, secrecy, lookalike `.tk` link, no HTTPS |
| Link | 53/100 | high | same as text (the URL is in the message) |
| Screenshot | skipped | | Tesseract is not installed |
| Email | 75/100 | high | text flags plus SPF/DKIM/DMARC fail, free-mail display name, Reply-To mismatch, `offer.pdf.exe` |

**Subtle / easy to miss** (expected **medium**)

> Tata Consultancy Services internship. Kindly pay the joining fee to confirm your seat. Apply at https://secure-login.tk/offer

| Channel | Score | Band | Reasons |
|---|---|---|---|
| Text | 41/100 | medium | joining fee, claimed company does not match link domain, suspicious TLD, Tata Consultancy Services requires verification |
| Link | 41/100 | medium | same as text |
| Screenshot | skipped | | Tesseract is not installed |
| Email | 41/100 | medium | same wording flags; this fixture has no SPF fail or `pdf.exe` |

## 6. Limitations

- Abbreviations that are not in `backend/data/verified_companies.csv` do not get company-list points. Names shorter than four letters are ignored by the fuzzy check, so IBM-style shorts still need an alias in the CSV.
- WHOIS, redirects, and VirusTotal can time out. The text score is kept and the reasons include "URL check was unavailable." Unknown lookups are not scored as risky.
- Most labeled scam rows are templated contracts. The rubric looks for fee and lookalike language, so it under-calls those contracts as high risk. The saved F1 on the models is not a field trial.
- DistilBERT was not trained.
- Screenshot OCR needs the Tesseract program, not only the Python package.
- There is no live Gmail inbox, no published browser extension, and no mobile app.

## 7. Email privacy

This matches `backend/services/mail.py` as built, not a future Gmail add-in.

- The message is never rendered in a browser preview.
- Remote images are not loaded.
- Attachments are not opened or executed. Only the filename and declared type are read.
- Only headers, a plain-text snippet, filenames, and declared types are used, plus URLs copied from the raw source.
- If headers cannot be parsed, sender points stay at 0 and the reason is "Sender check was unavailable."
- Demo mail is sandbox fixtures in `demos/*.eml`. Do not use a personal inbox.
- If a Gmail integration is added later, request `gmail.metadata` or `gmail.readonly` only, never send or modify scopes.

The paste-email API is a local demo of those rules. It is not a published inbox extension.

## 8. Slide outline

1. Students get internship scams by chat, screenshot, link, and email.
2. InternGuard returns one 0–100 score and the reasons, not only "scam."
3. Four channels share one rubric.
4. Dataset: 348 rows, version sha256:e08a9a505a4b, suspicious now 20.
5. Models vs rubric table. Models look strong on templates; the product is the rubric.
6. Demo: legitimate 0 low.
7. Demo: obvious scam 53 high (email 75).
8. Demo: polite joining fee plus `.tk` link, 41 medium.
9. Privacy: no render, no remote images, attachments not opened.
10. Limits: company-list gaps, WHOIS timeouts, Tesseract, no DistilBERT.

## 9. Live-demo script

1. Start the API on port 8000 and the frontend on http://localhost:5173.
2. Confirm History is empty or note the count.
3. Paste `demos/legitimate.txt`. Score 0, low, no flags.
4. Paste `demos/obvious_scam.txt`. Score 53, high, fee and lookalike link.
5. Paste `demos/subtle.txt`. Score 41, medium, joining fee and TCS requires verification.
6. Open History. All three checks are listed. Refresh the page. They remain.
7. Optional: Analyze email using `demos/obvious_scam.eml`. Score 75, high, including `pdf.exe`.
8. Optional: upload a screenshot of the subtle message if Tesseract is installed.
9. Stop the API, click Analyze, show the error, confirm History is unchanged.
