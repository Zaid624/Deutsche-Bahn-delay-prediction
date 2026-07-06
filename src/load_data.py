"""
Load & clean monthly parquet data into the train_delays table in Supabase.

Scope (chosen for clear portfolio narrative):
- Train type: ICE only (high-speed long-distance, DB's flagship product)
- Stations: top 10 busiest ICE hubs (Frankfurt, Berlin, München, Hannover, Hamburg,
  Nürnberg, Berlin-Spandau, Köln, Kassel-Wilhelmshöhe, Düsseldorf)
- Cancellations: excluded (they represent a different phenomenon than delay)

Data quality checks performed:
1. Drop columns irrelevant to prediction
2. Filter scope (ICE + top 10 stations)
3. Exclude cancellations
4. Handle missing arrival/departure planned times
5. Verify no duplicate IDs
6. Batch insert for performance
"""

import glob
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text
from tqdm import tqdm

# Add project root to path so src imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import engine, SessionLocal, init_db
from src.models import TrainDelay


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATA_DIR = Path("data/monthly_processed_data")

TOP_10_STATIONS = [
    "Frankfurt (Main) Hbf",
    "Berlin Hauptbahnhof",
    "München Hbf",
    "Hannover Hbf",
    "Hamburg Hbf",
    "Nürnberg Hbf",
    "Berlin-Spandau",
    "Köln Hbf",
    "Kassel-Wilhelmshöhe",
    "Düsseldorf Hbf",
]

COLUMNS_TO_KEEP = [
    "id",
    "station_name",
    "train_number",
    "train_type",
    "delay_in_min",
    "is_canceled",
    "time",
    "train_line_ride_id",
    "train_line_station_num",
    "arrival_planned_time",
    "departure_planned_time",
]

BATCH_SIZE = 5000  # rows per INSERT


# ---------------------------------------------------------------------------
# Step 1: Load & filter each monthly file
# ---------------------------------------------------------------------------
def load_and_filter(filepath: Path) -> pd.DataFrame:
    """Read one parquet file, keep only ICE + top 10 stations, exclude canceled."""
    df = pd.read_parquet(filepath)

    # Keep only our columns of interest
    df = df[COLUMNS_TO_KEEP]

    # Scope: ICE trains only
    df = df[df["train_type"] == "ICE"].copy()

    # Scope: top 10 stations only
    df = df[df["station_name"].isin(TOP_10_STATIONS)].copy()

    # Exclude canceled trips
    before = len(df)
    df = df[~df["is_canceled"]].copy()
    after = len(df)
    canceled_count = before - after

    return df, canceled_count


# ---------------------------------------------------------------------------
# Step 2: Data-quality checks
# ---------------------------------------------------------------------------
def run_quality_checks(df: pd.DataFrame, source_label: str) -> dict:
    """Run a battery of quality checks and return a summary."""
    checks = {}

    # -- No duplicate IDs --
    dupes = df["id"].duplicated().sum()
    if dupes:
        raise ValueError(f"{source_label}: Found {dupes} duplicate IDs — aborting.")
    checks["duplicate_ids"] = 0

    # -- Missing values --
    for col in ["station_name", "train_number", "delay_in_min", "time"]:
        missing = df[col].isna().sum()
        if missing:
            raise ValueError(f"{source_label}: Column '{col}' has {missing} missing values.")
    # Arrival/departure times are allowed to be missing (~10% of rows)
    checks["missing_arrival_planned"] = int(df["arrival_planned_time"].isna().sum())
    checks["missing_departure_planned"] = int(df["departure_planned_time"].isna().sum())

    # -- Delay sanity ranges --
    extreme_late = (df["delay_in_min"] > 400).sum()
    extreme_early = (df["delay_in_min"] < -60).sum()
    if extreme_late > 0 or extreme_early > 0:
        print(f"  [!] {source_label}: {extreme_late} rows >400 min late, {extreme_early} rows <-60 min early (keeping them)")
    checks["extreme_delays"] = extreme_late + extreme_early

    return checks


