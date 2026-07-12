"""Leakage-safe, time-series training pipeline for DB delay prediction."""

import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.features import apply_aggregate_features, fit_aggregate_features

warnings.filterwarnings("ignore")

FEATURES_PATH = Path("data/features_v2.parquet")
MODEL_DIR = Path("models")
LOGREG_PATH = MODEL_DIR / "logreg_baseline.joblib"
XGB_PATH = MODEL_DIR / "xgb_model.joblib"
XGB_TUNED_PATH = MODEL_DIR / "xgb_tuned.joblib"
XGB_WEATHER_PATH = MODEL_DIR / "xgb_weather.joblib"
XGB_NO_CASCADE_PATH = MODEL_DIR / "xgb_weather_no_cascade.joblib"
AGGREGATES_PATH = MODEL_DIR / "feature_aggregates.joblib"

SPLIT_DATE = "2025-09-01"
TARGET = "delay_binary"
RANDOM_STATE = 42
# The product KPI is accuracy. Recall/F1 remain reported, but are not allowed
# to move the serving decision boundary away from the accuracy-optimal point.
THRESHOLD_OBJECTIVE = "accuracy"

NUMERIC_FEATURES = [
    "hour", "day_of_week", "month", "is_weekend", "is_rush_hour",
    "is_holiday", "prev_delay_min", "train_count", "hist_delay_rate",
    "planned_dwell_minutes", "is_first_stop",
]
WEATHER_FEATURES = [
    "temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_ms",
    "wind_direction", "sunshine_minutes", "cloud_cover_pct", "pressure_hpa",
]
CATEGORIC_FEATURES = ["station_name", "season", "prev_delayed", "has_planned_times"]
CASCADE_FEATURES = {"prev_delay_min", "is_first_stop", "prev_delayed"}


def load_data() -> pd.DataFrame:
    df = pd.read_parquet(FEATURES_PATH)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    print(f"Loaded {len(df):,} rows from {FEATURES_PATH}")
    return df.sort_values("time").reset_index(drop=True)


def feature_columns(numeric_features=None, include_cascade=True):
    numeric = list(numeric_features or NUMERIC_FEATURES)
    categorical = list(CATEGORIC_FEATURES)
    if not include_cascade:
        numeric = [column for column in numeric if column not in CASCADE_FEATURES]
        categorical = [column for column in categorical if column not in CASCADE_FEATURES]
    return numeric, categorical


