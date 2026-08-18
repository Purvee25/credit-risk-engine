"""
Evaluation plots (Phase 3) for the improved calibrated models — non-destructive.

Loads the staged models from models/v2/ and the reproducible split, then writes
diagnostic figures to reports/figures/ for the best alternative-feature model:
  ROC curve, PR curve, calibration curve, confusion matrix, feature importance,
  SHAP summary.

Run (after train_cv.py):  python3 evaluate.py
"""

import json
import os

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    PrecisionRecallDisplay,
    RocCurveDisplay,
)
from sklearn.calibration import CalibrationDisplay

import utils

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, "reports")
FIGS = os.path.join(REPORTS, "figures")


def _load(feature_set):
    best = json.load(open(os.path.join(REPORTS, "best_models_v2.json")))
    name = best[feature_set]["model"].replace(" ", "_").lower()
    bundle = joblib.load(os.path.join(HERE, "models", "v2", f"{name}_{feature_set}.joblib"))
    return bundle, best[feature_set]


def main():
    os.makedirs(FIGS, exist_ok=True)
    df = pd.read_csv(os.path.join(HERE, "data", "applicants.csv"))
    y = df[utils.TARGET].values
    split = np.load(os.path.join(REPORTS, "split_idx.npz"))
    idx_test = split["test"]

    bundle, meta = _load("alternative")
    model, thr, cols = bundle["model"], bundle["threshold"], bundle["columns"]
    Xte, yte = df[cols].iloc[idx_test], y[idx_test]
    proba = model.predict_proba(Xte)[:, 1]
    pred = (proba >= thr).astype(int)

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(os.path.join(FIGS, name), dpi=120, bbox_inches="tight")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    RocCurveDisplay.from_predictions(yte, proba, ax=ax)
    ax.set_title("ROC — Trad+Behavioral (calibrated)")
    save(fig, "roc_curve.png")

    fig, ax = plt.subplots(figsize=(5, 4))
    PrecisionRecallDisplay.from_predictions(yte, proba, ax=ax)
    ax.set_title("Precision-Recall — Trad+Behavioral")
    save(fig, "pr_curve.png")

    fig, ax = plt.subplots(figsize=(5, 4))
    CalibrationDisplay.from_predictions(yte, proba, n_bins=10, ax=ax)
    ax.set_title("Calibration — Trad+Behavioral")
    save(fig, "calibration_curve.png")

    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay.from_predictions(
        yte, pred, display_labels=["No default", "Default"], ax=ax, colorbar=False)
    ax.set_title(f"Confusion matrix (threshold={thr:.2f})")
    save(fig, "confusion_matrix.png")

    # Permutation feature importance (model-agnostic, works on calibrated model).
    from sklearn.inspection import permutation_importance
    imp = permutation_importance(
        model, Xte, yte, scoring="average_precision",
        n_repeats=10, random_state=42, n_jobs=-1)
    order = np.argsort(imp.importances_mean)
    labels = [utils.FEATURE_LABELS[c] for c in cols]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(np.array(labels)[order], imp.importances_mean[order], color="#2f6690")
    ax.set_title("Permutation feature importance (AUC-PR drop)")
    save(fig, "feature_importance.png")

    # SHAP summary via the shared explainer (probability space) — kept compatible.
    try:
        import shap
        explain = utils.build_explainer(model, df[cols].sample(200, random_state=1), cols)
        sample = Xte.sample(min(150, len(Xte)), random_state=0)
        shap_vals = explain(sample)[0]
        shap.summary_plot(
            shap_vals, sample, feature_names=labels, show=False, plot_size=(6, 4))
        plt.title("SHAP summary — Trad+Behavioral")
        plt.savefig(os.path.join(FIGS, "shap_summary.png"), dpi=120, bbox_inches="tight")
        plt.close()
        shap_ok = True
    except Exception as e:  # SHAP is best-effort; don't fail the whole run
        shap_ok = False
        print(f"[warn] SHAP summary skipped: {e}")

    print(f"Figures written to {FIGS}")
    print("  roc_curve, pr_curve, calibration_curve, confusion_matrix, "
          f"feature_importance{', shap_summary' if shap_ok else ''}")


if __name__ == "__main__":
    main()
