"""
Feature engineering for Deutsche Bahn delay prediction.

Takes the cleaned historical data from Supabase and builds features
for the ML model. The output is saved as a local parquet file so
stages 4-5 (modeling, interpretation) don't need to hit the database
every time.

Feature rationale (why each feature might predict delays):
- hour / is_rush_hour: network congestion peaks during commuter hours;
  more trains = more cascading delays
- day_of_week / is_weekend: weekend schedules differ; fewer freight
  trains but also less staff
- month / season: winter weather (ice, snow, point failures) causes
  more delays; summer construction zones also contribute
- is_holiday: reduced service but also less congestion; effect differs
  by route
- station_name: some stations are bottleneck hubs (e.g. Frankfurt Hbf
  is a major junction) — captures route-specific infra effects

HIGH-IMPACT FEATURES (v2):
- prev_delayed / prev_delay_min: cascading delay — if the same train
  was already late at the previous station, it will likely stay late
  (correlation with target: 0.45, vs 0.27 for basic features)
- hist_delay_rate: historical delay rate for (station, hour, day_of_week)
  from training data — captures predictable congestion patterns
- train_count: number of ICE trains at this station in this hour —
  proxy for network congestion

Future extension: merge DWD (Deutscher Wetterdienst) weather data at
the station-hour level — precipitation, wind speed, temperature —
which likely has strong predictive power for delay.
"""

import sys
from pathlib import Path

import pandas as pd
from holidays import country_holidays

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.database import engine


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET_COL = "delay_in_min"
FEATURE_OUTPUT = Path("data/features_v2.parquet")

# Holidays observed nationwide in Germany (all states)
HOLIDAY_DE = country_holidays("DE", years=range(2024, 2027))

# Weather columns to merge
WEATHER_COLS = [
    "temperature_c", "humidity_pct", "precipitation_mm",
    "wind_speed_ms", "wind_direction",
    "sunshine_minutes", "cloud_cover_pct", "pressure_hpa",
]


