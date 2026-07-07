"""
Route-level weather features for train delay prediction.

Pipeline:
1. Read historical delay data from Supabase
2. For each unique (train_number, station_name, time), resolve EVA number
3. Get full route from DB Timetables API (via SQLite cache)
4. Look up DWD weather at every station along the route
5. Compute aggregated route-level weather features
6. Output for merging back onto the main dataset

Strategy for ambiguous matches: include them in the output with
ambiguous_match=True. The downstream model can decide whether to keep
or drop them. By default, features.py excludes ambiguous rows from
training but keeps them in scoring.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.database import engine
from src.eva_lookup import resolve_eva
from src.route_cache import RouteCache, get_route
from src.weather import (
    CACHE_DIR,
    DB_STATIONS,
    WEATHER_PARAMS,
    download_station_data,
    find_nearest_station,
    load_dwd_station_list,
)

logger = logging.getLogger(__name__)

# Route-level weather features
ROUTE_WEATHER_COLS = [
    "avg_temp_along_route",
    "max_precip_along_route",
    "rain_at_next_station",
    "weather_diff_from_origin_temp",
    "weather_diff_from_origin_precip",
    "n_stations_in_route",
    "missing_weather_stations_count",
    "ambiguous_match",
]

_weather_cache: dict[str, pd.DataFrame] = {}
_dwd_station_id_cache: dict[str, str] = {}
_dwd_station_list_cache: Optional[pd.DataFrame] = None

# Additional station coordinates for common ICE intermediate stations
# Format: canonical DB station name -> (lat, lon)
EXTRA_STATION_COORDS: dict[str, tuple[float, float]] = {
    "Mannheim Hbf": (49.479, 8.469),
    "Stuttgart Hbf": (48.783, 9.182),
    "Bremen Hbf": (53.086, 8.813),
    "Leipzig Hbf": (51.345, 12.382),
    "Dresden Hbf": (51.040, 13.731),
    "Freiburg Hbf": (47.997, 7.842),
    "Bielefeld Hbf": (52.029, 8.533),
    "Münster Hbf": (51.957, 7.635),
    "Bonn Hbf": (50.732, 7.097),
    "Würzburg Hbf": (49.801, 9.936),
    "Ulm Hbf": (48.400, 9.987),
    "Augsburg Hbf": (48.365, 10.887),
    "Karlsruhe Hbf": (48.993, 8.401),
    "Mainz Hbf": (50.001, 8.259),
    "Dortmund Hbf": (51.518, 7.459),
    "Essen Hbf": (51.451, 7.013),
    "Aachen Hbf": (50.768, 6.091),
    "Saarbrücken Hbf": (49.241, 6.992),
    "Regensburg Hbf": (49.014, 12.100),
    "Erfurt Hbf": (50.973, 11.038),
    "Rostock Hbf": (54.088, 12.133),
    "Kiel Hbf": (54.315, 10.131),
    "Göttingen Hbf": (51.536, 9.926),
    "Braunschweig Hbf": (52.252, 10.539),
    "Halle (Saale) Hbf": (51.477, 11.987),
    "Chemnitz Hbf": (50.841, 12.929),
    "Magdeburg Hbf": (52.130, 11.603),
    "Oldenburg Hbf": (53.142, 8.222),
    "Koblenz Hbf": (50.349, 7.589),
    "Darmstadt Hbf": (49.872, 8.629),
    "Wiesbaden Hbf": (50.070, 8.244),
    # Stations discovered via DB API ppth (may use different naming than DB_STATIONS)
    "Berlin Hbf": (52.525, 13.369),
    "Berlin Südkreuz": (52.476, 13.365),
    "Bochum Hbf": (51.479, 7.223),
    "Duisburg Hbf": (51.429, 6.775),
    "Frankfurt(M) Flughafen Fernbf": (50.052, 8.570),
    "Frankfurt(Main)Hbf": (50.107, 8.662),
    "Fulda": (50.554, 9.685),
    "Göttingen": (51.536, 9.926),
    "Hildesheim Hbf": (52.155, 9.950),
    "Aschaffenburg Hbf": (49.979, 9.143),
    "München-Pasing": (48.149, 11.459),
    "Stendal Hbf": (52.607, 11.862),
    "Siegburg/Bonn": (50.795, 7.210),
    "Köln Messe/Deutz Gl.11-12": (50.941, 6.974),
    "Wolfsburg Hbf": (52.429, 10.788),
}


def _station_to_coords(station_name: str) -> Optional[tuple[float, float]]:
    """Convert station name to (lat, lon) coordinates."""
    if station_name in DB_STATIONS:
        coords = DB_STATIONS[station_name]
        return (coords["lat"], coords["lon"])
    if station_name in EXTRA_STATION_COORDS:
        return EXTRA_STATION_COORDS[station_name]
    return None


def _get_weather_for_station(
    station_name: str,
    query_date,
    hour: int,
) -> Optional[dict]:
    coords = _station_to_coords(station_name)
    if coords is None:
        return None

    if station_name not in _dwd_station_id_cache:
        try:
            global _dwd_station_list_cache
            if _dwd_station_list_cache is None:
                _dwd_station_list_cache = load_dwd_station_list(
                    WEATHER_PARAMS["air_temperature"]
                )
            stations_df = _dwd_station_list_cache
            dwd_id = find_nearest_station(coords[0], coords[1], stations_df)
            _dwd_station_id_cache[station_name] = dwd_id
        except Exception as e:
            logger.debug("No DWD station for %s: %s", station_name, e)
            return None
    else:
        dwd_id = _dwd_station_id_cache[station_name]

    # Cache full station data by DWD station ID (not by date)
    if dwd_id not in _weather_cache:
        cache_path = CACHE_DIR / f"TU_{dwd_id}.parquet"
        if cache_path.exists():
            df = pd.read_parquet(cache_path)
        else:
            try:
                df = download_station_data(WEATHER_PARAMS["air_temperature"], dwd_id)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(cache_path, index=False)
            except Exception as e:
                logger.debug("No weather data for DWD station %s: %s", dwd_id, e)
                return None
        _weather_cache[dwd_id] = df

    df = _weather_cache[dwd_id]
    match = df[(df["date"] == pd.Timestamp(query_date)) & (df["hour"] == hour)]
    if len(match) == 0:
        return None

    row = match.iloc[0]
    result = {}
    for old_col, new_col in WEATHER_PARAMS["air_temperature"]["columns"].items():
        if old_col in df.columns and pd.notna(row.get(old_col)):
            result[new_col] = row[old_col]
    return result if result else None


def compute_route_weather_features(
    route_stations: list,
    query_date,
    hour: int,
    current_station_name: str,
) -> dict:
    features = {
        "avg_temp_along_route": None,
        "max_precip_along_route": None,
        "rain_at_next_station": None,
        "weather_diff_from_origin_temp": None,
        "weather_diff_from_origin_precip": None,
        "n_stations_in_route": len(route_stations),
        "missing_weather_stations_count": 0,
    }

    temps = []
    precip = []
    origin_temp = None
    origin_precip = None
    current_temp = None
    current_precip = None
    found_current = False
    found_next = False

    for stop in route_stations:
        name = (
            stop.name
            if hasattr(stop, "name")
            else (stop if isinstance(stop, str) else "")
        )
        if not name:
            continue

        weather = _get_weather_for_station(name, query_date, hour)
        if weather is None:
            features["missing_weather_stations_count"] += 1
            continue

        if "temperature_c" in weather and weather["temperature_c"] is not None:
            temps.append(weather["temperature_c"])
        if "precipitation_mm" in weather and weather["precipitation_mm"] is not None:
            precip.append(weather["precipitation_mm"])

        if name == current_station_name:
            found_current = True
            current_temp = weather.get("temperature_c")
            current_precip = weather.get("precipitation_mm")
            if origin_temp is None and temps:
                origin_temp = temps[0]
            if origin_precip is None and precip:
                origin_precip = precip[0]

        if found_current and not found_next:
            next_precip = weather.get("precipitation_mm")
            if next_precip is not None:
                features["rain_at_next_station"] = next_precip
                found_next = True

    if temps:
        features["avg_temp_along_route"] = sum(temps) / len(temps)
    if precip:
        features["max_precip_along_route"] = max(precip)
    if origin_temp is not None and current_temp is not None:
        features["weather_diff_from_origin_temp"] = current_temp - origin_temp
    if origin_precip is not None and current_precip is not None:
        features["weather_diff_from_origin_precip"] = current_precip - origin_precip

    return features


def dry_run_estimate() -> dict:
    """Estimate how many unique intermediate stations and API calls needed."""
    logger.setLevel(logging.INFO)

    print("=" * 60)
    print("Route-Weather Dry Run: Estimating Data Volume")
    print("=" * 60)

    print(
        "\nStep 1: Counting unique (train, station, hour) combos in historical data..."
    )
    df = pd.read_sql(
        """
        SELECT DISTINCT train_number, station_name, DATE(time) as date,
               EXTRACT(HOUR FROM time AT TIME ZONE 'Europe/Berlin') as hour
        FROM train_delays
        WHERE train_type = 'ICE'
        LIMIT 100000
        """,
        engine,
    )
    total_combos = len(df)
    unique_trains = df["train_number"].nunique()
    unique_stations = df["station_name"].nunique()
    print(f"  Unique (train, station, hour) combos sampled: {total_combos:,}")
    print(f"  Unique train numbers: {unique_trains:,}")
    print(f"  Unique station names: {unique_stations:,}")

    # Estimate API calls per unique (train, station, hour)
    # But many trains share the same route for the same (station, hour) so we deduplicate
    by_train_station = df.groupby(["train_number", "station_name"]).size().reset_index()
    unique_route_combos = len(by_train_station)
    print(f"  Unique (train, station) pairs: {unique_route_combos:,}")
    print(
        f"  Est. API calls at 55/min: {unique_route_combos / 55:.1f} min (~{unique_route_combos / 55 / 60:.1f} hrs)"
    )

    print("\nStep 2: Getting route samples to discover intermediate stations...")
    route_cache = RouteCache()
    intermediate_stations = set()
    stations_with_weather = set()

    sample_size = min(50, unique_route_combos)
    sampled = by_train_station.sample(n=sample_size, random_state=42)
    resolved_count = 0
    for _, row in sampled.iterrows():
        # Convert pandas Series values to native Python types
        station_name_val = str(row["station_name"])
        train_number_val = str(row["train_number"])

        eva = resolve_eva(station_name_val)
        if eva is None:
            continue
        resolved_count += 1
        try:
            route = get_route(
                train_number=train_number_val,
                eva_number=eva,
                query_date=datetime.now().date(),
                hour=12,
                cache=route_cache,
            )
        except Exception:
            continue
        if route is None or not route.stops:
            continue
        for stop in route.stops:
            stop_name = stop.name if hasattr(stop, "name") else str(stop)
            if stop_name not in DB_STATIONS:
                intermediate_stations.add(stop_name)
            has_coords = _station_to_coords(stop_name) is not None
            if has_coords:
                stations_with_weather.add(stop_name)

    print(f"  Sampled {resolved_count} route lookups")
    all_known_coords = set(DB_STATIONS.keys()) | set(EXTRA_STATION_COORDS.keys())
    missing_coords = intermediate_stations - stations_with_weather
    new_stations = intermediate_stations - all_known_coords
    print(f"  Intermediate stations discovered: {len(intermediate_stations):,}")
    print(f"  Stations with known coordinates: {len(stations_with_weather):,}")
    print(f"  Stations needing coordinates added: {len(missing_coords):,}")
    print(f"  Stations beyond all known coords: {len(new_stations):,}")
    print(f"  Sample new: {sorted(new_stations)[:20]}")

    print("\nStep 3: Estimating DWD weather download cost...")
    avg_rows_per_station = 150_000
    new_count = len(new_stations)
    est_rows = new_count * avg_rows_per_station
    est_mb = est_rows * 8 * 8 / 1_000_000
    per_station_time = 30  # seconds
    est_time_min = new_count * per_station_time / 60

    print(f"  Estimated new DWD stations needed: ~{new_count}")
    print(f"  Estimated new weather rows: ~{est_rows:,} ({est_mb:.0f} MB)")
    print(f"  Estimated download time: ~{est_time_min:.0f} min")

    total = {
        "unique_route_combos": unique_route_combos,
        "api_calls_estimate": unique_route_combos,
        "api_time_minutes": round(unique_route_combos / 55, 1),
        "intermediate_stations_found": len(intermediate_stations),
        "new_stations_beyond_10": len(new_stations),
        "estimated_new_weather_rows": int(est_rows),
        "estimated_download_minutes": round(est_time_min, 0),
    }
    print("\n" + "=" * 60)
    print("DRY RUN SUMMARY")
    print("=" * 60)
    for k, v in total.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    return total


def build_route_weather_features(
    sample_size: Optional[int] = None,
) -> pd.DataFrame:
    print("Building route-level weather features...")
    df = pd.read_sql(
        """
        SELECT id, train_number, station_name, time,
               train_line_ride_id, train_line_station_num,
               delay_in_min
        FROM train_delays
        WHERE train_type = 'ICE'
        ORDER BY time
        """,
        engine,
        parse_dates=["time"],
    )
    if sample_size:
        df = df.sample(n=sample_size, random_state=42)
    print(f"  Loaded {len(df):,} rows")

    # Deduplicate to unique (train_number, station_name, date, hour)
    berlin_tz = "Europe/Berlin"
    df["date"] = df["time"].dt.tz_convert(berlin_tz).dt.date
    df["hour"] = df["time"].dt.tz_convert(berlin_tz).dt.hour

    # Pre-filter: skip night hours (0-5) where trains rarely run
    before = len(df)
    df = df[df["hour"].between(6, 23)]
    filtered = before - len(df)
    if filtered:
        print(
            f"  Filtered out {filtered} rows with hour 0-5 ({filtered / before * 100:.1f}%)"
        )

    unique_combos_df = (
        df[["train_number", "station_name", "date", "hour"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    unique_combos: pd.DataFrame = unique_combos_df  # Type hint for linter
    print(f"  Unique (train, station, date, hour) combos: {len(unique_combos):,}")

    route_cache = RouteCache()
    results = []

    processed = 0
    errors = 0
    ambiguous = 0
    no_route = 0

    for _, row in unique_combos.iterrows():
        # Convert pandas Series values to native Python types
        station_name_val = str(row["station_name"])
        train_number_val = str(row["train_number"])
        date_val = row["date"]
        hour_val = int(row["hour"])

        eva = resolve_eva(station_name_val)
        if eva is None:
            no_route += 1
            continue

        try:
            # Convert date to datetime.date if needed
            import datetime as dt

            if hasattr(date_val, "date"):
                date_param = date_val if isinstance(date_val, dt.date) else date_val
            else:
                date_param = date_val

            route = get_route(
                train_number=train_number_val,
                eva_number=eva,
                query_date=date_param,
                hour=hour_val,
                cache=route_cache,
            )
        except Exception as e:
            logger.warning(
                "Route fetch error for %s at %s: %s",
                train_number_val,
                station_name_val,
                e,
            )
            errors += 1
            continue

        if route is None or not route.stops:
            no_route += 1
            continue

        if route.ambiguous_match:
            ambiguous += 1

        weather_features = compute_route_weather_features(
            route.stops,
            date_val,
            hour_val,
            station_name_val,
        )

        result = {
            "train_number": train_number_val,
            "station_name": station_name_val,
            "date": date_val,
            "hour": hour_val,
            **weather_features,
            "ambiguous_match": route.ambiguous_match,
            "route_origin": route.departure_station,
            "route_destination": route.arrival_station,
        }
        results.append(result)

        processed += 1
        if processed % 100 == 0:
            print(f"  Processed {processed}/{len(unique_combos)}...")

    print(
        f"\n  Done. Processed {processed}, errors {errors}, no_route {no_route}, ambiguous {ambiguous}"
    )
    print(f"  Cache size: {route_cache.size()} entries")

    output = pd.DataFrame(results)
    return output


def merge_route_weather(
    features_df: pd.DataFrame,
    route_weather_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge route-level weather features onto the main feature DataFrame."""
    merge_cols = ["train_number", "station_name", "date", "hour"]
    route_weather_df["date"] = pd.to_datetime(route_weather_df["date"]).dt.date

    for col in merge_cols:
        if col not in features_df.columns and col != "date":
            if col == "date" and "date" not in features_df.columns:
                features_df["date"] = (
                    features_df["time"].dt.tz_convert("Europe/Berlin").dt.date
                )

    result = features_df.merge(
        route_weather_df[
            merge_cols + ROUTE_WEATHER_COLS + ["route_origin", "route_destination"]
        ],
        on=merge_cols,
        how="left",
    )
    return result


def predownload_weather_for_coords():
    """Download DWD weather for all known station coordinates (10 + extras)."""
    print("Pre-downloading DWD weather for all known stations...")
    all_coords = {}
    for name, c in DB_STATIONS.items():
        all_coords[name] = (c["lat"], c["lon"])
    all_coords.update(EXTRA_STATION_COORDS)
    global _dwd_station_list_cache
    if _dwd_station_list_cache is None:
        _dwd_station_list_cache = load_dwd_station_list(
            WEATHER_PARAMS["air_temperature"]
        )
    air_stations = _dwd_station_list_cache
    success = 0
    for name, (lat, lon) in all_coords.items():
        dwd_id = find_nearest_station(lat, lon, air_stations)
        cache_path = CACHE_DIR / f"TU_{dwd_id}.parquet"
        if cache_path.exists():
            success += 1
            continue
        try:
            df = download_station_data(WEATHER_PARAMS["air_temperature"], dwd_id)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache_path, index=False)
            success += 1
        except Exception as e:
            print(f"  Failed for {name} (DWD {dwd_id}): {e}")
    print(f"  Done: {success}/{len(all_coords)} stations cached")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    predownload_weather_for_coords()
