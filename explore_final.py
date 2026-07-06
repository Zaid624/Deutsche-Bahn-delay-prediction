import pandas as pd
import joblib
import numpy as np
from sklearn.metrics import accuracy_score
import warnings; warnings.filterwarnings("ignore")

df = pd.read_parquet("data/features_v2.parquet")
logreg = joblib.load("models/logreg_baseline.joblib")
xgb = joblib.load("models/xgb_tuned.joblib")

NUM = ["hour","day_of_week","month","is_weekend","is_rush_hour","is_holiday",
       "prev_delay_min","train_count","hist_delay_rate","planned_dwell_minutes","is_first_stop"]
CAT = ["station_name","season","prev_delayed","has_planned_times"]
TARGET = "delay_binary"
SPLIT_DATE = "2025-09-01"

test = df[df["time"] >= SPLIT_DATE].copy()
X_test = test[NUM + CAT]
y_test = test[TARGET]

# Ensemble: average probabilities
lr_proba = logreg.predict_proba(X_test)[:, 1]
xgb_proba = xgb.predict_proba(X_test)[:, 1]
ensemble_proba = (lr_proba + xgb_proba) / 2

for thresh in [0.45, 0.50, 0.55]:
    pred = (ensemble_proba >= thresh).astype(int)
    acc = accuracy_score(y_test, pred)
    print(f"Ensemble (threshold={thresh}): accuracy = {acc:.4f}")

# Best individual model
xgb_pred = xgb.predict(X_test)
print(f"XGBoost (threshold=0.5): accuracy = {accuracy_score(y_test, xgb_pred):.4f}")

# What if we had perfect prev_delay knowledge?
print()
print("=== Upper bound analysis ===")
# If prev_delayed=1, we'd predict 1 with 81.2% accuracy
# But we already use this feature in the model
# Let's check: what's the correlation ceiling?
from sklearn.metrics import roc_auc_score
print(f"Best ROC-AUC achieved: {roc_auc_score(y_test, xgb_proba):.4f}")
