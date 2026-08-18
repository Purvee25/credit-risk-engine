"""
Export precomputed scores + SHAP for the 3D web front-end.

Runs the trained models over a demo batch and writes a single static JSON the
React/Three.js site loads -- no backend required.

Output: web/public/data.json
  {
    "meta":       {generated, n_applicants, base_risk, thresholds...},
    "metrics":    [ {feature_set, model, precision, recall, f1, auc_pr, roc_auc} ],
    "best":       {traditional:{...}, alternative:{...}},
    "features":   [ {key, label} ],           # alternative feature order
    "applicants": [
        {id, income, credit_score, employment_length, existing_debt,
         loan_amount, payment_consistency_pct, income_volatility_score,
         debt_trend, risk, risk_traditional, category,
         shap: {feature_key: contribution_pct, ...}}
    ]
  }
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import utils

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "web", "public")
N_DEMO = 250


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(os.path.join(HERE, "data", "applicants.csv"))

    batch = (df.drop(columns=[utils.TARGET])
             .sample(N_DEMO, random_state=7).reset_index(drop=True))
    batch.insert(0, "id", [f"APP-{i:04d}" for i in range(1, len(batch) + 1)])

    alt_model, _, alt_cols = utils.load_best_model("alternative")
    trad_model, _, trad_cols = utils.load_best_model("traditional")

    risk = utils.score(batch, alt_model, alt_cols)
    risk_trad = utils.score(batch, trad_model, trad_cols)

    explain = utils.build_explainer(alt_model, df.sample(200, random_state=1), alt_cols)
    shap_vals, base = explain(batch)  # (N, n_features) in probability space

    applicants = []
    for i, row in batch.iterrows():
        rec = {
            "id": row["id"],
            "income": float(row["income"]),
            "credit_score": int(row["credit_score"]),
            "employment_length": float(row["employment_length"]),
            "existing_debt": float(row["existing_debt"]),
            "loan_amount": float(row["loan_amount"]),
            "payment_consistency_pct": float(row["payment_consistency_pct"]),
            "income_volatility_score": float(row["income_volatility_score"]),
            "debt_trend": float(row["debt_trend"]),
            "risk": round(float(risk[i]), 2),
            "risk_traditional": round(float(risk_trad[i]), 2),
            "category": utils.risk_category(risk[i] / 100),
            "shap": {c: round(float(shap_vals[i, j] * 100), 3)
                     for j, c in enumerate(alt_cols)},
        }
        applicants.append(rec)

    metrics = utils.load_metrics().round(4).to_dict(orient="records")
    best = utils.load_best_models()

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "n_applicants": len(applicants),
            "base_risk": round(float(base) * 100, 2),
            "default_threshold": 25,
            "income_min": float(batch["income"].min()),
            "income_max": float(batch["income"].max()),
        },
        "metrics": metrics,
        "best": best,
        "features": [{"key": c, "label": utils.FEATURE_LABELS[c]} for c in alt_cols],
        "applicants": applicants,
    }

    out = os.path.join(OUT_DIR, "data.json")
    with open(out, "w") as f:
        json.dump(payload, f)
    kb = os.path.getsize(out) / 1024
    print(f"Wrote {len(applicants)} applicants -> {out} ({kb:.0f} KB)")
    print(f"Base risk: {payload['meta']['base_risk']}% | "
          f"risk range: {min(a['risk'] for a in applicants):.1f}"
          f"–{max(a['risk'] for a in applicants):.1f}%")
    cats = pd.Series([a["category"] for a in applicants]).value_counts().to_dict()
    print("Category mix:", cats)


if __name__ == "__main__":
    main()
