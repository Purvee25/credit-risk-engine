"""
Credit Risk Decision Engine -- Streamlit app.

A prototype credit-risk scoring tool that predicts loan-default risk using both
traditional and alternative (behavioral) features, to explore fairer credit
access for thin-file borrowers.

Run:  streamlit run app.py
"""

import io

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import utils

# --------------------------------------------------------------------------- #
# Page config + banking-appropriate styling
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Credit Risk Decision Engine",
    page_icon="🏦",
    layout="wide",
)

NAVY = "#1f3a5f"
STEEL = "#2f6690"
SLATE = "#54667a"
GREEN = "#2e7d5b"
AMBER = "#c9820a"
RED = "#b23a48"

st.markdown(f"""
<style>
    .stApp {{ background-color: #f5f7fa; }}
    h1, h2, h3 {{ color: {NAVY}; }}
    section[data-testid="stSidebar"] {{ background-color: {NAVY}; }}
    section[data-testid="stSidebar"] * {{ color: #e8eef5; }}
    div[data-testid="stMetric"] {{
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
        padding: 14px 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .caption-box {{
        color: {SLATE}; font-size: 0.86rem; font-style: italic;
        margin-top: -6px; margin-bottom: 10px;
    }}
    .disclaimer {{
        background: #fff5f5; border-left: 5px solid {RED}; color: #7a2530;
        padding: 14px 18px; border-radius: 6px; font-weight: 500;
    }}
    .step-card {{
        background:#ffffff; border:1px solid #e2e8f0; border-radius:10px;
        padding:16px; text-align:center; height:100%;
    }}
    .step-num {{ color:{STEEL}; font-weight:700; font-size:0.8rem; }}
</style>
""", unsafe_allow_html=True)


def caption(text):
    st.markdown(f'<div class="caption-box">{text}</div>', unsafe_allow_html=True)


CAT_COLORS = {"Low": GREEN, "Medium": AMBER, "High": RED}


# --------------------------------------------------------------------------- #
# Cached resources
# --------------------------------------------------------------------------- #
@st.cache_resource
def load_artifacts():
    trad_model, trad_name, trad_cols = utils.load_best_model("traditional")
    alt_model, alt_name, alt_cols = utils.load_best_model("alternative")
    train_df = pd.read_csv(utils.MODELS_DIR.replace("models", "data") + "/applicants.csv")
    explain_alt = utils.build_explainer(alt_model, train_df.sample(200, random_state=1), alt_cols)
    return {
        "trad": (trad_model, trad_name, trad_cols),
        "alt": (alt_model, alt_name, alt_cols),
        "explain_alt": explain_alt,
        "background": train_df,
    }


@st.cache_data
def sample_template():
    df = pd.read_csv(utils.MODELS_DIR.replace("models", "data") + "/applicants.csv")
    tmpl = df.drop(columns=[utils.TARGET]).head(15).copy()
    tmpl.insert(0, "applicant_id", [f"APP-{i:04d}" for i in range(1, len(tmpl) + 1)])
    return tmpl


@st.cache_data
def default_batch():
    """A ready-to-use demo batch so every tab works without an upload."""
    df = pd.read_csv(utils.MODELS_DIR.replace("models", "data") + "/applicants.csv")
    batch = df.drop(columns=[utils.TARGET]).sample(300, random_state=7).reset_index(drop=True)
    batch.insert(0, "applicant_id", [f"APP-{i:04d}" for i in range(1, len(batch) + 1)])
    return batch


ART = load_artifacts()


# --------------------------------------------------------------------------- #
# Session state: the working batch shared across tabs
# --------------------------------------------------------------------------- #
if "batch" not in st.session_state:
    st.session_state.batch = None
if "batch_source" not in st.session_state:
    st.session_state.batch_source = None


