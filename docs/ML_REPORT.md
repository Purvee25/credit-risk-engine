# ML Report — Phase 3

Compares the **previous** production model (`train.py`, fixed hyperparameters,
0.5 threshold, no calibration) against the **improved** pipeline (`train_cv.py`:
Stratified 5-fold CV + lightweight grid tuning, held-out test set, validation
split for threshold selection, isotonic calibration, F1-optimized threshold).

All numbers are **actual results** on the same 25% stratified test set (seed=42).
Improved artifacts are staged in `models/v2/` and `reports/` — production
(`models/`) is unchanged.

## Best model per feature set (test set)

| Feature set | Metric | Previous | Improved | Δ |
|---|---|---|---|---|
| Traditional (LR) | AUC-PR | 0.520 | 0.510 | −0.010 |
| Traditional (LR) | ROC-AUC | 0.777 | 0.775 | −0.002 |
| **Trad + Behavioral (LR)** | **AUC-PR** | **0.668** | **0.660** | **−0.008** |
| Trad + Behavioral (LR) | ROC-AUC | 0.884 | 0.882 | −0.002 |
| Trad + Behavioral (LR) | F1 | 0.635 | 0.627 | −0.008 |
| Trad + Behavioral (LR) | Recall | 0.823 | 0.823 | 0.000 |
| Trad + Behavioral (LR) | Brier ↓ | not measured | **0.111** | new |
| Trad + Behavioral (LR) | Threshold | 0.50 (arbitrary) | **0.228** (max-F1) | new |

Full candidate grid: `reports/metrics_v2.csv`.

## Verdict — is the improved model better?

**Discrimination: not significantly better.** AUC-PR moves by ≤0.01 in both
feature sets — well inside cross-validation noise (CV AUC-PR spread across folds
is larger than this gap). The original Logistic Regression was already near the
achievable ceiling for this (largely additive-in-logit) data, so tuning `C` and
calibrating do not add ranking power.

**Calibration & rigor: genuinely better.**
- **Calibrated probabilities** — isotonic calibration gives a measured Brier
  score (0.111); the risk percentages the UI shows are now trustworthy
  probabilities rather than uncalibrated scores (see `calibration_curve.png`).
- **Principled operating threshold** — 0.228 (max-F1 on validation) replaces the
  arbitrary 0.5, matching how the app's approval slider is actually used.
- **Defensible methodology** — Stratified K-Fold tuning + an untouched test set
  remove the implicit selection-on-test bias in the original single split.

**Practical conclusion:** adopt the improved pipeline for its **calibration,
threshold, and methodological rigor** (valuable for production trust and a
research write-up), **not** for a headline accuracy gain — there isn't one, and
claiming one would be dishonest.

## Figures (`reports/figures/`)
- `roc_curve.png` · `pr_curve.png` — discrimination
- `calibration_curve.png` — reliability of predicted probabilities
- `confusion_matrix.png` — errors at the optimized threshold
- `feature_importance.png` — permutation importance (AUC-PR drop)
- `shap_summary.png` — per-feature SHAP contributions (probability space)

## Reproduce
```bash
python3 train_cv.py     # -> models/v2/, reports/metrics_v2.csv, best_models_v2.json
python3 evaluate.py     # -> reports/figures/*.png
```
