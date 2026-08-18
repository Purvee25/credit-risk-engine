# Resume blurb — Credit Risk Decision Engine

**Project name:** Credit Risk Decision Engine — Behavioral Credit Scoring Platform

**Domain:** Machine Learning / Full-Stack AI

**Tech stack:** Python · scikit-learn · XGBoost · SHAP · FastAPI · React · Three.js
(React Three Fiber) · Zustand · Streamlit · Altair · Figma

**One-line description:**
> Full-stack ML platform predicting loan-default risk from traditional + behavioral
> features to widen credit access for thin-file borrowers, served via a REST API,
> an analyst dashboard, and an interactive 3D web app.

**Bullets:**
- Trained and compared Logistic Regression, Random Forest, and XGBoost across two
  feature sets; improved AUC-PR from 0.52 → 0.67 by adding behavioral features,
  with class-weighting for 22% default imbalance and SHAP for explainability.
- Built a FastAPI backend serving real-time scoring, SHAP explanations, and
  CSV-batch endpoints, consumed by a Streamlit analyst dashboard and an immersive
  React + Three.js 3D risk-visualization app with graceful static fallback.
- Engineered an honest synthetic-data generator (5,000 applicants) and a cohesive
  dark UI design system (Figma), shipping a GPU-instanced WebGL "risk field" with
  live approval-threshold controls and decision-flip analysis.