def engineer_features(df: pd.DataFrame, weather_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Add time-based, cascading, and weather features.
    Optionally merges DWD weather data on (station_name, date, hour).
    """
    features = df.copy()

    # ---------------------------------------------------------------
    # Convert UTC timestamps to Europe/Berlin local time.
    # ---------------------------------------------------------------
    berlin_tz = "Europe/Berlin"
    local_time = features["time"].dt.tz_convert(berlin_tz)

    # -- Time-based features --
    features["hour"] = local_time.dt.hour
    features["day_of_week"] = local_time.dt.dayofweek
    features["month"] = local_time.dt.month
    features["is_weekend"] = features["day_of_week"].isin([5, 6]).astype(int)
    features["is_rush_hour"] = (
        ((features["hour"] >= 7) & (features["hour"] <= 9))
        | ((features["hour"] >= 16) & (features["hour"] <= 19))
    ).astype(int)

    # -- Season --
    features["season"] = features["month"].map(
        {12: "winter", 1: "winter", 2: "winter",
         3: "spring", 4: "spring", 5: "spring",
         6: "summer", 7: "summer", 8: "summer",
         9: "autumn", 10: "autumn", 11: "autumn"}
    )

    # -- German public holidays --
    features["is_holiday"] = (
        local_time.dt.date.map(lambda d: d in HOLIDAY_DE)
    ).astype(int)

    # ---------------------------------------------------------------
    # HIGH-IMPACT FEATURE 1: Cascading delay from previous station
    # For each train ride on a given day, the delay at the previous
    # station is the single strongest predictor of current delay.
    # ---------------------------------------------------------------
    features["ride_date"] = (
        features["train_line_ride_id"].astype(str)
        + "_"
        + features["time"].dt.date.astype(str)
    )
    features.sort_values(["ride_date", "train_line_station_num"], inplace=True)
    features["prev_delay_min"] = features.groupby("ride_date")["delay_in_min"].shift(1)
    features["prev_delayed"] = (features["prev_delay_min"] > 5).astype(int)
    # First station of a ride has no previous stop
    # - prev_delayed: -1 = unknown (missing indicator)
    # - prev_delay_min: 0 = assume no prior delay when unknown
    features["prev_delayed"] = features["prev_delayed"].fillna(-1).astype(int)
    features["prev_delay_min"] = features["prev_delay_min"].fillna(0)

    # ---------------------------------------------------------------
    # HIGH-IMPACT FEATURE 2: Train frequency at (station, hour)
    # ---------------------------------------------------------------
    freq = features.groupby(["station_name", "hour"]).size().rename("train_count")
    features = features.join(freq, on=["station_name", "hour"])

    # ---------------------------------------------------------------
    # FEATURE 3: Is this the first stop of the ride?
    # First stops have no cascading signal — delay is "fresh".
    # ---------------------------------------------------------------
    features["is_first_stop"] = (features["train_line_station_num"] == 1).astype(int)

    # ---------------------------------------------------------------
    # FEATURE 4: Planned dwell time (how long train stops at station)
    # Longer dwell = more recovery potential. Missing = -1 flag.
    # ---------------------------------------------------------------
    dwell = (
        pd.to_datetime(features["departure_planned_time"], errors="coerce")
        - pd.to_datetime(features["arrival_planned_time"], errors="coerce")
    )
    features["planned_dwell_minutes"] = dwell.dt.total_seconds().div(60)
    features["planned_dwell_minutes"] = features["planned_dwell_minutes"].fillna(-1)
    features["has_planned_times"] = (
        features["arrival_planned_time"].notna() & features["departure_planned_time"].notna()
    ).astype(int)

    # ---------------------------------------------------------------
    # Target variable
    # ---------------------------------------------------------------
    features["delay_binary"] = (features[TARGET_COL] > 5).astype(int)

    # ---------------------------------------------------------------
    # Weather features (from DWD, merged on station_name + date + hour)
    # XGBoost handles missing values natively; no imputation needed.
    # ---------------------------------------------------------------
    features["date"] = features["time"].dt.tz_convert("Europe/Berlin").dt.date
    if weather_df is not None:
        weather_lookup = weather_df.copy()
        weather_lookup["date"] = pd.to_datetime(weather_lookup["date"]).dt.date
        features = features.merge(
            weather_lookup[["station_name", "date", "hour"] + WEATHER_COLS],
            on=["station_name", "date", "hour"],
            how="left",
        )

    # Clean up temporary columns
    features.drop(columns=["ride_date"], inplace=True)

    return features


def add_historical_rates(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """
    Compute historical delay rate from TRAINING data only, then apply
    to both train and test. This avoids data leakage.

    The feature captures: 'at this station, on this hour and day-of-week,
    what fraction of trains historically were delayed?'
    """
    rate = train_df.groupby(["station_name", "hour", "day_of_week"])["delay_binary"].mean()
    rate.name = "hist_delay_rate"

    train_df = train_df.join(rate, on=["station_name", "hour", "day_of_week"])
    test_df = test_df.join(rate, on=["station_name", "hour", "day_of_week"])

    # Fill any station-hour-dow without historical data with global mean
    global_rate = train_df["delay_binary"].mean()
    train_df["hist_delay_rate"] = train_df["hist_delay_rate"].fillna(global_rate)
    test_df["hist_delay_rate"] = test_df["hist_delay_rate"].fillna(global_rate)

    return train_df, test_df


def load_from_db() -> pd.DataFrame:
    """Load train_delays from Supabase into a pandas DataFrame."""
    print("Loading data from Supabase ...")
    df = pd.read_sql(
        """
        SELECT
            id, station_name, train_number, train_type,
            delay_in_min, is_canceled, time,
            train_line_ride_id, train_line_station_num,
            arrival_planned_time, departure_planned_time
        FROM train_delays
        """,
        engine,
        parse_dates=["time", "arrival_planned_time", "departure_planned_time"],
    )
    print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")
    return df


def generate_and_save():
    """Run the full feature pipeline and save to parquet."""
    print("=" * 50)
    print("DB Delay Predictor - Feature Engineering v2")
    print("=" * 50)

    df_raw = load_from_db()

    print("Loading weather data ...")
    from src.weather import get_weather_data
    weather_df = get_weather_data()

    print("Engineering features (including weather) ...")
    df_feat = engineer_features(df_raw, weather_df=weather_df)

    print("Computing historical delay rates (train/test aware) ...")
    split_date = "2025-09-01"
    train = df_feat[df_feat["time"] < split_date].copy()
    test = df_feat[df_feat["time"] >= split_date].copy()
    train, test = add_historical_rates(train, test)
    df_feat = pd.concat([train, test], ignore_index=True)

    FEATURE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df_feat.to_parquet(FEATURE_OUTPUT, index=False)
    print(f"  Saved {len(df_feat):,} rows to {FEATURE_OUTPUT}")

    print("\nFeature overview:")
    print(f"  Target rate: {df_feat['delay_binary'].mean()*100:.1f}%")
    new_cols = [c for c in df_feat.columns if c not in [
        "id","station_name","train_number","train_type","delay_in_min",
        "is_canceled","time","train_line_ride_id","train_line_station_num",
        "arrival_planned_time","departure_planned_time"
    ]]
    print(f"  Feature columns: {new_cols}")
    # Show weather coverage
    if any(c in df_feat.columns for c in WEATHER_COLS):
        nan_pcts = {c: f"{df_feat[c].isna().mean()*100:.1f}%" for c in WEATHER_COLS if c in df_feat.columns}
        print(f"  Weather NaN %: {nan_pcts}")
    print(f"  Memory: {df_feat.memory_usage(deep=True).sum() / 1e6:.1f} MB")

    return df_feat


if __name__ == "__main__":
    generate_and_save()
