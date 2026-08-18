"""
Shared helpers for the Credit Risk Decision Engine: loading artifacts, scoring,
risk categorization, and SHAP explanations. Imported by both the SHAP smoke
test and the Streamlit app so scoring logic lives in exactly one place.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")

TARGET = "default"
TRADITIONAL = ["credit_score", "income", "existing_debt", "loan_amount"]
ALTERNATIVE_EXTRA = ["payment_consistency_pct", "income_volatility_score", "debt_trend"]
ALL_FEATURES = TRADITIONAL + ALTERNATIVE_EXTRA

# Human-friendly labels for charts/captions.
FEATURE_LABELS = {
    "credit_score": "Credit score",
    "income": "Annual income",
    "existing_debt": "Existing debt",
    "loan_amount": "Loan amount",
    "payment_consistency_pct": "Payment consistency %",
    "income_volatility_score": "Income volatility",
    "debt_trend": "Debt trend",
}


def load_feature_sets():
    with open(os.path.join(MODELS_DIR, "feature_sets.json")) as f:
        return json.load(f)


def load_best_models():
    with open(os.path.join(MODELS_DIR, "best_models.json")) as f:
        return json.load(f)


def load_metrics():
    return pd.read_csv(os.path.join(MODELS_DIR, "metrics.csv"))


def _model_path(model_name, feature_set):
    fname = f"{model_name.replace(' ', '_').lower()}_{feature_set}.joblib"
    return os.path.join(MODELS_DIR, fname)


def load_model(model_name, feature_set):
    return joblib.load(_model_path(model_name, feature_set))


def load_best_model(feature_set):
    """Return (estimator, model_name, feature_columns) for the best model."""
    best = load_best_models()[feature_set]
    cols = load_feature_sets()[feature_set]
    return load_model(best["model"], feature_set), best["model"], cols


def risk_category(prob):
    """Map a default probability to Low / Medium / High."""
    if prob < 0.15:
        return "Low"
    if prob < 0.40:
        return "Medium"
    return "High"


def score(df, model, cols):
    """Return default-probability array (percent 0-100) for df using model."""
    proba = model.predict_proba(df[cols])[:, 1]
    return proba * 100.0


def validate_columns(df, required):
    """Return (missing_cols, rows_with_missing_values)."""
    missing = [c for c in required if c not in df.columns]
    present = [c for c in required if c in df.columns]
    n_missing_vals = int(df[present].isna().any(axis=1).sum()) if present else 0
    return missing, n_missing_vals


# ---- SHAP -----------------------------------------------------------------
def build_explainer(model, background_df, cols):
    """
    Build a SHAP explainer appropriate to the model type.

    LinearExplainer for linear pipelines (fast, exact), TreeExplainer for tree
    ensembles. Falls back to the model-agnostic Explainer otherwise. Returns a
    callable(X_df) -> (shap_values_2d, base_value).
    """
    import shap

    bg = background_df[cols]

    is_tree = model.__class__.__name__ in {
        "RandomForestClassifier", "XGBClassifier"}

    if is_tree:
        explainer = shap.TreeExplainer(model)

        def explain(X_df):
            vals = explainer.shap_values(X_df[cols])
            # Binary classifiers may return a list [neg, pos]; take positive.
            if isinstance(vals, list):
                vals = vals[1]
            vals = np.asarray(vals)
            if vals.ndim == 3:  # (n, features, classes)
                vals = vals[:, :, 1]
            base = explainer.expected_value
            base = base[1] if isinstance(base, (list, np.ndarray)) and np.ndim(base) else base
            return vals, float(np.ravel(base)[0])

        return explain

    # Model-agnostic path (used for the linear pipeline too). Explains in
    # PROBABILITY space, so SHAP contributions read directly as "+/- risk %".
    bg_sample = bg.sample(min(100, len(bg)), random_state=0)

    def f(X):
        return model.predict_proba(pd.DataFrame(X, columns=cols))[:, 1]

    explainer = shap.Explainer(f, bg_sample)

    def explain(X_df):
        exp = explainer(X_df[cols])
        return np.asarray(exp.values), float(np.asarray(exp.base_values).ravel()[0])

    return explain
