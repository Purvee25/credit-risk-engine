"""Unit tests for scoring utilities and the ML thesis guard."""
import numpy as np
import pandas as pd

import utils


def _df(n=5):
    return pd.read_csv(f"{utils.HERE}/data/applicants.csv").head(n)


def test_validate_columns_detects_missing():
    df = _df().drop(columns=["debt_trend"])
    missing, n_bad = utils.validate_columns(df, utils.ALL_FEATURES)
    assert "debt_trend" in missing


def test_validate_columns_all_present():
    missing, n_bad = utils.validate_columns(_df(), utils.ALL_FEATURES)
    assert missing == [] and n_bad == 0


def test_score_returns_percentages():
    model, _, cols = utils.load_best_model("alternative")
    out = utils.score(_df(20), model, cols)
    assert out.shape == (20,)
    assert out.min() >= 0 and out.max() <= 100


def test_loaders_shapes():
    assert set(utils.load_feature_sets()) == {"traditional", "alternative"}
    assert len(utils.load_metrics()) == 6
    assert set(utils.load_best_models()) == {"traditional", "alternative"}


def test_build_explainer_additivity():
    df = pd.read_csv(f"{utils.HERE}/data/applicants.csv")
    model, _, cols = utils.load_best_model("alternative")
    explain = utils.build_explainer(model, df.sample(150, random_state=1), cols)
    vals, base = explain(df.head(1))
    pred = model.predict_proba(df.head(1)[cols])[0, 1]
    assert abs((base + vals[0].sum()) - pred) < 1e-6


def test_risk_category_bands():
    assert utils.risk_category(0.05) == "Low"
    assert utils.risk_category(0.14) == "Low"
    assert utils.risk_category(0.15) == "Medium"
    assert utils.risk_category(0.39) == "Medium"
    assert utils.risk_category(0.40) == "High"
    assert utils.risk_category(0.99) == "High"


def test_behavioral_beats_traditional_auc_pr():
    """Regression guard on the core thesis: behavioral features improve AUC-PR."""
    best = utils.load_best_models()
    assert best["alternative"]["auc_pr"] > best["traditional"]["auc_pr"]
