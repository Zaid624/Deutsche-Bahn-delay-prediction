from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from src.database import Base


class TrainDelay(Base):
    """
    Stores cleaned historical Deutsche Bahn train delay records.
    This table is the source of truth for model training.
    Data comes from piebro/deutsche-bahn-data (CC BY 4.0).
    """
    __tablename__ = "train_delays"

    id = Column(String, primary_key=True)
    station_name = Column(String, nullable=False, index=True)
    train_number = Column(String, nullable=False)
    train_type = Column(String, nullable=False)
    delay_in_min = Column(Integer, nullable=False)
    is_canceled = Column(Boolean, nullable=False)
    time = Column(DateTime(timezone=True), nullable=False, index=True)
    train_line_ride_id = Column(BigInteger, nullable=True)
    train_line_station_num = Column(Integer, nullable=True)
    arrival_planned_time = Column(DateTime(timezone=True), nullable=True)
    departure_planned_time = Column(DateTime(timezone=True), nullable=True)


class LivePrediction(Base):
    """
    Logs every prediction made through the Streamlit demo app.
    Supports monitoring: we store input features, model output, and can
    later backfill actual outcomes to assess prediction quality over time.
    """
    __tablename__ = "live_predictions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    station_name = Column(String, nullable=False)
    train_type = Column(String, nullable=False)
    train_number = Column(String, nullable=True)
    line_number = Column(String, nullable=True)
    predicted_delay = Column(Boolean, nullable=False)
    predicted_prob = Column(Float, nullable=False)
    features_used = Column(JSONB, nullable=True)
    actual_delay = Column(Boolean, nullable=True)
    actual_delay_in_min = Column(Float, nullable=True)
