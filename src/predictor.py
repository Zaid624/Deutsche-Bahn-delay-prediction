"""
Real-time delay prediction service.

Handles:
1. Fetching live train data from DB Timetables API
2. Engineering features matching training format
3. Making predictions with trained model
4. Logging predictions to database for monitoring
"""

import json
import logging
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# Suppress sklearn OneHotEncoder warning about unknown categories during transform
# prev_delayed can be -1 (unknown) which may not have been in the training split
warnings.filterwarnings("ignore", message="Found unknown categories", category=UserWarning)

import joblib
import pandas as pd
from sqlalchemy import text

from src.database import engine
from src.db_api import (
    RealtimeDelay,
    get_realtime_delays,
    get_station_plan,
    match_train_in_plan,
    find_tl_entries,
    _get_station_plan_with_fallback,
)
from src.eva_lookup import resolve_eva

logger = logging.getLogger(__name__)


class DelayPredictor:
    """Real-time train delay predictor."""

    def __init__(self, model_path: str = "models/xgb_weather.joblib"):
        """
        Initialize predictor with trained model.

        Args:
            model_path: Path to saved model file
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        logger.info("Loading model from %s", self.model_path)
        self.model = joblib.load(self.model_path)
        logger.info("Model loaded: %s", type(self.model).__name__)

        # Load historical statistics for features
        self._load_historical_stats()

    def _load_historical_stats(self):
        """Load precomputed historical statistics from database."""
        try:
            # Load historical delay rates
            query = """
            SELECT station_name,
                   EXTRACT(HOUR FROM time AT TIME ZONE 'Europe/Berlin') as hour,
                   EXTRACT(DOW FROM time AT TIME ZONE 'Europe/Berlin') as day_of_week,
                   AVG(CASE WHEN delay_in_min > 5 THEN 1 ELSE 0 END) as delay_rate,
                   COUNT(*) as train_count
            FROM train_delays
            GROUP BY station_name, hour, day_of_week
            """
            self.hist_stats = pd.read_sql(query, engine)
            logger.info(
                "Loaded historical stats for %d combinations", len(self.hist_stats)
            )

            # Compute global mean delay rate as fallback
            self.global_delay_rate = self.hist_stats["delay_rate"].mean()
            logger.info("Global delay rate: %.2f%%", self.global_delay_rate * 100)

        except Exception as e:
            logger.warning("Failed to load historical stats: %s", e)
            self.hist_stats = pd.DataFrame()
            self.global_delay_rate = 0.30  # Fallback: 30% delay rate

    def get_available_trains(
        self,
        station_name: str,
        query_date: Optional[date] = None,
        hour: Optional[int] = None,
    ) -> list[str]:
        """
        Fetch list of real ICE train numbers for a station/time from DB Timetables API.

        Args:
            station_name: Station name
            query_date: Date (default: today)
            hour: Hour (default: current hour)

        Returns:
            Sorted list of ICE train numbers at this station for the given time
        """
        eva = resolve_eva(station_name)
        if not eva:
            return []

        if query_date is None:
            query_date = date.today()
        if hour is None:
            hour = datetime.now().hour

        try:
            root, used_hour, used_date = _get_station_plan_with_fallback(
                eva, query_date, hour
            )
            trains: set[str] = set()
            for tl, ar, dp in find_tl_entries(root):
                c = tl.get("c", "")
                n = tl.get("n", "")
                if c.upper() == "ICE":
                    trains.add(n)
            return sorted(trains, key=int)
        except Exception as e:
            logger.warning("Failed to fetch train list for %s: %s", station_name, e)
            return []

    def fetch_live_data(
        self,
        station_name: str,
        train_number: str,
        query_date: Optional[date] = None,
        hour: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Fetch live train data from DB Timetables API.

        Args:
            station_name: Station name (e.g., "Frankfurt (Main) Hbf")
            train_number: Train number (e.g., "123")
            query_date: Date to query (default: today)
            hour: Hour to query (default: current hour)

        Returns:
            Dictionary with live train data, or None if not found
        """
        # Resolve EVA number
        eva = resolve_eva(station_name)
        if not eva:
            logger.error("Could not resolve EVA for station: %s", station_name)
            return None

        # Default to current date/time
        if query_date is None:
            query_date = date.today()
        if hour is None:
            hour = datetime.now().hour

        logger.info(
            "Fetching data for train %s at %s on %s %02d:00",
            train_number,
            station_name,
            query_date,
            hour,
        )

        try:
            # Fetch timetable plan with fallback (tries today and adjacent hours)
            root, used_hour, used_date = _get_station_plan_with_fallback(
                eva, query_date, hour
            )

            # Only filter by target hour when on the original query date
            target = hour if used_date == query_date else None
            candidates = match_train_in_plan(
                root, train_number, category="ICE", target_hour=target
            )

            if not candidates:
                logger.warning("Train %s not found in plan", train_number)
                return None

            # Use first candidate (most likely match)
            match = candidates[0]

            def fmt_time(t: Optional[str]) -> Optional[str]:
                if not t:
                    return None
                try:
                    return datetime.strptime(t, "%y%m%d%H%M").strftime("%H:%M")
                except ValueError:
                    return t

            result = {
                "station_name": station_name,
                "train_number": train_number,
                "train_type": "ICE",
                "query_date": query_date,
                "hour": hour,
                "scheduled_time": match.scheduled_time,
                "scheduled_time_display": fmt_time(match.scheduled_time),
                "eva_number": eva,
                "ambiguous": len(candidates) > 1,
                "s_id": match.s_id,
                "origin": match.origin,
                "destination": match.destination,
                "line": match.line,
                "route_stops": match.get_route_stops(),
                "actual_arrival_delay_min": None,
                "actual_departure_delay_min": None,
                "actual_arrival_time": None,
                "actual_departure_time": None,
                "arrival_platform": None,
                "departure_platform": None,
                "has_realtime_data": False,
            }

            # Fetch real-time delays and merge
            realtime_delays = get_realtime_delays(eva)
            if match.s_id and match.s_id in realtime_delays:
                rt = realtime_delays[match.s_id]
                result["actual_arrival_delay_min"] = rt.arrival_delay_min
                result["actual_departure_delay_min"] = rt.departure_delay_min
                result["actual_arrival_time"] = rt.arrival_actual_time
                result["actual_departure_time"] = rt.departure_actual_time
                result["arrival_platform"] = rt.arrival_pp
                result["departure_platform"] = rt.departure_pp
                result["has_realtime_data"] = True
                logger.info(
                    "Realtime delay for ICE %s at %s: arrival=%s min, departure=%s min",
                    train_number, station_name,
                    rt.arrival_delay_min, rt.departure_delay_min,
                )

            return result

        except Exception as e:
            logger.error("Failed to fetch live data: %s", e)
            return None

    def engineer_features(
        self,
        live_data: dict,
        weather_data: Optional[dict] = None,
    ) -> pd.DataFrame:
        """
        Engineer features from live data matching training format.

        Args:
            live_data: Dictionary from fetch_live_data()
            weather_data: Optional weather data (if available)

        Returns:
            DataFrame with single row containing all features
        """
        station_name = live_data["station_name"]
        hour = live_data["hour"]
        query_date = live_data["query_date"]

        # Create timestamp for feature engineering
        timestamp = pd.Timestamp(
            year=query_date.year,
            month=query_date.month,
            day=query_date.day,
            hour=hour,
            tz="Europe/Berlin",
        )

        features = {
            "station_name": station_name,
            "train_type": live_data["train_type"],
            "train_number": live_data["train_number"],
            "hour": hour,
            "day_of_week": timestamp.dayofweek,
            "month": timestamp.month,
            "is_weekend": int(timestamp.dayofweek >= 5),
            "is_rush_hour": int((7 <= hour <= 9) or (16 <= hour <= 19)),
        }

        # Season
        if timestamp.month in (12, 1, 2):
            features["season"] = "winter"
        elif timestamp.month in (3, 4, 5):
            features["season"] = "spring"
        elif timestamp.month in (6, 7, 8):
            features["season"] = "summer"
        else:
            features["season"] = "autumn"

        # German public holidays
        try:
            import holidays  # type: ignore

            de_holidays = holidays.country_holidays("DE", years=timestamp.year)
            features["is_holiday"] = int(timestamp.date() in de_holidays)
        except ImportError:
            features["is_holiday"] = 0

        # Historical delay rate for (station, hour, day_of_week)
        hist_match = self.hist_stats[
            (self.hist_stats["station_name"] == station_name)
            & (self.hist_stats["hour"] == hour)
            & (self.hist_stats["day_of_week"] == timestamp.dayofweek)
        ]

        if len(hist_match) > 0:
            features["hist_delay_rate"] = hist_match.iloc[0]["delay_rate"]
            features["train_count"] = hist_match.iloc[0]["train_count"]
        else:
            features["hist_delay_rate"] = self.global_delay_rate
            features["train_count"] = 50  # Reasonable default

        # Cascading delay features from real-time data
        # If the train actually arrived late, that delay cascaded from the prev segment
        actual_arrival = live_data.get("actual_arrival_delay_min")
        if actual_arrival is not None:
            features["prev_delay_min"] = max(0.0, actual_arrival)
            features["prev_delayed"] = int(actual_arrival > 5)
            features["is_first_stop"] = 0  # Not first stop (has arrival data)
        else:
            # No real-time data — conservative defaults
            features["prev_delay_min"] = 0.0
            features["prev_delayed"] = -1  # -1 = unknown
            features["is_first_stop"] = 1

        # Planned dwell time from real-time data (pt difference)
        actual_depart = live_data.get("actual_departure_delay_min")
        if actual_arrival is not None and actual_depart is not None:
            dwell = actual_depart - actual_arrival
            features["planned_dwell_minutes"] = max(0.0, dwell)
            features["has_planned_times"] = 1
        else:
            features["planned_dwell_minutes"] = -1
            features["has_planned_times"] = 0

        # Weather features (if available)
        if weather_data:
            for key, value in weather_data.items():
                features[key] = value
        else:
            # Set weather to None (XGBoost handles missing values)
            weather_cols = [
                "temperature_c",
                "humidity_pct",
                "precipitation_mm",
                "wind_speed_ms",
                "wind_direction",
                "sunshine_minutes",
                "cloud_cover_pct",
                "pressure_hpa",
            ]
            for col in weather_cols:
                features[col] = None

        return pd.DataFrame([features])

    def predict(self, features: pd.DataFrame) -> dict:
        """
        Make delay prediction.

        Args:
            features: DataFrame with single row of features

        Returns:
            Dictionary with prediction results
        """
        try:
            # Get probability
            proba = self.model.predict_proba(features)[0]
            prob_delayed = float(proba[1])

            # Binary prediction
            delayed = prob_delayed > 0.5

            # Confidence (distance from 0.5)
            confidence_score = abs(prob_delayed - 0.5) * 2  # 0 to 1 scale
            if confidence_score > 0.7:
                confidence = "high"
            elif confidence_score > 0.4:
                confidence = "medium"
            else:
                confidence = "low"

            return {
                "delayed": bool(delayed),
                "probability": prob_delayed,
                "confidence": confidence,
                "confidence_score": confidence_score,
            }

        except Exception as e:
            logger.error("Prediction failed: %s", e)
            return {
                "delayed": None,
                "probability": None,
                "confidence": "error",
                "confidence_score": 0.0,
                "error": str(e),
            }

    def log_prediction(
        self,
        live_data: dict,
        features: pd.DataFrame,
        prediction: dict,
    ):
        """
        Log prediction to live_predictions table for monitoring.

        Args:
            live_data: Original live data dict
            features: Features used for prediction
            prediction: Prediction results dict
        """
        try:
            record = {
                "created_at": datetime.now(),
                "station_name": live_data["station_name"],
                "train_type": live_data["train_type"],
                "train_number": live_data["train_number"],
                "line_number": None,  # Not available from API
                "predicted_delay": prediction.get("delayed"),
                "predicted_prob": prediction.get("probability"),
                "features_used": json.dumps(features.iloc[0].to_dict(), default=str),
                "actual_delay": None,  # To be backfilled later
                "actual_delay_in_min": None,
            }

            df = pd.DataFrame([record])
            df.to_sql("live_predictions", engine, if_exists="append", index=False)
            logger.info("Logged prediction for train %s", live_data["train_number"])

        except Exception as e:
            logger.error("Failed to log prediction: %s", e)

    def get_recent_predictions(self, limit: int = 20) -> pd.DataFrame:
        """
        Retrieve recent predictions from database.

        Args:
            limit: Number of recent predictions to fetch

        Returns:
            DataFrame with recent predictions
        """
        try:
            query = f"""
            SELECT
                created_at,
                station_name,
                train_number,
                predicted_delay,
                predicted_prob,
                actual_delay
            FROM live_predictions
            ORDER BY created_at DESC
            LIMIT {limit}
            """
            return pd.read_sql(query, engine)
        except Exception as e:
            logger.error("Failed to fetch predictions: %s", e)
            return pd.DataFrame()

    def predict_and_log(
        self,
        station_name: str,
        train_number: str,
        query_date: Optional[date] = None,
        hour: Optional[int] = None,
    ) -> dict:
        """
        Complete prediction pipeline: fetch → engineer → predict → log.

        Args:
            station_name: Station name
            train_number: Train number
            query_date: Date (default: today)
            hour: Hour (default: current hour)

        Returns:
            Dictionary with all results
        """
        # 1. Fetch live data
        live_data = self.fetch_live_data(station_name, train_number, query_date, hour)
        if not live_data:
            return {
                "error": "Could not fetch live data",
                "station_name": station_name,
                "train_number": train_number,
            }

        # 2. Engineer features
        features = self.engineer_features(live_data)

        # 3. Make prediction
        prediction = self.predict(features)

        # 4. Log to database
        self.log_prediction(live_data, features, prediction)

        # 5. Include real-time delay info in the result
        rt_info = {
            "has_realtime_data": live_data.get("has_realtime_data", False),
            "actual_arrival_delay_min": live_data.get("actual_arrival_delay_min"),
            "actual_departure_delay_min": live_data.get("actual_departure_delay_min"),
            "actual_arrival_time": live_data.get("actual_arrival_time"),
            "actual_departure_time": live_data.get("actual_departure_time"),
            "arrival_platform": live_data.get("arrival_platform"),
            "departure_platform": live_data.get("departure_platform"),
            "origin": live_data.get("origin"),
            "destination": live_data.get("destination"),
            "route_stops": live_data.get("route_stops", []),
            "scheduled_time_display": live_data.get("scheduled_time_display"),
        }

        # 6. Return combined results
        return {
            **live_data,
            **prediction,
            **rt_info,
            "features": features.iloc[0].to_dict(),
        }


    def get_model_metrics(self) -> dict:
        """Load saved model performance metrics from JSON."""
        metrics_path = Path("models/model_metrics.json")
        if metrics_path.exists():
            try:
                import json as json_module
                with open(metrics_path) as f:
                    return json_module.load(f)
            except Exception as e:
                logger.warning("Failed to load model metrics: %s", e)
        return {}

    def get_feature_importance(self) -> Optional[dict]:
        """Extract feature importance from the XGBoost model if available."""
        try:
            xgb = self.model.named_steps.get("classifier")
            if xgb and hasattr(xgb, "feature_importances_"):
                preprocessor = self.model.named_steps.get("preprocessor")
                if preprocessor:
                    num_features = preprocessor.transformers_[0][2]
                    cat_encoder = preprocessor.transformers_[1][1]
                    cat_features = preprocessor.transformers_[1][2]
                    cat_names = []
                    if hasattr(cat_encoder, "get_feature_names_out"):
                        cat_names = cat_encoder.get_feature_names_out(cat_features).tolist()
                    all_names = list(num_features) + cat_names
                    if len(all_names) == len(xgb.feature_importances_):
                        importances = sorted(
                            zip(all_names, xgb.feature_importances_),
                            key=lambda x: x[1], reverse=True,
                        )
                        return {name: float(imp) for name, imp in importances[:20]}
        except Exception as e:
            logger.warning("Failed to extract feature importance: %s", e)
        return None


# Convenience function for one-off predictions
def predict_delay(
    station_name: str,
    train_number: str,
    model_path: str = "models/xgb_weather.joblib",
) -> dict:
    """
    Quick prediction function.

    Args:
        station_name: Station name
        train_number: Train number
        model_path: Path to model file

    Returns:
        Prediction results
    """
    predictor = DelayPredictor(model_path)
    return predictor.predict_and_log(station_name, train_number)