# ---------------------------------------------------------------------------
# Step 3: Batch insert into Supabase (train_delays table)
# ---------------------------------------------------------------------------
def insert_batches(df: pd.DataFrame):
    """
    Insert rows using pandas' to_sql with multi-row VALUES for speed.
    The 'multi' method generates a single INSERT with multiple value tuples
    per chunk, which is much faster than executemany over a high-latency
    connection (e.g. cloud database).
    """
    df_to_insert = df.copy()
    df_to_insert = df_to_insert.where(pd.notna(df_to_insert), None)
    total = len(df_to_insert)
    inserted = 0
    for start in range(0, total, BATCH_SIZE):
        batch = df_to_insert.iloc[start : start + BATCH_SIZE]
        batch.to_sql(
            "train_delays",
            engine,
            if_exists="append",
            method="multi",
            index=False,
            chunksize=BATCH_SIZE,
        )
        inserted += len(batch)
    return inserted, 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("DB Delay Predictor - Historical Data Loader")
    print("=" * 60)

    # 0. Ensure tables exist
    print("\n[0] Initialising database tables...")
    init_db()

    # 1. Discover parquet files
    files = sorted(glob.glob(str(DATA_DIR / "data-*.parquet")))
    if not files:
        print(f"No parquet files found in {DATA_DIR}. Did you run the download step?")
        sys.exit(1)
    print(f"\n[1] Found {len(files)} monthly parquet files")

    # 2. Load & concatenate all months
    print("\n[2] Loading and filtering data...")
    all_dfs = []
    total_canceled = 0
    total_checks = {}

    for fpath in tqdm(files, desc="Processing months"):
        month_label = Path(fpath).stem
        df_part, canceled = load_and_filter(Path(fpath))
        if len(df_part) == 0:
            continue
        checks = run_quality_checks(df_part, month_label)
        all_dfs.append(df_part)
        total_canceled += canceled
        total_checks[month_label] = checks

    df_all = pd.concat(all_dfs, ignore_index=True)
    print(f"\n  Total rows after filtering: {len(df_all):,}")
    print(f"  Canceled rows excluded: {total_canceled:,}")
    print(f"  Stations in scope: {df_all['station_name'].nunique()} / {len(TOP_10_STATIONS)}")

    stations_found = set(df_all["station_name"].unique())
    missing_stations = set(TOP_10_STATIONS) - stations_found
    if missing_stations:
        print(f"  [!] Missing from data: {missing_stations}")

    # 3. Final data quality summary
    print("\n[3] Data quality summary (across all months):")
    print(f"  Rows: {len(df_all):,}")
    print(f"  Columns: {list(df_all.columns)}")
    print(f"  Delay range: [{df_all['delay_in_min'].min()}, {df_all['delay_in_min'].max()}]")
    print(f"  Median delay: {df_all['delay_in_min'].median():.1f} min")
    print(f"  % delayed > 5 min: {(df_all['delay_in_min'] > 5).mean() * 100:.1f}%")
    print(f"  Missing arrival_planned_time: {df_all['arrival_planned_time'].isna().sum():,} / {len(df_all):,}")
    print(f"  Missing departure_planned_time: {df_all['departure_planned_time'].isna().sum():,} / {len(df_all):,}")

    # 4. Clear existing data and re-insert
    print(f"\n[4] Inserting into Supabase (batches of {BATCH_SIZE:,})...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE train_delays"))
        conn.commit()
    inserted, skipped = insert_batches(df_all)
    print(f"  Inserted: {inserted:,} rows")
    if skipped:
        print(f"  Skipped (already existed): {skipped:,}")

    # 5. Verify count
    print("\n[5] Verifying row count in Supabase...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM train_delays"))
        db_count = result.scalar()
    print(f"  train_delays table now has {db_count:,} rows")

    print("\nDone. Load complete.")


if __name__ == "__main__":
    main()
