# FAQ

**Is this usable for real lending?**
No. It's a prototype on **synthetic data**, not validated for production lending.
Every surface carries that disclaimer.

**Why synthetic data instead of a real dataset?**
Real credit datasets rarely include the behavioral signals this project is
about, and open ones raise licensing/PII issues. The generator is designed so
the "behavioral data helps" result is *earned, not leaked* — see
[MLPipeline.md](MLPipeline.md).

**Why AUC-PR instead of accuracy?**
Defaults are the rare class (~22%). Accuracy is misleading (a "reject everyone"
model looks ~78% accurate). AUC-PR measures how well the model separates
defaulters from non-defaulters.

**How much do behavioral features actually help?**
Best-model **AUC-PR 0.52 → 0.67** on the held-out test set. The magnitude is
illustrative (synthetic), not a market estimate.

**Are the risk percentages calibrated probabilities?**
The production model reports ranked scores. The improved `train_cv.py` pipeline
adds isotonic **calibration** (Brier 0.111) — see [ML_REPORT.md](ML_REPORT.md).

**Does the site need the backend?**
No. The SPA falls back to a bundled `data.json` snapshot; live scoring / CSV
upload require the FastAPI backend.

**Is the login real authentication?**
No — it's a demo gate stored in `localStorage`. The API supports an optional
`X-API-Key` for real access control.

**What's the fairness check?**
Approval rate across income brackets — an **access lens**, not a legal bias
verdict (income is not a protected attribute).

**Can I score my own applicants?**
Yes — Portfolio → download template → Upload CSV (backend required).
