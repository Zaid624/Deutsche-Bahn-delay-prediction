"""
Model interpretation and portfolio visualizations.

Produces 4 plots saved to reports/:
  1. delay_by_hour.png       — % delayed by hour of day
  2. delay_by_station.png    — % delayed by station (sorted)
  3. delay_by_season.png     — % delayed by season
  4. shap_importance.png     — SHAP feature importance (top 12)
"""

import sys
import warnings
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.train import CATEGORIC_FEATURES, NUMERIC_FEATURES, WEATHER_FEATURES, SPLIT_DATE, TARGET

REPORTS_DIR = Path("reports")
FEATURES_PATH = Path("data/features_v2.parquet")
MODEL_PATH = Path("models/xgb_weather.joblib")


def setup_plotting():
    """Global matplotlib settings for consistent, clean charts."""
    sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def plot_delay_by_hour(df: pd.DataFrame):
    """Bar chart: % of trains delayed (>5 min) for each hour of the day."""
    hourly = df.groupby("hour")[TARGET].mean().mul(100).reset_index()

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=hourly, x="hour", y=TARGET, color="#4C72B0", edgecolor="white", ax=ax)
    train_pct = df[df["time"] < SPLIT_DATE][TARGET].mean() * 100
    test_pct = df[df["time"] >= SPLIT_DATE][TARGET].mean() * 100
    ax.axhline(train_pct, color="gray", ls="--", lw=1, label=f"Train avg ({train_pct:.0f}%)")
    ax.axhline(test_pct, color="red", ls="--", lw=1, label=f"Test avg ({test_pct:.0f}%)")
    ax.set_xlabel("Hour of day (0 = midnight)")
    ax.set_ylabel("Trains delayed > 5 min (%)")
    ax.set_title("ICE Delays by Hour of Day\n(top 10 stations, Jul 2024 – Nov 2025)")
    ax.legend()
    fig.tight_layout()
    path = REPORTS_DIR / "delay_by_hour.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def plot_delay_by_station(df: pd.DataFrame):
    """Horizontal bar chart: % delayed per station, sorted worst → best."""
    station_order = (
        df.groupby("station_name")[TARGET]
        .mean()
        .sort_values(ascending=False)
        .index
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(
        data=df,
        x=TARGET,
        y="station_name",
        order=station_order,
        color="#DD8452",
        edgecolor="white",
        ax=ax,
    )
    ax.set_xlabel("Trains delayed > 5 min (%)")
    ax.set_ylabel("")
    ax.set_title("ICE Delays by Station\n(Jul 2024 – Nov 2025)")
    fig.tight_layout()
    path = REPORTS_DIR / "delay_by_station.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def plot_delay_by_season(df: pd.DataFrame):
    """Grouped bar chart: % delayed in each season."""
    season_order = ["winter", "spring", "summer", "autumn"]
    seasonal = df.groupby("season")[TARGET].mean().reindex(season_order).mul(100).reset_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=seasonal, x="season", y=TARGET, order=season_order, color="#55A868", edgecolor="white", ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("Trains delayed > 5 min (%)")
    ax.set_title("ICE Delays by Season")
    fig.tight_layout()
    path = REPORTS_DIR / "delay_by_season.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def plot_feature_importance(pipeline, X_test_raw: pd.DataFrame, weather_model: bool = False):
    """
    XGBoost built-in feature importance (gain-based).

    Gain = average improvement in accuracy each feature contributes
    whenever it is used in a tree split. This is the most reliable
    single-number importance metric for tree-based models.

    SHAP would give more nuanced per-prediction explanations, but
    XGBoost's gain importance tells the same high-level story for a
    portfolio project and avoids a known version-compatibility issue
    between shap and xgboost >= 2.1.
    """
    preprocessor = pipeline.named_steps["preprocessor"]
    classifier = pipeline.named_steps["classifier"]

    # Feature names after one-hot encoding
    cat_encoder = preprocessor.named_transformers_["cat"]
    cat_feature_names = cat_encoder.get_feature_names_out(CATEGORIC_FEATURES).tolist()
    numeric_cols = NUMERIC_FEATURES + (WEATHER_FEATURES if weather_model else [])
    all_feature_names = numeric_cols + cat_feature_names

    # Gain-based importance from XGBoost
    importance = classifier.feature_importances_
    assert len(importance) == len(all_feature_names)

    feat_df = pd.DataFrame({"feature": all_feature_names, "importance": importance})
    feat_df = feat_df.sort_values("importance", ascending=True).tail(12)

    # Color weather features differently
    colors = []
    for f in feat_df["feature"]:
        if any(w in f for w in WEATHER_FEATURES):
            colors.append("#55A868")  # green for weather
        else:
            colors.append("#4C72B0")  # blue for non-weather

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(feat_df["feature"], feat_df["importance"], color=colors, edgecolor="white")
    ax.set_xlabel("Feature importance (gain)")
    ax.set_ylabel("")
    title = "Top 12 Features with Weather Data\n(delay > 5 min prediction)" if weather_model else "Top 12 Features by XGBoost Gain Importance"
    ax.set_title(title)
    # Custom legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4C72B0", label="Non-weather"),
        Patch(facecolor="#55A868", label="Weather"),
    ]
    ax.legend(handles=legend_elements, loc="lower right")
    fig.tight_layout()
    path = REPORTS_DIR / "feature_importance.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def main():
    print("=" * 50)
    print("DB Delay Predictor - Model Interpretation")
    print("=" * 50)

    setup_plotting()

    # 1. Load data
    print("\nLoading features ...")
    df = pd.read_parquet(FEATURES_PATH)
    print(f"  {len(df):,} rows")

    # 2. Load model (weather model)
    print("\nLoading XGBoost weather model ...")
    pipeline = joblib.load(MODEL_PATH)
    print(f"  Loaded from {MODEL_PATH}")

    # 3. Generate plots
    print("\nGenerating plots ...")
    plot_delay_by_hour(df)
    plot_delay_by_station(df)
    plot_delay_by_season(df)

    print("\nPlotting feature importance (with weather) ...")
    all_features = NUMERIC_FEATURES + WEATHER_FEATURES + CATEGORIC_FEATURES
    X_test_raw = df[df["time"] >= SPLIT_DATE][[c for c in all_features if c in df.columns]]
    plot_feature_importance(pipeline, X_test_raw, weather_model=True)

    # 4. Also save non-weather feature importance (without weather features highlighted)
    try:
        print("\nLoading non-weather XGBoost model for comparison ...")
        old_model = joblib.load(Path("models/xgb_tuned.joblib"))
        old_X_test = df[df["time"] >= SPLIT_DATE][NUMERIC_FEATURES + CATEGORIC_FEATURES]
        plot_feature_importance(old_model, old_X_test, weather_model=False)
        import shutil
        shutil.copy(REPORTS_DIR / "feature_importance.png", REPORTS_DIR / "feature_importance_noweather.png")
        print(f"  Also saved feature_importance_noweather.png")
    except Exception as e:
        print(f"  Could not load non-weather model: {e}")

    print(f"\nAll plots saved to {REPORTS_DIR}/")


if __name__ == "__main__":
    main()
