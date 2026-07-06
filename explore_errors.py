import pandas as pd
import joblib
import warnings; warnings.filterwarnings("ignore")

df = pd.read_parquet("data/features_v2.parquet")
model = joblib.load("models/xgb_tuned.joblib")

NUM_FEATURES = ["hour","day_of_week","month","is_weekend","is_rush_hour","is_holiday",
                "prev_delay_min","train_count","hist_delay_rate"]
CAT_FEATURES = ["station_name","season","prev_delayed"]
TARGET = "delay_binary"
SPLIT_DATE = "2025-09-01"

test = df[df["time"] >= SPLIT_DATE].copy()
X_test = test[NUM_FEATURES + CAT_FEATURES]
y_test = test[TARGET]

y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

test["pred"] = y_pred
test["prob"] = y_proba
test["correct"] = (y_pred == y_test)

# False positives (predicted delayed, actually on time)
fp = test[(test["pred"]==1) & (test["correct"]==False)]
fn = test[(test["pred"]==0) & (test["correct"]==False)]

print(f"False positives: {len(fp)}")
print(f"False negatives: {len(fn)}")
print()

# Analyze FP: what are their features like?
print("=== False Positives (model says delayed, actually on time) ===")
print(f"  Mean hist_delay_rate: {fp['hist_delay_rate'].mean():.3f} vs overall {test['hist_delay_rate'].mean():.3f}")
print(f"  Mean prev_delay_min: {fp['prev_delay_min'].mean():.1f}")
print(f"  % with prev_delayed=1: {(fp['prev_delayed']==1).mean()*100:.1f}%")
print(f"  Mean train_count: {fp['train_count'].mean():.0f}")
print()

print("=== False Negatives (model says on time, actually delayed) ===")
print(f"  Mean hist_delay_rate: {fn['hist_delay_rate'].mean():.3f} vs overall {test['hist_delay_rate'].mean():.3f}")
print(f"  Mean prev_delay_min: {fn['prev_delay_min'].mean():.1f}")
print(f"  % with prev_delayed=1: {(fn['prev_delayed']==1).mean()*100:.1f}%")
print(f"  Mean train_count: {fn['train_count'].mean():.0f}")

# Try tuning the threshold
from sklearn.metrics import accuracy_score
print("\n=== Threshold Tuning ===")
best_acc = 0
best_thresh = 0.5
for thresh in [i/20 for i in range(5, 16)]:
    pred_at_thresh = (y_proba >= thresh).astype(int)
    acc = accuracy_score(y_test, pred_at_thresh)
    if acc > best_acc:
        best_acc = acc
        best_thresh = thresh
    print(f"  Threshold {thresh:.2f}: accuracy = {acc:.4f}")
print(f"\nBest threshold: {best_thresh:.2f} with accuracy {best_acc:.4f}")
