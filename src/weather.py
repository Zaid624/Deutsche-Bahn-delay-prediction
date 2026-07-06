"""
Download and cache DWD (Deutscher Wetterdienst) open weather data.

Downloads hourly observations from DWD's CDC (Climate Data Center) open
data server for the nearest weather station to each of our 10 DB train
stations. Data is cached locally as parquet files to avoid re-downloading.

Data source: https://opendata.dwd.de/ (free, no API key needed)
License: CC BY 4.0 (must credit DWD)
"""

import io
import zipfile
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

CACHE_DIR = Path("data/weather_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Our delay data covers 2024-07 through 2025-11
DELAY_START = "2024-07-01"
DELAY_END = "2025-11-30"

# Our DB train stations with approximate coordinates
DB_STATIONS = {
    "Frankfurt (Main) Hbf": {"lat": 50.107, "lon": 8.662},
    "Berlin Hauptbahnhof": {"lat": 52.525, "lon": 13.369},
    "München Hbf": {"lat": 48.140, "lon": 11.555},
    "Hannover Hbf": {"lat": 52.376, "lon": 9.742},
    "Hamburg Hbf": {"lat": 53.553, "lon": 10.006},
    "Nürnberg Hbf": {"lat": 49.446, "lon": 11.082},
    "Berlin-Spandau": {"lat": 52.530, "lon": 13.197},
    "Köln Hbf": {"lat": 50.943, "lon": 6.959},
    "Kassel-Wilhelmshöhe": {"lat": 51.313, "lon": 9.448},
    "Düsseldorf Hbf": {"lat": 51.221, "lon": 6.793},
}

# DWD base URL for hourly climate observations
DWD_BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly"

# Weather parameters we want to download
WEATHER_PARAMS = {
    "air_temperature": {
        "folder": "air_temperature",
        "code": "TU",
        "columns": {
            "TT_TU": "temperature_c",
            "RF_TU": "humidity_pct",
        },
        "description": "Temperature and humidity at 2m height",
    },
    "precipitation": {
        "folder": "precipitation",
        "code": "RR",
        "columns": {
            "R1": "precipitation_mm",
        },
        "description": "Hourly precipitation height",
    },
    "wind": {
        "folder": "wind",
        "code": "FF",
        "columns": {
            "F": "wind_speed_ms",
            "D": "wind_direction",
        },
        "description": "Wind speed and direction",
    },
    "sun": {
        "folder": "sun",
        "code": "SD",
        "columns": {
            "SD_SO": "sunshine_minutes",
        },
        "description": "Sunshine duration",
    },
    "cloudiness": {
        "folder": "cloudiness",
        "code": "N",
        "columns": {
            "V_N": "cloud_cover_pct",
        },
        "description": "Total cloud cover",
    },
    "pressure": {
        "folder": "pressure",
        "code": "P0",
        "columns": {
            "P": "pressure_hpa",
        },
        "description": "Station pressure",
    },
}


def load_dwd_station_list(param_info: dict) -> pd.DataFrame:
    """
    Download the station description file for a given parameter.
    DWD uses a fixed-width format; pandas infers column boundaries.
    """
    folder = param_info["folder"]
    code = param_info["code"]
    url = f"{DWD_BASE}/{folder}/historical/{code}_Stundenwerte_Beschreibung_Stationen.txt"
    print(f"  Downloading station list from {url}")

    col_names = ["station_id", "von_datum", "bis_datum", "height",
                 "latitude", "longitude", "name", "state", "abgabe"]

    df = pd.read_fwf(
        url, encoding="latin1", skiprows=[0, 1], header=None,
        names=col_names, na_values=["-999"],
    )
    df = df.dropna(subset=["station_id"])
    df["station_id"] = df["station_id"].astype(str).str.strip()
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    return df


def find_nearest_station(lat: float, lon: float, stations_df: pd.DataFrame) -> str:
    """
    Find the station ID of the nearest weather station that has recent data
    covering our target period (2024-07 to 2025-11).
    Prefers stations with data extending into our target range over closer
    stations that were decommissioned earlier.
    """
    stations_df = stations_df.dropna(subset=["latitude", "longitude", "bis_datum"])
    # Keep only stations with data up to at least 2024
    recent = stations_df[stations_df["bis_datum"].astype(str).str[:4] >= "2024"].copy()
    if len(recent) == 0:
        recent = stations_df  # fallback

    # Calculate distance and prefer stations that cover our full delay date range
    dlat = recent["latitude"] - lat
    dlon = recent["longitude"] - lon
    recent["dist_deg"] = (dlat ** 2 + dlon ** 2) ** 0.5

    # Add a penalty to stations whose bis_datum ends before our target end
    # This pushes us toward stations that cover the full period
    recent["bis_numeric"] = pd.to_numeric(recent["bis_datum"], errors="coerce")
    target_end = 20251130
    # Stations that don't cover our full range get a distance penalty
    recent["penalty"] = ((target_end - recent["bis_numeric"]).clip(lower=0) / 100000) * 2.0
    recent["score"] = recent["dist_deg"] + recent["penalty"]

    idx = recent["score"].idxmin()
    nearest = recent.loc[idx]
    sid = str(int(nearest["station_id"]))
    return sid.zfill(5)  # DWD uses 5-digit IDs with leading zeros


def get_station_file_url(param_info: dict, station_id: str, subdir: str = "historical") -> str:
    """
    Build the URL for the zip file for a given station, parameter, and subdirectory.
    Subdir can be 'historical' or 'recent'.
    """
    import re
    from html.parser import HTMLParser

    class LinkParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                for name, val in attrs:
                    if name == "href":
                        self.links.append(val)

    folder = param_info["folder"]
    code = param_info["code"]
    base_url = f"{DWD_BASE}/{folder}/{subdir}/"
    with urlopen(base_url) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    parser = LinkParser()
    parser.feed(html)

    # Find zip file matching our station
    # Recent files use format: stundenwerte_{code}_{station_id}_akt.zip
    # Historical files use format: stundenwerte_{code}_{station_id}_dates_hist.zip
    if subdir == "recent":
        pattern = re.compile(rf"stundenwerte_{code}_{station_id}_akt\.zip")
    else:
        pattern = re.compile(rf"stundenwerte_{code}_{station_id}_.*\.zip")
    for link in parser.links:
        if pattern.match(link):
            return base_url + link

    raise FileNotFoundError(
        f"No data file found for station {station_id}, param {folder} ({code}) in {subdir}/"
    )


def _parse_zip_file(zf: zipfile.ZipFile, station_id: str) -> pd.DataFrame:
    """Find and parse the product CSV from a DWD zip archive."""
    csv_files = [f for f in zf.namelist() if f.endswith(".txt") or f.endswith(".csv")]
    csv_files = [f for f in csv_files if "produkt" in f.lower()]
    if not csv_files:
        csv_files = [f for f in zf.namelist() if f.endswith(".txt") or f.endswith(".csv")]
        csv_files = [f for f in csv_files if not f.startswith("Metadaten")]
    if not csv_files:
        raise FileNotFoundError(f"No data file found in zip for station {station_id}")
    csv_file = csv_files[0]
    with zf.open(csv_file) as f:
        df = pd.read_csv(f, sep=";", encoding="latin1", na_values=["-999", "-999.0"])

    # Strip whitespace from ALL column names (DWD headers have leading spaces)
    df.columns = df.columns.str.strip()

    # Parse date from MESS_DATUM (format: YYYYMMDDHH)
    dt_col = "MESS_DATUM" if "MESS_DATUM" in df.columns else None
    if dt_col is None:
        date_cols = [c for c in df.columns if "ende" in c.lower() or "zeit" in c.lower()]
        dt_col = date_cols[0] if date_cols else df.columns[1]

    df[dt_col] = df[dt_col].astype(str).str.strip()
    df["date"] = pd.to_datetime(df[dt_col].str[:8], format="%Y%m%d", errors="coerce")
    df["hour"] = df[dt_col].str[8:10].astype(int)
    return df


def _download_zip_and_parse(url: str, station_id: str) -> pd.DataFrame:
    """Download a zip file and parse its contents."""
    print(f"    Downloading {url.split('/')[-1]}")
    with urlopen(url) as resp:
        zip_bytes = resp.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return _parse_zip_file(zf, station_id)


def download_station_data(param_info: dict, station_id: str) -> pd.DataFrame:
    """
    Download and parse hourly weather data for a given station and parameter.
    Checks both 'historical' and 'recent' directories and concatenates them.
    Returns a DataFrame with date, hour, and weather measurements.
    """
    folder = param_info["folder"]
    code = param_info["code"]

    # Download from historical directory
    historical_url = get_station_file_url(param_info, station_id)
    df_hist = _download_zip_and_parse(historical_url, station_id)

    # Optionally download from 'recent' directory (covers last ~2 years)
    recent_url = None
    try:
        recent_url = get_station_file_url(param_info, station_id, subdir="recent")
        df_recent = _download_zip_and_parse(recent_url, station_id)
        # Concatenate, keeping the latest value for each (date, hour)
        combined = pd.concat([df_hist, df_recent], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "hour"], keep="last")
        combined = combined.sort_values(["date", "hour"]).reset_index(drop=True)
        return combined
    except (FileNotFoundError, Exception):
        pass  # No recent data available, use historical only

    return df_hist


