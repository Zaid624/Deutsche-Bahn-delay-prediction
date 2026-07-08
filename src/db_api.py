import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from typing import Optional, Union
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
_DB_TZ = "Europe/Berlin"

logger = logging.getLogger(__name__)


class DBApiError(Exception):
    pass


class AuthenticationError(DBApiError):
    pass


class NotFoundError(DBApiError):
    pass


class RateLimitError(DBApiError):
    pass


@dataclass
class RouteStop:
    name: str
    is_origin: bool = False
    is_destination: bool = False


@dataclass
class ExtractedRoute:
    train_number: str
    train_category: str
    departure_station: str
    arrival_station: str
    stops: list[RouteStop]
    ambiguous_match: bool = False
    raw_ppth_arrival: Optional[str] = None
    raw_ppth_departure: Optional[str] = None


@dataclass
class CandidateMatch:
    eva_number: str
    arrival_ppth: Optional[str]
    departure_ppth: Optional[str]
    scheduled_time: Optional[str]
    category: str
    number: str
    s_id: Optional[str] = None
    time_diff_minutes: Optional[int] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    line: Optional[str] = None

    def get_route_stops(self) -> list[str]:
        stops = []
        if self.arrival_ppth:
            stops.extend(parse_ppth(self.arrival_ppth))
        if self.departure_ppth:
            stops.extend(parse_ppth(self.departure_ppth)[1:])
        return stops


@dataclass
class RealtimeDelay:
    s_id: str
    arrival_pt: Optional[str]
    arrival_ct: Optional[str]
    departure_pt: Optional[str]
    departure_ct: Optional[str]
    arrival_pp: Optional[str] = None
    departure_pp: Optional[str] = None

    @property
    def arrival_delay_min(self) -> Optional[float]:
        if self.arrival_pt and self.arrival_ct:
            pt = datetime.strptime(self.arrival_pt, "%y%m%d%H%M")
            ct = datetime.strptime(self.arrival_ct, "%y%m%d%H%M")
            return (ct - pt).total_seconds() / 60
        return None

    @property
    def departure_delay_min(self) -> Optional[float]:
        if self.departure_pt and self.departure_ct:
            pt = datetime.strptime(self.departure_pt, "%y%m%d%H%M")
            ct = datetime.strptime(self.departure_ct, "%y%m%d%H%M")
            return (ct - pt).total_seconds() / 60
        return None

    def format_time(self, time_str: Optional[str]) -> Optional[str]:
        if not time_str:
            return None
        try:
            return datetime.strptime(time_str, "%y%m%d%H%M").strftime("%H:%M")
        except ValueError:
            return time_str

    @property
    def arrival_scheduled_time(self) -> Optional[str]:
        return self.format_time(self.arrival_pt)

    @property
    def arrival_actual_time(self) -> Optional[str]:
        return self.format_time(self.arrival_ct)

    @property
    def departure_scheduled_time(self) -> Optional[str]:
        return self.format_time(self.departure_pt)

    @property
    def departure_actual_time(self) -> Optional[str]:
        return self.format_time(self.departure_ct)


def _get_credentials() -> tuple[str, str]:
    client_id = os.getenv("DB_CLIENT_ID")
    api_key = os.getenv("DB_CLIENT_SECRET")
    if not client_id or not api_key:
        import streamlit as st
        try:
            client_id = st.secrets["DB_CLIENT_ID"]
            api_key = st.secrets["DB_CLIENT_SECRET"]
        except (KeyError, Exception):
            raise AuthenticationError(
                "DB_CLIENT_ID and DB_CLIENT_SECRET must be set in .env or Streamlit secrets"
            )
    return client_id, api_key


def _request_xml(path: str) -> ET.Element:
    client_id, api_key = _get_credentials()
    url = BASE_URL + path
    req = Request(url)
    req.add_header("DB-Client-Id", client_id)
    req.add_header("DB-Api-Key", api_key)
    try:
        with urlopen(req, timeout=15) as resp:
            return ET.fromstring(resp.read())
    except HTTPError as e:
        if e.code == 401:
            raise AuthenticationError(f"Invalid credentials (401) for {path}")
        if e.code == 403:
            raise AuthenticationError(f"Access denied (403) for {path}")
        if e.code == 404:
            raise NotFoundError(f"Resource not found: {path}")
        if e.code == 429:
            raise RateLimitError(f"Rate limit exceeded (429) for {path}")
        raise DBApiError(f"HTTP {e.code} for {path}: {e.read()[:200]}")
    except ET.ParseError as e:
        raise DBApiError(f"XML parse error for {path}: {e}")
    except URLError as e:
        raise DBApiError(f"Network error for {path}: {e}")