def build_preprocessor(numeric_features, categorical_features):
    return ColumnTransformer([
        ("num", StandardScaler(), numeric_features),
        ("cat", OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore"), categorical_features),
    ])


def prepare_split(train_df, validation_df, numeric_features=None, include_cascade=True):
    """Fit aggregate features on the left side of a time split only."""
    aggregates = fit_aggregate_features(train_df)
    train = apply_aggregate_features(train_df, aggregates)
    validation = apply_aggregate_features(validation_df, aggregates)
    numeric, categorical = feature_columns(numeric_features, include_cascade)
    selected = numeric + categorical
    missing = [column for column in selected if column not in train.columns]
    if missing:
        raise ValueError(f"Required feature columns are missing: {missing}")
    return train[selected], train[TARGET], validation[selected], validation[TARGET], numeric, categorical


def select_threshold(y_true, probabilities, objective=THRESHOLD_OBJECTIVE):
    """Choose a validation-only operating threshold for the stated objective."""
    candidates = np.arange(0.20, 0.81, 0.01)
    if objective == "accuracy":
        scores = [accuracy_score(y_true, probabilities >= value) for value in candidates]
    elif objective == "f1":
        scores = [f1_score(y_true, probabilities >= value, zero_division=0) for value in candidates]
    else:
        raise ValueError(f"Unsupported threshold objective: {objective}")
    return float(candidates[int(np.argmax(scores))])


def evaluate_probabilities(y_true, probabilities, threshold):
    predictions = (np.asarray(probabilities) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "threshold": float(threshold),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def make_xgb(tuned=False, y_train=None):
    if XGBClassifier is None:
        raise ImportError("xgboost is required to train the production model")
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    params = {
        "n_estimators": 550 if tuned else 300,
        "max_depth": 7 if tuned else 6,
        "learning_rate": 0.05 if tuned else 0.1,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "min_child_weight": 3 if tuned else 1,
        "reg_alpha": 0.1 if tuned else 0.0,
        "reg_lambda": 2.0 if tuned else 1.0,
        "scale_pos_weight": neg / max(pos, 1),
        "random_state": RANDOM_STATE, "n_jobs": -1, "eval_metric": "logloss",
    }
    return XGBClassifier(**params)


def fit_model(kind, X_train, y_train, numeric, categorical):
    preprocessor = build_preprocessor(numeric, categorical)
    if kind == "Logistic Regression":
        classifier = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=RANDOM_STATE, n_jobs=-1)
    elif kind == "XGBoost (default)":
        classifier = make_xgb(tuned=False, y_train=y_train)
    else:
        classifier = make_xgb(tuned=True, y_train=y_train)
    pipeline = Pipeline([("preprocessor", preprocessor), ("classifier", classifier)])
    pipeline.fit(X_train, y_train)
    return pipeline


def rolling_windows(df, holdout_start, windows=3):
    """Return expanding train / fixed validation windows before final holdout."""
    history = df[df["time"] < pd.Timestamp(holdout_start, tz="UTC")]
    start, end = history["time"].min(), history["time"].max()
    span = (end - start) / (windows + 1)
    result = []
    for index in range(windows):
        validation_start = start + span * (index + 1)
        validation_end = start + span * (index + 2) if index < windows - 1 else end + pd.Timedelta(nanoseconds=1)
        train = history[history["time"] < validation_start]
        validation = history[(history["time"] >= validation_start) & (history["time"] < validation_end)]
        if not train.empty and not validation.empty:
            result.append((train, validation, str(validation_start.date()), str(validation_end.date())))
    return result


def run_rolling_validation(
    df, model_kind="XGBoost + Weather", windows=3, include_cascade=True
):
    """Assess the selected production family on strictly forward validation windows."""
    fold_metrics, thresholds = [], []
    for fold, (train, validation, start, end) in enumerate(rolling_windows(df, SPLIT_DATE, windows), start=1):
        X_train, y_train, X_val, y_val, numeric, categorical = prepare_split(
            train,
            validation,
            NUMERIC_FEATURES + WEATHER_FEATURES,
            include_cascade=include_cascade,
        )
        model = fit_model(model_kind, X_train, y_train, numeric, categorical)
        probabilities = model.predict_proba(X_val)[:, 1]
        threshold = select_threshold(y_val, probabilities)
        metrics = evaluate_probabilities(y_val, probabilities, threshold)
        metrics.update({"fold": fold, "validation_start": start, "validation_end": end})
        fold_metrics.append(metrics)
        thresholds.append(threshold)
        print(f"  Fold {fold}: AUC={metrics['roc_auc']:.4f}, F1={metrics['f1']:.4f}, threshold={threshold:.2f}")
    summary = {
        metric: {"mean": float(np.mean([row[metric] for row in fold_metrics])), "std": float(np.std([row[metric] for row in fold_metrics]))}
        for metric in ("accuracy", "precision", "recall", "f1", "roc_auc", "brier_score")
    }
    return {"objective": THRESHOLD_OBJECTIVE, "folds": fold_metrics, "summary": summary, "selected_threshold": float(np.median(thresholds))}


def train_and_evaluate(name, train_df, test_df, numeric_features=None, include_cascade=True, threshold=0.5, save_path=None):
    X_train, y_train, X_test, y_test, numeric, categorical = prepare_split(
        train_df, test_df, numeric_features, include_cascade
    )
    model = fit_model(name, X_train, y_train, numeric, categorical)
    metrics = evaluate_probabilities(y_test, model.predict_proba(X_test)[:, 1], threshold)
    print(f"  {name}: accuracy={metrics['accuracy']:.4f}, AUC={metrics['roc_auc']:.4f}, F1={metrics['f1']:.4f}")
    if save_path:
        joblib.dump(model, save_path)
        print(f"  Saved to {save_path}")
    return model, metrics


def main():
    print("DB Delay Predictor - Leakage-safe model training")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    train_df = df[df["time"] < pd.Timestamp(SPLIT_DATE, tz="UTC")].copy()
    test_df = df[df["time"] >= pd.Timestamp(SPLIT_DATE, tz="UTC")].copy()
    if train_df.empty or test_df.empty:
        raise ValueError("Time split produced an empty train or holdout period")

    print("\nRolling validation (aggregate features refit per fold):")
    rolling = run_rolling_validation(df)
    threshold = rolling["selected_threshold"]
    print(f"Selected holdout threshold from rolling validation: {threshold:.2f}")

    print("\nRolling validation for missing-realtime fallback:")
    fallback_rolling = run_rolling_validation(df, include_cascade=False)
    fallback_threshold = fallback_rolling["selected_threshold"]
    print(f"Selected fallback threshold from rolling validation: {fallback_threshold:.2f}")

    results = {}
    _, results["Logistic Regression"] = train_and_evaluate("Logistic Regression", train_df, test_df, threshold=threshold, save_path=LOGREG_PATH)
    _, results["XGBoost (default)"] = train_and_evaluate("XGBoost (default)", train_df, test_df, threshold=threshold, save_path=XGB_PATH)
    _, results["XGBoost (tuned)"] = train_and_evaluate("XGBoost (tuned)", train_df, test_df, threshold=threshold, save_path=XGB_TUNED_PATH)
    weather_model, results["XGBoost + Weather"] = train_and_evaluate(
        "XGBoost + Weather", train_df, test_df, NUMERIC_FEATURES + WEATHER_FEATURES, threshold=threshold, save_path=XGB_WEATHER_PATH
    )
    _, results["XGBoost + Weather (no realtime cascade)"] = train_and_evaluate(
        "XGBoost + Weather", train_df, test_df, NUMERIC_FEATURES + WEATHER_FEATURES,
        include_cascade=False, threshold=fallback_threshold, save_path=XGB_NO_CASCADE_PATH,
    )
    # The predictor reads precisely these training-period lookups rather than
    # recomputing aggregates over all rows in the operational database.
    joblib.dump(fit_aggregate_features(train_df), AGGREGATES_PATH)

    # The holdout is reporting-only. Do not select the deployed model from it;
    # its operating threshold and family were assessed on the rolling windows.
    best_model = "XGBoost + Weather"
    metrics_data = {name: values for name, values in results.items()}
    metrics_data.update({
        "_best_model": best_model,
        "_serving_model": "XGBoost + Weather",
        "_training_date": str(pd.Timestamp.now()),
        "_training_rows": int(len(train_df)),
        "_holdout_rows": int(len(test_df)),
        "_split_date": SPLIT_DATE,
        "_threshold_objective": THRESHOLD_OBJECTIVE,
        "_selected_threshold": threshold,
        "_fallback_threshold": fallback_threshold,
        "_rolling_validation": rolling,
        "_fallback_rolling_validation": fallback_rolling,
        "_features": {"numeric": NUMERIC_FEATURES + WEATHER_FEATURES, "categorical": CATEGORIC_FEATURES},
        "_fallback_model": {"path": str(XGB_NO_CASCADE_PATH), "reason": "missing realtime cascading delay"},
    })

    try:
        classifier = weather_model.named_steps["classifier"]
        preprocessor = weather_model.named_steps["preprocessor"]
        numeric = preprocessor.transformers_[0][2]
        encoder = preprocessor.transformers_[1][1]
        categorical = preprocessor.transformers_[1][2]
        names = list(numeric) + encoder.get_feature_names_out(categorical).tolist()
        metrics_data["_feature_importance"] = {name: float(value) for name, value in sorted(zip(names, classifier.feature_importances_), key=lambda item: item[1], reverse=True)}
    except Exception as exc:
        print(f"Warning: could not extract feature importance: {exc}")

    with open(MODEL_DIR / "model_metrics.json", "w") as file:
        json.dump(metrics_data, file, indent=2)
    print(f"Metrics saved to {MODEL_DIR / 'model_metrics.json'}")


if __name__ == "__main__":
    main()
