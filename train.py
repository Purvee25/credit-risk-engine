"""
Train and compare models for the Credit Risk Decision Engine.

Two feature sets:
  - traditional:  credit_score, income, existing_debt, loan_amount
  - alternative:  traditional + payment_consistency_pct,
                  income_volatility_score, debt_trend  ("Traditional + Alternative")

Three models each: Logistic Regression, Random Forest, XGBoost.

Class imbalance is handled with class weighting (class_weight / scale_pos_weight)
rather than SMOTE -- simpler, keeps feature distributions honest, and generally
better-calibrated on mixed-scale tabular financial data.

Evaluation emphasizes precision / recall / F1 / AUC-PR (average precision) --
the metrics that matter for a rare positive class -- not accuracy.

Artifacts saved to models/:
  - <model>_<featureset>.joblib   (fitted pipeline)
  - metrics.csv                   (full comparison table)
  - feature_sets.json             (column lists per set)
  - best_models.json              (best model per feature set, by AUC-PR)
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data", "applicants.csv")
MODELS_DIR = os.path.join(HERE, "models")

TARGET = "default"
TRADITIONAL = ["credit_score", "income", "existing_debt", "loan_amount"]
ALTERNATIVE_EXTRA = ["payment_consistency_pct", "income_volatility_score", "debt_trend"]

FEATURE_SETS = {
    "traditional": TRADITIONAL,
    "alternative": TRADITIONAL + ALTERNATIVE_EXTRA,
}


def build_models(y_train):
    """Return dict of name -> unfitted estimator, with imbalance handling."""
    neg, pos = np.bincount(y_train)
    scale_pos_weight = neg / pos
    return {
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=2000, class_weight="balanced", C=1.0)),
        ]),
        "Random Forest": RandomForestClassifier(
            n_estimators=300, max_depth=8, min_samples_leaf=20,
            class_weight="balanced", random_state=42, n_jobs=-1),
        "XGBoost": XGBClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
            random_state=42, n_jobs=-1),
    }


def evaluate(model, X_test, y_test, threshold=0.5):
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    return {
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "f1": f1_score(y_test, pred, zero_division=0),
        "auc_pr": average_precision_score(y_test, proba),
        "roc_auc": roc_auc_score(y_test, proba),
    }


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    df = pd.read_csv(DATA)
    y = df[TARGET].values

    # One shared split so both feature sets are compared on the same rows.
    idx_train, idx_test = train_test_split(
        np.arange(len(df)), test_size=0.25, stratify=y, random_state=42)

    rows = []
    best = {}
    for set_name, cols in FEATURE_SETS.items():
        X = df[cols]
        X_train, X_test = X.iloc[idx_train], X.iloc[idx_test]
        y_train, y_test = y[idx_train], y[idx_test]

        models = build_models(y_train)
        best_auc_pr, best_name = -1.0, None
        for model_name, est in models.items():
            est.fit(X_train, y_train)
            metrics = evaluate(est, X_test, y_test)
            rows.append({"feature_set": set_name, "model": model_name, **metrics})

            fname = f"{model_name.replace(' ', '_').lower()}_{set_name}.joblib"
            joblib.dump(est, os.path.join(MODELS_DIR, fname))

            if metrics["auc_pr"] > best_auc_pr:
                best_auc_pr, best_name = metrics["auc_pr"], model_name

        best[set_name] = {"model": best_name, "auc_pr": round(best_auc_pr, 4)}

    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(os.path.join(MODELS_DIR, "metrics.csv"), index=False)
    with open(os.path.join(MODELS_DIR, "feature_sets.json"), "w") as f:
        json.dump(FEATURE_SETS, f, indent=2)
    with open(os.path.join(MODELS_DIR, "best_models.json"), "w") as f:
        json.dump(best, f, indent=2)

    # Save the test-set indices so the app can reuse an honest holdout if needed.
    np.save(os.path.join(MODELS_DIR, "test_idx.npy"), idx_test)

    pd.set_option("display.width", 120)
    print("=== Model comparison (test set, threshold=0.5) ===\n")
    print(metrics_df.round(4).to_string(index=False))
    print("\n=== Best model per feature set (by AUC-PR) ===")
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    main()