def get_station_plan(
    eva_number: str,
    query_date: Optional[Union[date, str]] = None,
    hour: Optional[int] = None,
) -> ET.Element:
    if query_date is None:
        query_date = date.today()
    if hour is None:
        hour = datetime.now().astimezone().__getattribute__("hour")
    if isinstance(query_date, str):
        query_date = datetime.strptime(query_date, "%Y-%m-%d").date()
    date_str = query_date.strftime("%y%m%d")
    hour_str = f"{hour:02d}"
    path = f"/plan/{eva_number}/{date_str}/{hour_str}"
    return _request_xml(path)


def get_full_changes(eva_number: str) -> ET.Element:
    return _request_xml(f"/fchg/{eva_number}")


def get_recent_changes(eva_number: str) -> ET.Element:
    return _request_xml(f"/rchg/{eva_number}")


def search_station(pattern: str) -> list[dict]:
    root = _request_xml(f"/station/{quote(pattern, safe='')}")
    stations = []
    for el in root.findall("station"):
        stations.append({
            "name": el.get("name"),
            "eva": el.get("eva"),
            "ds100": el.get("ds100"),
        })
    return stations


def parse_ppth(ppth: Optional[str]) -> list[str]:
    if not ppth:
        return []
    return [s.strip() for s in ppth.split("|") if s.strip()]


def find_tl_entries(root: ET.Element) -> list[tuple[ET.Element, ET.Element, ET.Element]]:
    results = []
    for s in root.findall("s"):
        tl = s.find("tl")
        ar = s.find("ar")
        dp = s.find("dp")
        if tl is not None:
            results.append((tl, ar, dp))
    return results


def match_train_in_plan(
    root: ET.Element,
    train_number: str,
    category: str = "ICE",
    target_hour: Optional[int] = None,
) -> list[CandidateMatch]:
    candidates = []
    for s in root.findall("s"):
        tl = s.find("tl")
        if tl is None:
            continue
        c = tl.get("c", "")
        n = tl.get("n", "")
        if c.upper() == category.upper() and n == train_number:
            ar = s.find("ar")
            dp = s.find("dp")
            scheduled_dp = dp.get("pt") if dp is not None else None
            scheduled_ar = ar.get("pt") if ar is not None else None
            scheduled_time = scheduled_dp or scheduled_ar
            candidate = CandidateMatch(
                eva_number=root.get("eva", ""),
                arrival_ppth=ar.get("ppth") if ar is not None else None,
                departure_ppth=dp.get("ppth") if dp is not None else None,
                scheduled_time=scheduled_time,
                category=c,
                number=n,
                s_id=s.get("id"),
                origin=tl.get("f"),
                destination=tl.get("t"),
                line=tl.get("l") or tl.get("fb"),
            )
            if target_hour is not None and scheduled_time:
                try:
                    sch_hour = int(scheduled_time[6:8])
                    candidate.time_diff_minutes = abs(sch_hour - target_hour)
                except (ValueError, IndexError):
                    candidate.time_diff_minutes = None
            candidates.append(candidate)

    if target_hour is not None and len(candidates) > 1:
        timed = [c for c in candidates if c.time_diff_minutes is not None]
        if timed:
            min_diff = min(c.time_diff_minutes for c in timed)
            candidates = [c for c in timed if c.time_diff_minutes == min_diff]

    return candidates


def get_realtime_delays(eva_number: str) -> dict[str, RealtimeDelay]:
    """
    Fetch real-time delay data from the DB changes API.

    Tries fchg (full daily changes) first, then falls back to rchg (recent).
    Returns a dict mapping s_id -> RealtimeDelay with actual (ct) times.
    Only returns entries that have actual changes (ct values present).
    """
    delays: dict[str, RealtimeDelay] = {}
    try:
        root = get_full_changes(eva_number)
    except NotFoundError:
        logger.info("No full changes available for EVA %s, trying recent", eva_number)
        try:
            root = get_recent_changes(eva_number)
        except NotFoundError:
            logger.info("No recent changes available for EVA %s", eva_number)
            return delays
    except Exception as e:
        logger.warning("Failed to fetch full changes for EVA %s: %s", eva_number, e)
        return delays

    try:
        for s in root.findall("s"):
            s_id = s.get("id")
            if not s_id:
                continue
            ar = s.find("ar")
            dp = s.find("dp")
            if ar is None and dp is None:
                continue
            delay = RealtimeDelay(
                s_id=s_id,
                arrival_pt=ar.get("pt") if ar is not None else None,
                arrival_ct=ar.get("ct") if ar is not None else None,
                departure_pt=dp.get("pt") if dp is not None else None,
                departure_ct=dp.get("ct") if dp is not None else None,
                arrival_pp=ar.get("pp") if ar is not None else None,
                departure_pp=dp.get("pp") if dp is not None else None,
            )
            # Only include if there's actual change data
            if delay.arrival_ct is not None or delay.departure_ct is not None:
                delays[s_id] = delay
        logger.info(
            "Loaded %d realtime delays for EVA %s", len(delays), eva_number
        )
    except NotFoundError:
        logger.info("No recent changes available for EVA %s", eva_number)
    except Exception as e:
        logger.warning("Failed to fetch realtime delays for EVA %s: %s", eva_number, e)
    return delays


