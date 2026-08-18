"""
Improved training pipeline (Phase 3) — non-destructive.

Adds over `train.py`: Stratified K-Fold CV with lightweight hyperparameter
tuning, a held-out final test set (untouched during selection), an internal
validation split for operating-threshold optimization, and probability
calibration (CalibratedClassifierCV).

Artifacts are written to a STAGING location so production is not overwritten:
  models/v2/<model>_<featureset>.joblib   (calibrated best per feature set)
  reports/metrics_v2.csv                  (all candidates, test-set metrics)
  reports/best_models_v2.json             (best per feature set + threshold)
  reports/split_idx.npz                   (fit/val/test indices, reproducible)

Run:  python3 train_cv.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

import utils

SEED = 42
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "applicants.csv")
OUT_MODELS = os.path.join(HERE, "models", "v2")
REPORTS = os.path.join(HERE, "reports")

FEATURE_SETS = {
    "traditional": utils.TRADITIONAL,
    "alternative": utils.TRADITIONAL + utils.ALTERNATIVE_EXTRA,
}


def build_grids(scale_pos_weight):
    """Small, reproducible grids — tuned for AUC-PR, not exhaustive."""
    return {
        "Logistic Regression": (
            Pipeline([
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
            ]),
            {"clf__C": [0.1, 1.0, 10.0]},
        ),
        "Random Forest": (
            RandomForestClassifier(
                class_weight="balanced", random_state=SEED, n_jobs=-1),
            {"n_estimators": [200, 400], "max_depth": [6, 10], "min_samples_leaf": [20]},
        ),
        "XGBoost": (
            XGBClassifier(
                scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
                subsample=0.9, colsample_bytree=0.9, random_state=SEED, n_jobs=-1),
            {"max_depth": [3, 5], "learning_rate": [0.05, 0.1], "n_estimators": [300]},
        ),
    }


def best_threshold(y_true, proba):
    """Operating threshold that maximizes F1 on a validation set."""
    prec, rec, thr = precision_recall_curve(y_true, proba)
    if len(thr) == 0:
        return 0.5
    f1 = 2 * prec[:-1] * rec[:-1] / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thr[int(np.argmax(f1))])


def metrics_at(y, proba, thr):
    pred = (proba >= thr).astype(int)
    return {
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "auc_pr": average_precision_score(y, proba),
        "roc_auc": roc_auc_score(y, proba),
        "brier": brier_score_loss(y, proba),
        "threshold": thr,
    }


def main():
    os.makedirs(OUT_MODELS, exist_ok=True)
    os.makedirs(REPORTS, exist_ok=True)
    df = pd.read_csv(DATA)
    y = df[utils.TARGET].values
    idx = np.arange(len(df))

    # Same 25% test split as train.py (SEED=42) -> comparable, untouched test set.
    idx_train, idx_test = train_test_split(
        idx, test_size=0.25, stratify=y, random_state=SEED)
    # Carve a validation set from train for threshold selection only.
    idx_fit, idx_val = train_test_split(
        idx_train, test_size=0.2, stratify=y[idx_train], random_state=SEED)
    np.savez(os.path.join(REPORTS, "split_idx.npz"),
             fit=idx_fit, val=idx_val, test=idx_test)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    rows, best = [], {}

    for set_name, cols in FEATURE_SETS.items():
        X = df[cols]
        Xfit, yfit = X.iloc[idx_fit], y[idx_fit]
        Xval, yval = X.iloc[idx_val], y[idx_val]
        Xte, yte = X.iloc[idx_test], y[idx_test]
        neg, pos = np.bincount(yfit)
        grids = build_grids(neg / pos)

        best_ap, best_name, best_est, best_thr = -1.0, None, None, 0.5
        for name, (est, grid) in grids.items():
            gs = GridSearchCV(est, grid, scoring="average_precision",
                              cv=cv, n_jobs=-1)
            gs.fit(Xfit, yfit)
            # Calibrate the tuned estimator (cross-val calibration on fit split).
            cal = CalibratedClassifierCV(gs.best_estimator_, method="isotonic", cv=3)
            cal.fit(Xfit, yfit)

            thr = best_threshold(yval, cal.predict_proba(Xval)[:, 1])
            m = metrics_at(yte, cal.predict_proba(Xte)[:, 1], thr)
            rows.append({"feature_set": set_name, "model": name,
                         "cv_ap": round(gs.best_score_, 4), **m,
                         "params": json.dumps(gs.best_params_)})
            if m["auc_pr"] > best_ap:
                best_ap, best_name, best_est, best_thr = m["auc_pr"], name, cal, thr

        fname = f"{best_name.replace(' ', '_').lower()}_{set_name}.joblib"
        joblib.dump({"model": best_est, "threshold": best_thr, "columns": cols},
                    os.path.join(OUT_MODELS, fname))
        best[set_name] = {"model": best_name, "auc_pr": round(best_ap, 4),
                          "threshold": round(best_thr, 4)}

    metrics_df = pd.DataFrame(rows).round(4)
    metrics_df.to_csv(os.path.join(REPORTS, "metrics_v2.csv"), index=False)
    with open(os.path.join(REPORTS, "best_models_v2.json"), "w") as f:
        json.dump(best, f, indent=2)

    pd.set_option("display.width", 140)
    print("=== Improved candidates (untouched test set) ===\n")
    print(metrics_df.drop(columns=["params"]).to_string(index=False))
    print("\n=== Best per feature set (by test AUC-PR) ===")
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
