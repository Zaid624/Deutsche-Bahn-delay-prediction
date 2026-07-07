import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from src.db_api import search_station, NotFoundError, DBApiError

logger = logging.getLogger(__name__)

# Known EVA numbers for our 10 DB stations (verified via DB API)
# Format: canonical_name -> eva_number
KNOWN_STATIONS: dict[str, str] = {
    "Frankfurt (Main) Hbf": "8000105",
    "Frankfurt Hbf": "8000105",
    "Frankfurt(Main)Hbf": "8000105",
    "Berlin Hauptbahnhof": "8011160",
    "Berlin Hbf": "8011160",
    "Berlin Hbf (tief)": "8011160",
    "München Hbf": "8000261",
    "München Hbf": "8000261",
    "Hannover Hbf": "8000152",
    "Hamburg Hbf": "8002549",
    "Nürnberg Hbf": "8000284",
    "Nürnberg Hbf": "8000284",
    "Berlin-Spandau": "8089020",
    "Köln Hbf": "8000207",
    "Köln Hbf": "8000207",
    "Kassel-Wilhelmshöhe": "8000254",
    "Düsseldorf Hbf": "8000085",
    "Düsseldorf Hbf": "8000085",
}

# Name normalizations: strip parenthetical suffixes and common variants
_REMOVE_PARENS = re.compile(r"\s*\(.*?\)\s*")
_REMOVE_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                                  "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})


def normalize_station_name(name: str) -> str:
    name = _REMOVE_PARENS.sub(" ", name).strip()
    name = name.translate(_REMOVE_UMLAUTS)
    name = re.sub(r"\s+", " ", name)
    return name


# Build normalized -> eva lookup
_NORMALIZED: dict[str, str] = {}
for raw_name, eva in KNOWN_STATIONS.items():
    norm = normalize_station_name(raw_name)
    _NORMALIZED[norm] = eva


# Cache for API-fetched stations
_api_cache: dict[str, str] = {}
_api_cache_path = Path("data/eva_cache.parquet")


def _load_api_cache():
    global _api_cache
    if _api_cache_path.exists():
        try:
            df = pd.read_parquet(_api_cache_path)
            _api_cache = dict(zip(df["name"], df["eva"]))
            logger.info("Loaded %d EVA entries from %s", len(_api_cache), _api_cache_path)
        except Exception as e:
            logger.warning("Failed to load EVA cache: %s", e)


def _save_api_cache():
    _api_cache_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(list(_api_cache.items()), columns=["name", "eva"])
    df.to_parquet(_api_cache_path, index=False)
    logger.info("Saved %d EVA entries to %s", len(df), _api_cache_path)


def resolve_eva(station_name: str) -> Optional[str]:
    # 1. Direct lookup in known stations
    if station_name in KNOWN_STATIONS:
        return KNOWN_STATIONS[station_name]

    # 2. Normalized lookup
    norm = normalize_station_name(station_name)
    if norm in _NORMALIZED:
        return _NORMALIZED[norm]

    # 3. Check API cache
    _load_api_cache()
    if station_name in _api_cache:
        return _api_cache[station_name]

    # 4. Try API lookup
    try:
        results = search_station(station_name)
    except (NotFoundError, DBApiError) as e:
        logger.warning("API lookup failed for '%s': %s", station_name, e)
        return None

    if not results:
        logger.warning("No EVA found for station '%s'", station_name)
        return None

    # Try exact name match first
    for r in results:
        if r["name"].lower() == station_name.lower():
            _api_cache[station_name] = r["eva"]
            _save_api_cache()
            return r["eva"]

    # Fall back to first result
    best = results[0]
    logger.info(
        "Fuzzy match for '%s' -> '%s' (EVA %s)",
        station_name, best["name"], best["eva"],
    )
    _api_cache[station_name] = best["eva"]
    _save_api_cache()
    return best["eva"]


def batch_resolve_eva(station_names: list[str]) -> dict[str, Optional[str]]:
    results = {}
    for name in station_names:
        if name not in results:
            results[name] = resolve_eva(name)
    return results


def get_station_name_variants(station_name: str) -> list[str]:
    variants = [station_name]
    norm = normalize_station_name(station_name)
    if norm != station_name:
        variants.append(norm)
    no_parens = _REMOVE_PARENS.sub(" ", station_name).strip()
    if no_parens != station_name and no_parens != norm:
        variants.append(no_parens)
    return variants