def _get_station_plan_with_fallback(
    eva_number: str,
    query_date: date,
    hour: int,
    max_offset: int = 2,
) -> tuple[ET.Element, int, date]:
    """
    Try the requested date+hour, then adjacent hours on the same date.
    If all fail on the historical date, fall back to today (and adjacent
    hours), because the API only retains ~14 days of timetable data.
    ICE train routes are stable — same number = same route regardless of date.

    Returns (root_element, used_hour, used_date).
    """
    offsets = [0]
    for i in range(1, max_offset + 1):
        offsets.append(-i)
        offsets.append(i)

    # Try today first — API only keeps ~7-14 days of data.
    # Historical dates will almost always 404 for past 2024-2025 data.
    fallback_dates = [date.today(), query_date, date.today() - timedelta(days=1)]

    for fallback_date in fallback_dates:
        for offset in offsets:
            candidate_hour = hour + offset
            if candidate_hour < 0 or candidate_hour > 23:
                continue
            try:
                root = get_station_plan(eva_number, fallback_date, candidate_hour)
                return root, candidate_hour, fallback_date
            except NotFoundError:
                continue

    logger.warning(
        "No plan found for EVA %s %s hour %d (tried %d dates, ±%d hours)",
        eva_number, query_date, hour, len(fallback_dates), max_offset,
    )
    raise NotFoundError(
        f"No plan found for EVA {eva_number} {query_date} hour {hour} "
        f"(tried {len(fallback_dates)} dates, ±{max_offset} hours)"
    )


def extract_route(
    train_number: str,
    eva_number: str,
    query_date: Optional[Union[date, str]] = None,
    hour: Optional[int] = None,
    category: str = "ICE",
) -> ExtractedRoute:
    if query_date is None:
        query_date = date.today()
    if hour is None:
        hour = datetime.now().astimezone().__getattribute__("hour")
    if isinstance(query_date, str):
        query_date = datetime.strptime(query_date, "%Y-%m-%d").date()

    root, used_hour, used_date = _get_station_plan_with_fallback(eva_number, query_date, hour)
    # Only filter by target hour when on the original query date (schedule matches).
    # On fallback dates (today/yesterday), the train may run at different hours.
    target = hour if used_date == query_date else None
    candidates = match_train_in_plan(root, train_number, category, target_hour=target)

    if not candidates:
        return ExtractedRoute(
            train_number=train_number,
            train_category=category,
            departure_station="",
            arrival_station="",
            stops=[],
        )

    best = candidates[0]
    ambiguous = len(candidates) > 1

    stops_ar = parse_ppth(best.arrival_ppth)
    stops_dp = parse_ppth(best.departure_ppth)

    if stops_ar:
        origin = stops_ar[0]
        pre_stops = [RouteStop(s) for s in stops_ar[1:]]
    else:
        origin = ""
        pre_stops = []

    if stops_dp:
        destination = stops_dp[-1]
        post_stops = [RouteStop(s) for s in stops_dp[:-1]]
    else:
        destination = ""
        post_stops = []

    all_stops_in_order = [RouteStop(origin, is_origin=True)] if origin else []
    all_stops_in_order.extend(pre_stops)
    all_stops_in_order.extend(post_stops)
    if destination:
        all_stops_in_order.append(RouteStop(destination, is_destination=True))

    station_name = root.get("station", "")
    if origin and not station_name:
        pass
    elif station_name:
        if not any(s.name == station_name for s in all_stops_in_order):
            all_stops_in_order.append(RouteStop(station_name))

    origin_name = stops_ar[0] if stops_ar else (stops_dp[0] if stops_dp else "")
    dest_name = stops_dp[-1] if stops_dp else (stops_ar[-1] if stops_ar else "")

    return ExtractedRoute(
        train_number=train_number,
        train_category=category,
        departure_station=origin_name,
        arrival_station=dest_name,
        stops=all_stops_in_order,
        ambiguous_match=ambiguous,
        raw_ppth_arrival=best.arrival_ppth,
        raw_ppth_departure=best.departure_ppth,
    )