def score_batch(df):
    """Attach risk scores (traditional + alternative) and categories."""
    out = df.copy()
    alt_model, _, alt_cols = ART["alt"]
    trad_model, _, trad_cols = ART["trad"]
    out["risk_pct"] = utils.score(out, alt_model, alt_cols).round(2)
    out["risk_pct_traditional"] = utils.score(out, trad_model, trad_cols).round(2)
    out["risk_category"] = [utils.risk_category(p / 100) for p in out["risk_pct"]]
    return out


def get_scored_batch():
    if st.session_state.batch is None:
        return None
    return score_batch(st.session_state.batch)


# --------------------------------------------------------------------------- #
# Sidebar navigation
# --------------------------------------------------------------------------- #
st.sidebar.title("🏦 Credit Risk\nDecision Engine")
st.sidebar.markdown("---")
TAB = st.sidebar.radio(
    "Navigate",
    ["Overview", "Batch Assessment", "Applicant Drill-Down",
     "Traditional vs Alternative", "Fairness Check", "Model Performance & Limitations"],
)
st.sidebar.markdown("---")
if st.session_state.batch is not None:
    st.sidebar.success(f"Batch loaded: {len(st.session_state.batch)} applicants "
                       f"({st.session_state.batch_source})")
else:
    st.sidebar.info("No batch loaded yet.\nGo to **Batch Assessment**.")
st.sidebar.caption("Prototype — not for production lending decisions.")


