# User Guide

A walkthrough of the app for a non-technical reviewer (loan officer / analyst).

> ⚠️ Prototype on synthetic data — **not** for real lending decisions.

## The website
- **Landing** — the pitch and a live 3D "risk field" (each point is an applicant).
- **Product / How it works / Technology / Results** — background pages.
- **Launch app** → the interactive dashboard.

## The dashboard (`/app`)
Sign in with the demo login (no real credentials). Six views in the sidebar:

| View | What you do |
|------|-------------|
| **Overview** | See the 3D field: height = default risk, colour = Low/Medium/High. |
| **Portfolio** | Drag the **approval threshold** — approval rate, average risk, and estimated default update live. Upload your own CSV to score a real batch. |
| **Applicant** | Pick one applicant; see their risk score and a **SHAP** bar chart of what raised/lowered it. |
| **Trad vs Behavioral** | Compare the traditional vs behavioral score for one applicant — watch **decision flips** (traditional rejects, behavioral approves). |
| **Fairness** | Approval rate by income bracket, with an access-gap verdict. |
| **Performance** | Model metrics table; behavioral vs traditional. |

## Uploading applicants
On **Portfolio**: download the **template**, fill in your rows, **Upload CSV**.
Required columns: credit_score, income, existing_debt, loan_amount,
payment_consistency_pct, income_volatility_score, debt_trend.
The field re-scores live through the backend. **Reset** returns to the demo batch.

## Reading a risk score
- **Low** (<15%), **Medium** (15–40%), **High** (≥40%).
- The SHAP chart: green bars lower risk, red bars raise it; they sum from a
  baseline to the final score.
