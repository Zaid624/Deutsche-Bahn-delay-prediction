-- ============================================================
-- SCHEMA DOCUMENTATION
-- Deutsche Bahn Delay Prediction — Portfolio Project
-- ============================================================
-- Rationale for using PostgreSQL (Supabase):
--   - Relational integrity (no duplicate records from parquet loading)
--   - JSONB support for logging prediction features
--   - SQLAlchemy ORM for clean Python integration with pandas
--   - Supabase: free hosted Postgres, no ops overhead for a portfolio project
-- ============================================================

-- TABLE: train_delays
-- Purpose: Source of truth for model training.
--          Each row = one observation of a train at a station at a point in time.
--          Loaded once from cleaned monthly parquet files.
-- Row estimate (scoped): ~750K rows (ICE only, top 10 stations, 17 months)

CREATE TABLE IF NOT EXISTS train_delays (
    id                      TEXT PRIMARY KEY,           -- unique record ID from source
    station_name            TEXT NOT NULL,               -- e.g. "Frankfurt (Main) Hbf"
    train_number            TEXT NOT NULL,               -- e.g. "123"
    train_type              TEXT NOT NULL,               -- always 'ICE' in our scope
    delay_in_min            INTEGER NOT NULL,            -- target variable; negative = early
    is_canceled             BOOLEAN NOT NULL,            -- TRUE if trip was canceled
    time                    TIMESTAMPTZ NOT NULL,        -- observation time (Europe/Berlin)
    train_line_ride_id      BIGINT,                      -- groups stops belonging to same ride
    train_line_station_num  INTEGER,                     -- stop sequence number within ride
    arrival_planned_time    TIMESTAMPTZ,                 -- planned arrival at station
    departure_planned_time  TIMESTAMPTZ                  -- planned departure from station
);

CREATE INDEX idx_train_delays_station ON train_delays (station_name);
CREATE INDEX idx_train_delays_time     ON train_delays (time);


-- TABLE: live_predictions
-- Purpose: Log every prediction made via the Streamlit demo.
--          Supports monitoring: feature snapshot in JSONB, actual outcome nullable
--          so we can backfill later to assess model performance over time.
-- Row estimate: grows with demo usage (maybe ~50-200 rows for a demo)

CREATE TABLE IF NOT EXISTS live_predictions (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL,
    station_name        TEXT NOT NULL,
    train_type          TEXT NOT NULL,
    train_number        TEXT,
    line_number         TEXT,
    predicted_delay     BOOLEAN NOT NULL,                -- model output: delayed > 5 min?
    predicted_prob      FLOAT NOT NULL,                  -- probability from model (0-1)
    features_used       JSONB,                           -- snapshot of input features
    actual_delay        BOOLEAN,                         -- filled later if user confirms
    actual_delay_in_min FLOAT                            -- filled later if user confirms
);

CREATE INDEX idx_live_predictions_created ON live_predictions (created_at);
