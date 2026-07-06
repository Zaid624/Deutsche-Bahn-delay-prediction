import pandas as pd
import warnings; warnings.filterwarnings("ignore")

df = pd.read_parquet("data/features.parquet")

# Group by ride + date to get per-journey groups
df["ride_date"] = df["train_line_ride_id"].astype(str) + "_" + df["time"].dt.date.astype(str)
ride_date_counts = df.groupby("ride_date").size()
print(f"Unique ride+date combos: {len(ride_date_counts)}")
print(f"Rows per ride+date: mean={ride_date_counts.mean():.1f}, median={ride_date_counts.median():.0f}")

# For each ride+date, sort by station_num and shift to get previous delay
df_sorted = df.sort_values(["ride_date", "train_line_station_num"])
df_sorted["prev_delay"] = df_sorted.groupby("ride_date")["delay_in_min"].shift(1)
df_sorted["prev_delayed"] = (df_sorted["prev_delay"] > 5).astype(float)

# Check cascading effect
valid = df_sorted.dropna(subset=["prev_delayed"])
corr = valid["prev_delayed"].corr(valid["delay_binary"])
pct_if_delayed = valid[valid["prev_delayed"]==1]["delay_binary"].mean() * 100
pct_if_not = valid[valid["prev_delayed"]==0]["delay_binary"].mean() * 100
print(f"\nCascading delay effect:")
print(f"  Correlation with target: {corr:.3f}")
print(f"  If prev stop delayed -> {pct_if_delayed:.1f}% current delayed")
print(f"  If prev stop on time -> {pct_if_not:.1f}% current delayed")
print(f"  Valid rows (have previous stop): {len(valid):,}")

# Historical delay rate per (station, hour, day_of_week)
print("\n--- Historical delay rate features ---")
print("Station+hour+day_of_week combos:")
shdw = df.groupby(["station_name", "hour", "day_of_week"])["delay_binary"].mean()
print(f"  Unique combos: {len(shdw)}")
print(f"  Rate range: {shdw.min():.2f} to {shdw.max():.2f}")

# Train frequency per (station, hour)
print("\n--- Train frequency ---")
freq = df.groupby(["station_name", "hour"]).size().rename("train_count")
print(f"  Mean trains per station-hour: {freq.mean():.0f}")
print(f"  Range: {freq.min()} to {freq.max()}")

# Check: user's delay_binary correlation with train_count
df_with_freq = df.join(freq, on=["station_name", "hour"])
print(f"  Correlation train_count vs delay: {df_with_freq['train_count'].corr(df_with_freq['delay_binary']):.3f}")