def download_all_weather() -> pd.DataFrame:
    """
    Download and merge weather data for all our DB stations.
    Returns a DataFrame with columns: station_name, date, hour, and weather measurements.
    """
    all_weather = []

    for db_name, coords in DB_STATIONS.items():
        print(f"\nProcessing weather for {db_name} ...")

        station_weather = None

        for param_name, param_info in WEATHER_PARAMS.items():
            param_code = param_info["code"]

            # Check cache first
            cache_path = CACHE_DIR / f"{param_code}_{coords['lat']}_{coords['lon']}.parquet"
            if cache_path.exists():
                df_param = pd.read_parquet(cache_path)
                print(f"  Cached {param_name} ({len(df_param)} rows)")
            else:
                try:
                    stations_df = load_dwd_station_list(param_info)
                    station_id = find_nearest_station(coords["lat"], coords["lon"], stations_df)
                    df_param = download_station_data(param_info, station_id)
                except Exception as e:
                    print(f"  Failed for nearest station {station_id}: {e}")
                    # Try nearby stations in order of distance
                    stations_df = stations_df.dropna(subset=["latitude", "longitude", "bis_datum"])
                    recent = stations_df[stations_df["bis_datum"].astype(str).str[:4] >= "2024"].copy()
                    if len(recent) > 0:
                        dlat = recent["latitude"] - coords["lat"]
                        dlon = recent["longitude"] - coords["lon"]
                        recent["dist"] = (dlat ** 2 + dlon ** 2) ** 0.5
                        candidates = recent.sort_values("dist")
                        for _, row in candidates.iterrows():
                            sid = str(int(row["station_id"])).zfill(5)
                            if sid == station_id:
                                continue
                            try:
                                df_param = download_station_data(param_info, sid)
                                print(f"  Using fallback station {sid} ({row['name']})")
                                break
                            except Exception:
                                continue
                        else:
                            print(f"  No fallback station found for {param_name}")
                            continue
                    else:
                        continue

                # Rename columns
                col_map = {}
                for old_col, new_col in param_info["columns"].items():
                    if old_col in df_param.columns:
                        col_map[old_col] = new_col
                df_param = df_param.rename(columns=col_map)

                # Keep only what we need
                keep_cols = ["date", "hour"] + list(col_map.values())
                df_param = df_param[[c for c in keep_cols if c in df_param.columns]]
                df_param.to_parquet(cache_path, index=False)
                print(f"  Downloaded {param_name} ({len(df_param)} rows) -> cached")

            # Merge into station-level dataframe (outer join to keep all data)
            if station_weather is None:
                station_weather = df_param
            else:
                station_weather = station_weather.merge(
                    df_param, on=["date", "hour"], how="outer"
                )

        if station_weather is not None:
            station_weather["station_name"] = db_name
            # Filter to our delay data date range
            station_weather = station_weather[
                (station_weather["date"] >= pd.Timestamp(DELAY_START))
                & (station_weather["date"] <= pd.Timestamp(DELAY_END))
            ]
            # Forward-fill weather values within each day (weather changes slowly)
            station_weather = station_weather.sort_values(["date", "hour"])
            weather_cols = [c for c in station_weather.columns if c not in ("date", "hour", "station_name")]
            station_weather[weather_cols] = station_weather.groupby("date")[weather_cols].transform(lambda g: g.ffill())
            all_weather.append(station_weather)

    if not all_weather:
        raise RuntimeError("No weather data downloaded for any station!")

    result = pd.concat(all_weather, ignore_index=True)
    # Drop rows without a valid date
    result = result.dropna(subset=["date"])
    result["date"] = result["date"].dt.date

    print(f"\nTotal weather records: {len(result):,}")
    print(f"Columns: {list(result.columns)}")

    return result


def get_weather_data() -> pd.DataFrame:
    """
    Public entry point: download (or load cached) weather data for all stations.
    """
    cache_all = CACHE_DIR / "all_weather.parquet"
    if cache_all.exists():
        print(f"Loading cached weather data from {cache_all}")
        return pd.read_parquet(cache_all)
    df = download_all_weather()
    df.to_parquet(cache_all, index=False)
    print(f"Cached merged weather to {cache_all}")
    return df


if __name__ == "__main__":
    df = get_weather_data()
    print(df.head(10).to_string())
    print(df.describe())
