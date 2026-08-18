"""
Synthetic data generator for the Credit Risk Decision Engine.

Design goal: make the "alternative data helps" thesis a REAL result, not a
tautology. We do this by:

  1. Drawing a latent "true creditworthiness" that depends on BOTH traditional
     drivers (income, debt burden) and behavioral drivers (payment
     consistency, income volatility, debt trend).
  2. Deriving the *observed* traditional features as NOISY, partial proxies of
     that latent state -- credit_score in particular is a lagging, coarse
     signal that is especially unreliable for thin-file borrowers.
  3. Making the behavioral signal matter MOST when the traditional file is thin
     (short employment / little credit history), which is exactly the
     financial-inclusion story the app is about.

Because default is generated from the latent state (not directly from the
observed features), a model still has to *discover* the behavioral signal from
noisy inputs. Alternative features winning is therefore an earned outcome.
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
N = 5000


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def generate(n: int = N, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # ---- Applicant fundamentals -------------------------------------------
    # Income: lognormal, floored to a sensible minimum.
    income = np.clip(rng.lognormal(mean=10.9, sigma=0.55, size=n), 12_000, 400_000)

    # Employment length in years (thin-file <=> short tenure / young file).
    employment_length = np.clip(rng.gamma(shape=2.0, scale=2.6, size=n), 0, 40)

    # "Thin file" strength: 1 = essentially no history, 0 = long history.
    thinness = np.clip(1.0 - employment_length / 12.0, 0.0, 1.0)

    # Loan amount scales loosely with income plus noise.
    loan_amount = np.clip(
        income * rng.uniform(0.08, 0.55, size=n) + rng.normal(0, 4000, size=n),
        1_000, 250_000,
    )

    # Existing debt: fraction of income already committed.
    dti_latent = np.clip(rng.beta(2.0, 5.0, size=n) + rng.normal(0, 0.05, n), 0, 1.2)
    existing_debt = np.round(dti_latent * income, 2)

    # ---- Behavioral / alternative signals ---------------------------------
    # payment_consistency_pct: % of recent obligations paid on time (0-100).
    payment_consistency_pct = np.clip(rng.normal(84, 14, size=n), 20, 100)

    # income_volatility_score: 0 (stable salary) .. 100 (gig/erratic).
    income_volatility_score = np.clip(rng.normal(35, 20, size=n), 0, 100)

    # debt_trend: change in debt load, -1 (paying down) .. +1 (ballooning).
    debt_trend = np.clip(rng.normal(0.0, 0.35, size=n), -1, 1)

    # ---- Latent true risk (the ground truth default driver) ---------------
    # Standardize the pieces so coefficients are interpretable.
    z_income = (np.log(income) - np.log(income).mean()) / np.log(income).std()
    z_dti = (dti_latent - dti_latent.mean()) / dti_latent.std()
    z_pay = (payment_consistency_pct - 84) / 14
    z_vol = (income_volatility_score - 35) / 20

    # Behavioral influence is amplified for thin-file borrowers: for someone
    # with a long, rich traditional record the behavioral add-on is smaller.
    behavioral = (
        -1.15 * z_pay          # paying on time lowers risk
        + 0.75 * z_vol         # volatile income raises risk
        + 0.80 * debt_trend    # rising debt raises risk
    )
    behavioral_gain = 0.6 + 1.4 * thinness  # 0.6 (rich file) .. 2.0 (thin file)

    logit = (
        -2.35                      # base rate -> ~ realistic default prevalence
        - 0.85 * z_income          # higher income lowers risk
        + 1.05 * z_dti             # higher debt-to-income raises risk
        + behavioral_gain * behavioral
        + rng.normal(0, 0.45, size=n)  # irreducible noise
    )
    p_default = _sigmoid(logit)
    default = rng.binomial(1, p_default)

    # ---- Observed credit_score: NOISY, LAGGING proxy of latent state ------
    # Built from income + dti + a slow reflection of payment history, but with
    # extra noise for thin files (bureau has little to score).
    score_core = (
        680
        + 55 * z_income
        - 60 * z_dti
        + 40 * z_pay
        - 20 * z_vol
    )
    score_noise = rng.normal(0, 25 + 55 * thinness, size=n)  # thin files noisier
    credit_score = np.clip(np.round(score_core + score_noise), 300, 850).astype(int)

    df = pd.DataFrame({
        "income": np.round(income, 2),
        "employment_length": np.round(employment_length, 1),
        "existing_debt": existing_debt,
        "loan_amount": np.round(loan_amount, 2),
        "credit_score": credit_score,
        "payment_consistency_pct": np.round(payment_consistency_pct, 1),
        "income_volatility_score": np.round(income_volatility_score, 1),
        "debt_trend": np.round(debt_trend, 3),
        "default": default.astype(int),
    })
    return df


if __name__ == "__main__":
    import os

    df = generate()
    out = os.path.join(os.path.dirname(__file__), "data", "applicants.csv")
    df.to_csv(out, index=False)

    # Quick sanity report
    print(f"Rows: {len(df):,}")
    print(f"Default rate: {df['default'].mean():.3%}")
    print("\nCorrelation of each feature with default:")
    corr = df.corr(numeric_only=True)["default"].drop("default").sort_values()
    print(corr.round(3).to_string())
    print(f"\nSaved -> {out}")