# --------------------------------------------------------------------------- #
# TAB 1 — Overview
# --------------------------------------------------------------------------- #
def tab_overview():
    st.title("Credit Risk Decision Engine")
    st.subheader("Predicting loan-default risk with traditional *and* behavioral data — "
                 "to widen fair credit access for thin-file borrowers.")

    st.markdown("""
    **The problem.** Tens of millions of creditworthy people are *thin-file* —
    they have little or no traditional credit history, so a conventional score
    either rejects them or can't rate them at all. Yet many of these applicants
    show strong **behavioral** signals of reliability: they pay bills on time,
    keep debt stable, and manage variable income responsibly. This tool tests
    whether adding those alternative signals produces fairer, more accurate
    lending decisions than a traditional score alone.
    """)

    st.markdown("### How this works")
    steps = [
        ("STEP 1", "📊 Data", "5,000 applicants with traditional and behavioral attributes."),
        ("STEP 2", "🧬 Feature Engineering", "Two feature sets: traditional vs. traditional + alternative."),
        ("STEP 3", "🤖 Model", "Logistic Regression, Random Forest & XGBoost, tuned for imbalance."),
        ("STEP 4", "🔍 Explainable Decision", "A risk score plus a SHAP breakdown of what drove it."),
    ]
    cols = st.columns(4)
    for col, (num, title, body) in zip(cols, steps):
        with col:
            st.markdown(
                f'<div class="step-card"><div class="step-num">{num}</div>'
                f'<h4 style="margin:6px 0">{title}</h4>'
                f'<div style="color:{SLATE};font-size:0.88rem">{body}</div></div>',
                unsafe_allow_html=True)

    st.markdown("")
    best_alt = utils.load_best_models()["alternative"]
    best_trad = utils.load_best_models()["traditional"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Applicants in dataset", "5,000")
    c2.metric("Best model (AUC-PR)", f'{best_alt["auc_pr"]:.2f}',
              delta=f'+{best_alt["auc_pr"] - best_trad["auc_pr"]:.2f} vs traditional')
    c3.metric("Feature sets compared", "2 × 3 models")
    caption("AUC-PR (area under the precision-recall curve) is the key accuracy "
            "measure here because defaults are rare; the delta shows how much the "
            "behavioral features improve on a traditional-only score.")


# --------------------------------------------------------------------------- #
# TAB 2 — Batch Assessment
# --------------------------------------------------------------------------- #
def tab_batch():
    st.title("Batch Assessment")
    st.write("Upload a CSV of loan applicants to score them all at once, or use the "
             "built-in demo batch to explore the tool.")

    left, right = st.columns([2, 1])
    with left:
        uploaded = st.file_uploader("Upload applicant CSV", type=["csv"])
    with right:
        st.download_button("⬇️ Download sample template",
                           sample_template().to_csv(index=False),
                           "applicant_template.csv", "text/csv")
        if st.button("Use demo batch (300 applicants)"):
            st.session_state.batch = default_batch()
            st.session_state.batch_source = "demo"
            st.rerun()

    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")
            return
        _, alt_cols = None, ART["alt"][2]
        missing, n_bad = utils.validate_columns(df, alt_cols)
        if missing:
            st.error(f"Missing required column(s): **{', '.join(missing)}**. "
                     f"Required: {', '.join(alt_cols)}. "
                     "Download the sample template for the correct format.")
            return
        if n_bad:
            st.warning(f"{n_bad} row(s) have missing values in required fields and "
                       "will be dropped before scoring.")
            df = df.dropna(subset=alt_cols).reset_index(drop=True)
        if "applicant_id" not in df.columns:
            df.insert(0, "applicant_id", [f"APP-{i:04d}" for i in range(1, len(df) + 1)])
        st.session_state.batch = df
        st.session_state.batch_source = uploaded.name
        st.success(f"Loaded {len(df)} applicants from {uploaded.name}.")

    scored = get_scored_batch()
    if scored is None:
        st.info("No batch loaded. Upload a CSV or click **Use demo batch** above.")
        return

    st.markdown("### Threshold & summary")
    threshold = st.slider(
        "Approve applicants with default risk **below** this percentage",
        min_value=1, max_value=90, value=25, step=1, format="%d%%")
    caption("Move the slider to set your risk appetite. Everything below the line is "
            "approved; the metrics and estimated default rate update live.")

    approved = scored["risk_pct"] < threshold
    approval_rate = approved.mean()
    # Estimated default rate among approved = mean predicted risk of approved pool.
    est_default_approved = (scored.loc[approved, "risk_pct"].mean() / 100
                            if approved.any() else 0.0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total applicants", f"{len(scored):,}")
    m2.metric("Average risk", f"{scored['risk_pct'].mean():.1f}%")
    m3.metric("Approval rate", f"{approval_rate:.0%}")
    m4.metric("Est. default rate (approved)", f"{est_default_approved:.1%}")
    caption("Estimated default rate is the average predicted risk among the applicants "
            "you would approve — a proxy for the losses this policy would let through.")

    st.markdown("### Risk distribution")
    hist = alt.Chart(scored).mark_bar(color=STEEL).encode(
        alt.X("risk_pct:Q", bin=alt.Bin(maxbins=30), title="Predicted default risk (%)"),
        alt.Y("count()", title="Number of applicants"),
        tooltip=[alt.Tooltip("count()", title="Applicants")],
    )
    rule = alt.Chart(pd.DataFrame({"t": [threshold]})).mark_rule(
        color=RED, strokeDash=[6, 4], size=2).encode(x="t:Q")
    st.altair_chart(hist + rule, use_container_width=True)
    caption("Each bar counts applicants at a given risk level. The dashed red line is "
            "your approval threshold — bars to its left are approved.")

    st.markdown("### Applicant results")
    fcol1, fcol2 = st.columns([1, 3])
    with fcol1:
        cat_filter = st.multiselect("Filter by risk category",
                                    ["Low", "Medium", "High"],
                                    default=["Low", "Medium", "High"])
    view = scored[scored["risk_category"].isin(cat_filter)].copy()
    view["decision"] = np.where(view["risk_pct"] < threshold, "✅ Approve", "❌ Decline")
    show_cols = (["applicant_id"] + ART["alt"][2] +
                 ["risk_pct", "risk_category", "decision"])
    st.dataframe(
        view[show_cols].sort_values("risk_pct"),
        use_container_width=True, hide_index=True,
        column_config={
            "risk_pct": st.column_config.NumberColumn("Risk %", format="%.1f"),
        })
    caption("Sortable, filterable table of every applicant with their score, risk band, "
            "and the approve/decline decision at the current threshold.")

    export = view[show_cols].copy()
    st.download_button("⬇️ Download results as CSV",
                       export.to_csv(index=False),
                       "risk_results.csv", "text/csv")


# --------------------------------------------------------------------------- #
# TAB 3 — Applicant Drill-Down
# --------------------------------------------------------------------------- #
def tab_drilldown():
    st.title("Applicant Drill-Down")
    scored = get_scored_batch()
    if scored is None:
        st.info("Load a batch in **Batch Assessment** first.")
        return

    applicant_id = st.selectbox("Select an applicant", scored["applicant_id"].tolist())
    row = scored[scored["applicant_id"] == applicant_id].iloc[0]
    risk = row["risk_pct"]
    cat = row["risk_category"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Default risk", f"{risk:.1f}%")
    c2.metric("Risk category", cat)
    c3.metric("Credit score", int(row["credit_score"]))
    st.markdown(
        f'<div style="height:8px;background:{CAT_COLORS[cat]};border-radius:4px;'
        f'width:{min(risk,100):.0f}%"></div>', unsafe_allow_html=True)
    caption(f"This applicant sits in the **{cat}** risk band. The bar length reflects "
            "their predicted probability of default.")

    st.markdown("### What drove this decision?")
    alt_model, _, alt_cols = ART["alt"]
    vals, base = ART["explain_alt"](pd.DataFrame([row[alt_cols]], columns=alt_cols))
    contrib = pd.DataFrame({
        "feature": [utils.FEATURE_LABELS[c] for c in alt_cols],
        "impact": vals[0] * 100,
    }).sort_values("impact")
    contrib["direction"] = np.where(contrib["impact"] >= 0, "Increases risk", "Reduces risk")

    chart = alt.Chart(contrib).mark_bar().encode(
        x=alt.X("impact:Q", title="Impact on default risk (percentage points)"),
        y=alt.Y("feature:N", sort=contrib["feature"].tolist(), title=None),
        color=alt.Color("direction:N",
                        scale=alt.Scale(domain=["Increases risk", "Reduces risk"],
                                        range=[RED, GREEN]),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("feature"), alt.Tooltip("impact:Q", format="+.2f")],
    )
    st.altair_chart(chart, use_container_width=True)
    caption(f"Reading this: the model starts from a baseline risk of {base*100:.0f}% "
            "(the average applicant). Red bars pushed this person's risk **up**, green "
            "bars pulled it **down**, adding up to their final score.")


# --------------------------------------------------------------------------- #
# TAB 4 — Traditional vs Alternative
# --------------------------------------------------------------------------- #
def tab_compare():
    st.title("Traditional vs. Alternative Scoring")
    st.write("The central question: does adding behavioral data change who gets "
             "approved — especially for thin-file borrowers?")
    scored = get_scored_batch()
    if scored is None:
        st.info("Load a batch in **Batch Assessment** first.")
        return

    threshold = st.slider("Approval threshold (approve if risk below)",
                          1, 90, 25, 1, format="%d%%")

    scored = scored.copy()
    scored["trad_decision"] = np.where(scored["risk_pct_traditional"] < threshold,
                                       "Approve", "Decline")
    scored["alt_decision"] = np.where(scored["risk_pct"] < threshold,
                                      "Approve", "Decline")
    flipped_up = scored[(scored["trad_decision"] == "Decline") &
                        (scored["alt_decision"] == "Approve")]
    flipped_down = scored[(scored["trad_decision"] == "Approve") &
                          (scored["alt_decision"] == "Decline")]

    st.markdown("### Individual comparison")
    applicant_id = st.selectbox("Select an applicant", scored["applicant_id"].tolist())
    row = scored[scored["applicant_id"] == applicant_id].iloc[0]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Traditional model")
        st.metric("Default risk", f"{row['risk_pct_traditional']:.1f}%")
        st.markdown(f"**Decision:** {'✅ Approve' if row['trad_decision']=='Approve' else '❌ Decline'}")
        caption("Uses only credit score, income, existing debt and loan amount.")
    with c2:
        st.markdown("#### Traditional + Alternative model")
        st.metric("Default risk", f"{row['risk_pct']:.1f}%",
                  delta=f"{row['risk_pct'] - row['risk_pct_traditional']:+.1f} pts")
        st.markdown(f"**Decision:** {'✅ Approve' if row['alt_decision']=='Approve' else '❌ Decline'}")
        caption("Adds payment consistency, income volatility and debt trend.")

    if row["trad_decision"] != row["alt_decision"]:
        if row["alt_decision"] == "Approve":
            st.success("🔑 **Decision flip:** the traditional model would **decline** this "
                       "applicant, but the behavioral signals reveal them as an acceptable "
                       "risk — a thin-file borrower the old score would have missed.")
        else:
            st.warning("⚠️ **Decision flip:** the traditional model would approve this "
                       "applicant, but behavioral signals flag elevated risk the "
                       "traditional score overlooked.")
    else:
        st.info("Both models agree on this applicant at the current threshold.")

    st.markdown("### Portfolio-level impact")
    m1, m2, m3 = st.columns(3)
    m1.metric("Newly approved by behavioral data", len(flipped_up))
    m2.metric("Newly declined by behavioral data", len(flipped_down))
    m3.metric("Net change in approvals", f"{len(flipped_up) - len(flipped_down):+d}")
    caption("Across the whole batch, how many decisions the behavioral features flip in "
            "each direction at the current threshold.")

    if len(flipped_up):
        st.markdown("**Applicants the traditional model would have rejected, now approved:**")
        st.dataframe(
            flipped_up[["applicant_id", "credit_score", "payment_consistency_pct",
                        "income_volatility_score", "risk_pct_traditional", "risk_pct"]]
            .rename(columns={"risk_pct_traditional": "trad_risk_%", "risk_pct": "alt_risk_%"}),
            use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# TAB 5 — Fairness Check
# --------------------------------------------------------------------------- #
def tab_fairness():
    st.title("Fairness Check")
    st.write("Do approval rates differ sharply across income brackets? This is an "
             "**access lens**, not a legal bias verdict — income is not a protected "
             "attribute, and some variation is expected.")
    scored = get_scored_batch()
    if scored is None:
        st.info("Load a batch in **Batch Assessment** first.")
        return

    threshold = st.slider("Approval threshold (approve if risk below)",
                          1, 90, 25, 1, format="%d%%")
    scored = scored.copy()
    scored["approved"] = scored["risk_pct"] < threshold
    scored["income_bracket"] = pd.qcut(
        scored["income"], 3, labels=["Low income", "Medium income", "High income"])

    rates = (scored.groupby("income_bracket", observed=True)["approved"]
             .mean().reset_index())
    rates["approval_pct"] = rates["approved"] * 100

    chart = alt.Chart(rates).mark_bar().encode(
        x=alt.X("income_bracket:N", title=None,
                sort=["Low income", "Medium income", "High income"]),
        y=alt.Y("approval_pct:Q", title="Approval rate (%)",
                scale=alt.Scale(domain=[0, 100])),
        color=alt.value(STEEL),
        tooltip=[alt.Tooltip("income_bracket"), alt.Tooltip("approval_pct:Q", format=".1f")],
    )
    labels = chart.mark_text(dy=-8, color=NAVY).encode(
        text=alt.Text("approval_pct:Q", format=".0f"))
    st.altair_chart(chart + labels, use_container_width=True)
    caption("Share of applicants approved in each income third, at the current threshold.")

    gap = rates["approval_pct"].max() - rates["approval_pct"].min()
    low = rates.loc[rates["income_bracket"] == "Low income", "approval_pct"].iloc[0]
    high = rates.loc[rates["income_bracket"] == "High income", "approval_pct"].iloc[0]
    if gap < 10:
        st.success(f"✅ Approval rates are within **{gap:.0f} percentage points** across "
                   "income brackets — no large access gap at this threshold.")
    elif gap < 25:
        st.warning(f"⚠️ There is a **{gap:.0f}-point** approval gap between the highest and "
                   f"lowest income brackets (low income {low:.0f}% vs high income {high:.0f}%). "
                   "Worth monitoring.")
    else:
        st.error(f"🚩 A large **{gap:.0f}-point** approval gap exists (low income {low:.0f}% "
                 f"vs high income {high:.0f}%). Investigate whether the model is denying "
                 "credit access to lower-income but creditworthy applicants.")


# --------------------------------------------------------------------------- #
# TAB 6 — Model Performance & Limitations
# --------------------------------------------------------------------------- #
def tab_performance():
    st.title("Model Performance & Limitations")
    metrics = utils.load_metrics().copy()
    metrics["feature_set"] = metrics["feature_set"].map(
        {"traditional": "Traditional", "alternative": "Traditional + Alternative"})
    metrics = metrics.rename(columns={
        "feature_set": "Feature set", "model": "Model", "precision": "Precision",
        "recall": "Recall", "f1": "F1", "auc_pr": "AUC-PR", "roc_auc": "ROC-AUC"})

    st.markdown("### Model comparison")
    st.dataframe(
        metrics.style.format({c: "{:.3f}" for c in
                              ["Precision", "Recall", "F1", "AUC-PR", "ROC-AUC"]})
        .background_gradient(subset=["AUC-PR"], cmap="Blues"),
        use_container_width=True, hide_index=True)
    caption("Precision = of those flagged high-risk, how many truly default. "
            "Recall = of true defaulters, how many we catch. F1 balances the two. "
            "AUC-PR is the headline metric for this imbalanced problem. Accuracy is "
            "deliberately omitted — it is misleading when defaults are rare.")

    best = utils.load_best_models()
    delta = best["alternative"]["auc_pr"] - best["traditional"]["auc_pr"]
    st.info(f"**Key finding:** adding behavioral features lifts the best model's AUC-PR "
            f"from {best['traditional']['auc_pr']:.2f} to {best['alternative']['auc_pr']:.2f} "
            f"(**+{delta:.2f}**) — a meaningful gain in separating defaulters from "
            "non-defaulters, concentrated among thin-file applicants.")

    st.markdown("### Limitations")
    st.markdown("""
    - **Synthetic data.** The 5,000 applicants are generated, not real. Behavioral
      signals are designed to be informative (especially for thin files), so the
      *magnitude* of improvement is illustrative, not a market estimate.
    - **No temporal validation.** Real credit models must be validated across time
      and economic cycles; this is a single static split.
    - **Fairness lens is partial.** We check income-bracket access only. A real audit
      needs protected attributes, disparate-impact testing, and legal review.
    - **Not calibrated for pricing.** Scores rank risk; they are not calibrated
      probabilities suitable for setting interest rates or reserves.
    """)

    st.markdown(
        '<div class="disclaimer">⚠️ This is a prototype for demonstration purposes. '
        'It is <b>not validated for production lending decisions</b> and must not be '
        'used to approve, deny, or price real credit.</div>',
        unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
{
    "Overview": tab_overview,
    "Batch Assessment": tab_batch,
    "Applicant Drill-Down": tab_drilldown,
    "Traditional vs Alternative": tab_compare,
    "Fairness Check": tab_fairness,
    "Model Performance & Limitations": tab_performance,
}[TAB]()
