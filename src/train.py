"""
Model training pipeline for DB delay prediction (v2 — improved features).

Features now include cascading delay, historical rates, and train
frequency for significantly better accuracy.
"""

import sys
import warnings
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from xgboost import XGBClassifier
except ImportError:
    XGBClassifier = None  # type: ignore

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FEATURES_PATH = Path("data/features_v2.parquet")
MODEL_DIR = Path("models")
LOGREG_PATH = MODEL_DIR / "logreg_baseline.joblib"
XGB_PATH = MODEL_DIR / "xgb_model.joblib"
XGB_TUNED_PATH = MODEL_DIR / "xgb_tuned.joblib"
XGB_WEATHER_PATH = MODEL_DIR / "xgb_weather.joblib"

SPLIT_DATE = "2025-09-01"
TARGET = "delay_binary"
RANDOM_STATE = 42

NUMERIC_FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "is_rush_hour",
    "is_holiday",
    "prev_delay_min",
    "train_count",
    "hist_delay_rate",
    "planned_dwell_minutes",
    "is_first_stop",
]

WEATHER_FEATURES = [
    "temperature_c",
    "humidity_pct",
    "precipitation_mm",
    "wind_speed_ms",
    "wind_direction",
    "sunshine_minutes",
    "cloud_cover_pct",
    "pressure_hpa",
]

CATEGORIC_FEATURES = ["station_name", "season", "prev_delayed", "has_planned_times"]


def load_data() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PATH)
    print(f"Loaded {len(df):,} rows from {FEATURES_PATH}")
    return df


def prepare_features(df: pd.DataFrame):
    train_df = df[df["time"] < SPLIT_DATE].copy()
    test_df = df[df["time"] >= SPLIT_DATE].copy()
    print(f"\nTime-based split: train <= {SPLIT_DATE}")
    print(
        f"  Train: {len(train_df):,} rows ({train_df[TARGET].mean() * 100:.1f}% delayed)"
    )
    print(
        f"  Test:  {len(test_df):,} rows ({test_df[TARGET].mean() * 100:.1f}% delayed)"
    )

    ALL_FEATURES = NUMERIC_FEATURES + WEATHER_FEATURES + CATEGORIC_FEATURES
    X_train = train_df[[c for c in ALL_FEATURES if c in train_df.columns]]
    y_train = train_df[TARGET]
    X_test = test_df[[c for c in ALL_FEATURES if c in test_df.columns]]
    y_test = test_df[TARGET]
    return X_train, X_test, y_train, y_test


def build_preprocessor(numeric_features=None):
    if numeric_features is None:
        numeric_features = NUMERIC_FEATURES
    return ColumnTransformer(
        [
            ("num", StandardScaler(), numeric_features),
            (
                "cat",
                OneHotEncoder(
                    drop="first", sparse_output=False, handle_unknown="ignore"
                ),
                CATEGORIC_FEATURES,
            ),
        ]
    )


def evaluate_model(name: str, model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division="warn")
    rec = recall_score(y_test, y_pred, zero_division="warn")
    f1 = f1_score(y_test, y_pred, zero_division="warn")
    auc = roc_auc_score(y_test, y_proba)
    cm = confusion_matrix(y_test, y_pred)

    print(f"  {'=' * 40}")
    print(f"  {name}")
    print(f"  {'=' * 40}")
    print(f"  Accuracy:  {acc:.4f}")
    print(f"  Precision: {prec:.4f}")
    print(f"  Recall:    {rec:.4f}")
    print(f"  F1:        {f1:.4f}")
    print(f"  ROC-AUC:   {auc:.4f}")
    print("\n  Confusion matrix:")
    print(f"    TN={cm[0, 0]:,}  FP={cm[0, 1]:,}")
    print(f"    FN={cm[1, 0]:,}  TP={cm[1, 1]:,}")
    print("\n  Classification report:")
    print(
        f"  {classification_report(y_test, y_pred, target_names=['On time', 'Delayed'], zero_division='warn')}"
    )

    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1, "roc_auc": auc}


