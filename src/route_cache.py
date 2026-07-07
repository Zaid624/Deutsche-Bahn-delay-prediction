"""
SQLite-backed route cache with token-bucket rate limiter.

Cache choice: SQLite over JSON because:
- We need fast key lookups across millions of historical rows. SQLite
  indexes give O(log n) lookups vs O(n) scan for a JSON file.
- Incremental writes: each cache miss adds one row; with JSON we'd
  rewrite the entire file on every update.
- Built into Python stdlib — zero dependencies.

Rate limiter: Token-bucket with 55 tokens/min (5 under the 60 limit as
headroom). This avoids bursty 429 responses from the DB API.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path
from typing import Optional

from src.db_api import ExtractedRoute, RouteStop

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/route_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "routes.sqlite"

# Rate limiter settings
TOKENS_PER_MINUTE = 55
REFILL_INTERVAL = 60.0 / TOKENS_PER_MINUTE  # seconds between tokens


class RateLimiter:
    """Token-bucket rate limiter. Thread-safe."""

    def __init__(self, tokens_per_minute: int = TOKENS_PER_MINUTE):
        self.max_tokens = tokens_per_minute
        self.tokens = float(tokens_per_minute)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.max_tokens, self.tokens + elapsed * self.max_tokens / 60.0
        )
        self.last_refill = now

    def acquire(self, block: bool = True) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            if not block:
                return False
            sleep_time = REFILL_INTERVAL
            logger.debug("Rate limit hit, sleeping %.2fs", sleep_time)
            time.sleep(sleep_time)
            self.tokens = self.max_tokens - 1.0
            self.last_refill = time.monotonic()
            return True


# Global rate limiter instance
_limiter = RateLimiter()


class RouteCache:
    """SQLite cache for route data. Thread-safe via SQLite WAL mode."""

    def __init__(self, db_path: Path = CACHE_DB):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=10)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._init_db()
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                cache_key TEXT PRIMARY KEY,
                train_number TEXT NOT NULL,
                eva_number TEXT NOT NULL,
                date TEXT NOT NULL,
                hour INTEGER NOT NULL,
                departure_station TEXT,
                arrival_station TEXT,
                stops_json TEXT,
                ambiguous_match INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_routes_lookup
            ON routes(train_number, eva_number, date, hour)
        """)
        conn.commit()

    @staticmethod
    def _make_key(
        train_number: str, eva_number: str, query_date: str, hour: int
    ) -> str:
        return f"{train_number}|{eva_number}|{query_date}|{hour}"

    def get(
        self, train_number: str, eva_number: str, query_date: str, hour: int
    ) -> Optional[ExtractedRoute]:
        key = self._make_key(train_number, eva_number, query_date, hour)
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT stops_json, departure_station, arrival_station, ambiguous_match FROM routes WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        stops_json, dep, arr, ambiguous = row
        stops_list = json.loads(stops_json) if stops_json else []
        stops = []
        for s in stops_list:
            if isinstance(s, dict):
                stops.append(RouteStop(**s))
            elif isinstance(s, (list, tuple)):
                # Handle legacy format: [name, is_origin, is_destination]
                name = s[0]
                is_origin = s[1] if len(s) > 1 else False
                is_destination = s[2] if len(s) > 2 else False
                stops.append(RouteStop(name, is_origin, is_destination))
            else:
                stops.append(RouteStop(s))
        return ExtractedRoute(
            train_number=train_number,
            train_category="",
            departure_station=dep or "",
            arrival_station=arr or "",
            stops=stops,
            ambiguous_match=bool(ambiguous),
        )

    def put(
        self,
        train_number: str,
        eva_number: str,
        query_date: str,
        hour: int,
        route: ExtractedRoute,
    ):
        key = self._make_key(train_number, eva_number, query_date, hour)
        stops_json = json.dumps(
            [
                {
                    "name": s.name,
                    "is_origin": s.is_origin,
                    "is_destination": s.is_destination,
                }
                for s in route.stops
            ]
        )
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR REPLACE INTO routes
                   (cache_key, train_number, eva_number, date, hour,
                    departure_station, arrival_station, stops_json, ambiguous_match)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    key,
                    train_number,
                    eva_number,
                    query_date,
                    hour,
                    route.departure_station,
                    route.arrival_station,
                    stops_json,
                    int(route.ambiguous_match),
                ),
            )
            conn.commit()

    def size(self) -> int:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT COUNT(*) FROM routes").fetchone()
            return row[0] if row else 0

    def stats(self) -> dict:
        with self._lock:
            conn = self._get_conn()
            total = conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
            ambiguous = conn.execute(
                "SELECT COUNT(*) FROM routes WHERE ambiguous_match = 1"
            ).fetchone()[0]
            return {"total": total, "ambiguous": ambiguous}


def get_route(
    train_number: str,
    eva_number: str,
    query_date: date,
    hour: int,
    cache: Optional[RouteCache] = None,
) -> Optional[ExtractedRoute]:
    if cache is None:
        cache = RouteCache()
    date_str = query_date.isoformat()

    cached = cache.get(train_number, eva_number, date_str, hour)
    if cached is not None:
        return cached

    # Cache miss — acquire rate limiter token, then call API
    _limiter.acquire(block=True)

    from src.db_api import extract_route as _api_extract_route

    try:
        route = _api_extract_route(
            train_number=train_number,
            eva_number=eva_number,
            query_date=query_date,
            hour=hour,
        )
    except Exception as e:
        logger.warning(
            "Route fetch failed for %s at EVA %s %sT%02d: %s",
            train_number,
            eva_number,
            date_str,
            hour,
            e,
        )
        return None

    cache.put(train_number, eva_number, date_str, hour, route)
    return route