def train_logreg(X_train, y_train, X_test, y_test, numeric_features=None):
    print("\n--- Logistic Regression (baseline) ---")
    if numeric_features is None:
        numeric_features = NUMERIC_FEATURES
    pipeline = Pipeline(
        [
            ("preprocessor", build_preprocessor(numeric_features)),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)
    metrics = evaluate_model("Logistic Regression", pipeline, X_test, y_test)
    joblib.dump(pipeline, LOGREG_PATH)
    print(f"  Saved to {LOGREG_PATH}")
    return pipeline, metrics


def train_xgboost(
    X_train,
    y_train,
    X_test,
    y_test,
    tuned=False,
    numeric_features=None,
    label=None,
    save_path=None,
):
    """XGBoost with tuned hyperparameters + early stopping."""
    if label is None:
        label = "XGBoost (tuned)" if tuned else "XGBoost (default)"
    if numeric_features is None:
        numeric_features = NUMERIC_FEATURES
    print(f"\n--- {label} ---")

    # Scale pos weight: ratio of negative to positive
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()

    if tuned:
        params = {
            "n_estimators": 800,
            "max_depth": 8,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "reg_alpha": 0.1,
            "reg_lambda": 2.0,
            "gamma": 0.1,
            "scale_pos_weight": neg / pos,
            "random_state": RANDOM_STATE,
            "n_jobs": -1,
            "eval_metric": "logloss",
            "early_stopping_rounds": 50,
        }
    else:
        params = {
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "scale_pos_weight": neg / pos,
            "random_state": RANDOM_STATE,
            "n_jobs": -1,
            "eval_metric": "logloss",
        }

    if tuned:
        preprocessor = build_preprocessor(numeric_features)
        X_tr = preprocessor.fit_transform(X_train)
        X_te = preprocessor.transform(X_test)
        clf = XGBClassifier(**params)
        clf.fit(
            X_tr, y_train, eval_set=[(X_tr, y_train), (X_te, y_test)], verbose=False
        )
        pipeline = Pipeline(
            [
                ("preprocessor", preprocessor),
                ("classifier", clf),
            ]
        )
        print(f"  Best iteration: {clf.best_iteration}")
    else:
        pipeline = Pipeline(
            [
                ("preprocessor", build_preprocessor(numeric_features)),
                ("classifier", XGBClassifier(**params)),
            ]
        )
        pipeline.fit(X_train, y_train)

    metrics = evaluate_model(label, pipeline, X_test, y_test)
    if save_path:
        joblib.dump(pipeline, save_path)
        print(f"  Saved to {save_path}")
    return pipeline, metrics


def main():
    print("=" * 50)
    print("DB Delay Predictor - Model Training v3 (with weather)")
    print("=" * 50)

    df = load_data()
    X_train, X_test, y_train, y_test = prepare_features(df)

    results = {}
    # Baseline models without weather
    _, results["Logistic Regression"] = train_logreg(X_train, y_train, X_test, y_test)
    _, results["XGBoost (default)"] = train_xgboost(
        X_train, y_train, X_test, y_test, tuned=False
    )
    _, results["XGBoost (tuned)"] = train_xgboost(
        X_train, y_train, X_test, y_test, tuned=True
    )

    # Model with weather features
    print("\n" + "-" * 50)
    print("XGBoost with Weather Features")
    print("-" * 50)
    all_features = NUMERIC_FEATURES + WEATHER_FEATURES

    _, results["XGBoost + Weather"] = train_xgboost(
        X_train,
        y_train,
        X_test,
        y_test,
        tuned=True,
        numeric_features=all_features,
        label="XGBoost + Weather",
        save_path=XGB_WEATHER_PATH,
    )

    print("\n" + "=" * 50)
    print("Model Comparison Summary")
    print("=" * 50)
    comparison = pd.DataFrame(results).round(4)
    print(comparison.to_string())

    print(f"\nModels saved to {MODEL_DIR}/")


if __name__ == "__main__":
    main()
