# DB Delay Predictor - Improvements Roadmap

Current accuracy: **74.7%** → Target: **80-85%**

---

## Phase 1: Quick Wins (Est. +2-3% accuracy, 1-2 weeks)

### 1.1 Weather Extremes (Categorical Binning)
**Impact:** +0.5-1.0% accuracy  
**Effort:** Low (2-3 hours)

Replace continuous weather features with categorical extremes:

```python
# In features.py
def add_weather_extremes(df):
    df['heavy_rain'] = (df['precipitation_mm'] > 10).astype(int)
    df['strong_wind'] = (df['wind_speed_ms'] > 15).astype(int)
    df['ice_risk'] = ((df['temperature_c'] < 2) & 
                       (df['precipitation_mm'] > 0)).astype(int)
    df['extreme_temp'] = ((df['temperature_c'] < -5) | 
                          (df['temperature_c'] > 35)).astype(int)
    return df
```

**Rationale:** Rare weather events have disproportionate impact but get diluted in continuous features.

---

### 1.2 Event Calendar
**Impact:** +0.3-0.5% accuracy  
**Effort:** Low (4-6 hours)

Add major events causing abnormal passenger volumes:

```python
# events.py (new file)
import pandas as pd
from datetime import date

MAJOR_EVENTS = {
    # Format: (city, event_name, start_date, end_date)
    ("München", "Oktoberfest 2024", date(2024, 9, 21), date(2024, 10, 6)),
    ("Frankfurt", "Buchmesse 2024", date(2024, 10, 16), date(2024, 10, 20)),
    ("Berlin", "ITB 2025", date(2025, 3, 4), date(2025, 3, 8)),
    ("Köln", "Karneval 2025", date(2025, 2, 27), date(2025, 3, 5)),
    ("Hannover", "CeBIT 2024", date(2024, 9, 10), date(2024, 9, 14)),
    # Add Bundesliga matches, concerts, trade fairs
}

def is_major_event(station_name: str, date: date) -> bool:
    for city, event, start, end in MAJOR_EVENTS:
        if city in station_name and start <= date <= end:
            return True
    return False
```

Data sources:
- `https://www.messe.de/` (trade fairs)
- `https://www.bundesliga.com/en/bundesliga/fixtures` (football)
- Manual collection for top 20 recurring events

---

### 1.3 Try LightGBM / CatBoost
**Impact:** +0.3-0.8% accuracy  
**Effort:** Low (1 hour)

```bash
pip install lightgbm catboost
```

```python
# In train.py
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier

# LightGBM handles categorical natively (no one-hot encoding)
def train_lightgbm(X_train, y_train, categorical_features):
    model = LGBMClassifier(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=31,
        categorical_feature=categorical_features,
        random_state=42
    )
    model.fit(X_train, y_train)
    return model
```

**Why:** Sometimes one GBM library handles your specific data distribution better. Worth 1 hour to test.

---

## Phase 2: Medium Impact (Est. +2-4% accuracy, 2-4 weeks)

### 2.1 Route-Level Weather Features
**Impact:** +1.0-2.0% accuracy  
**Effort:** Medium (scaffolding already exists in `route_weather.py`)

**Status:** 80% complete! Just needs:
1. Run `dry_run_estimate()` to see API call costs
2. Run `build_route_weather_features(sample_size=10000)` to generate features
3. Merge into main feature pipeline

```python
# In features.py
from src.route_weather import merge_route_weather

df_with_route_weather = merge_route_weather(df_features, route_weather_df)
```

**New features added:**
- `avg_temp_along_route` - Average temperature across all stations
- `max_precip_along_route` - Highest precipitation on route
- `rain_at_next_station` - Binary: is next stop experiencing rain?
- `weather_diff_from_origin_temp` - Temp delta from origin station
- `n_stations_in_route` - Route complexity proxy

---

### 2.2 Track Works / Construction Data
**Impact:** +1.0-2.0% accuracy  
**Effort:** Medium (web scraping + API integration)

**Data Source:** DB Bauarbeiten (construction work announcements)
- API: `https://data.deutschebahn.com/dataset/baustellen`
- Scraping: `https://bauinfos.deutschebahn.com/`

```python
# construction.py (new file)
import requests
import pandas as pd

def fetch_construction_schedule(start_date, end_date):
    """Fetch planned track works from DB API."""
    # Implementation: scrape or API call
    # Return: DataFrame with (station_name, start_date, end_date, severity)
    pass

def add_construction_features(df, construction_df):
    """Add binary feature: is_construction_affected."""
    # Merge on (station_name, date)
    pass
```

**Alternative (if API unavailable):** Manual collection of major multi-week works from DB press releases.

---

### 2.3 First-Stop Delay Prediction (Advanced)
**Impact:** +0.5-1.0% accuracy (mostly for first stops)  
**Effort:** Medium-High

**Current bottleneck:** First stops have no cascading delay signal (prev_delay_min = 0).

**Solution:** Train a separate model for first stops using:
- Historical first-stop delay rate by (train_number, station, hour)
- Track occupancy (if available from DB API)
- Weather extremes
- Time since last departure (schedule slack)

```python
# In features.py
is_first_model_needed = df['is_first_stop'] == 1
first_stop_features = ['hist_first_delay_rate', 'scheduled_slack_min', 
                        'heavy_rain', 'hour', 'is_weekend']
```

---

## Phase 3: Diminishing Returns (Est. +0.5-1.0%, 2+ weeks)

### 3.1 Hyperparameter Tuning with Optuna
**Impact:** +0.2-0.5% accuracy  
**Effort:** Low-Medium (needs compute time)

```python
import optuna
from optuna.integration import XGBoostPruningCallback

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 300, 1000),
        'max_depth': trial.suggest_int('max_depth', 4, 12),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15),
        'subsample': trial.suggest_float('subsample', 0.6, 0.95),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 0.95),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 7),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 3.0),
    }
    model = XGBClassifier(**params, random_state=42)
    # Cross-validation score
    scores = cross_val_score(model, X_train, y_train, cv=3, scoring='accuracy')
    return scores.mean()

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50, timeout=7200)  # 2 hours
```

---

### 3.2 Regression Instead of Classification
**Impact:** +0.5-1.0% accuracy  
**Effort:** Medium (pipeline change)

**Current:** Binary classification (delayed > 5 min: yes/no)  
**Proposed:** Regression (predict exact delay minutes) + threshold

```python
# In train.py
from xgboost import XGBRegressor

model = XGBRegressor(objective='reg:squarederror', ...)
model.fit(X_train, y_train_delay_minutes)

# At inference
predicted_delay_min = model.predict(X_test)
predicted_binary = (predicted_delay_min > 5).astype(int)
```

**Benefit:** Model gets more gradient signal during training (5 vs 6 min delay is different from 5 vs 50 min).

---

## Phase 4: Real-Time System (Production)

### Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌───────────────┐
│ DB Timetables API   │────>│ Feature Engine    │────>│ Model Server   │
│ (live train data)   │     │ (merge weather,   │     │ (XGBoost)      │
│                     │     │  hist rates, etc) │     └───────┬───────┘
└─────────────────────┘     └──────────────────┘             │
                                                             ▼
┌─────────────────────┐                              ┌───────────────┐
│ DWD Open Data       │─────────────────────────────>│ Prediction    │
│ (hourly weather)    │                              │ (delayed?     │
└─────────────────────┘                              │  prob + min)  │
                                                     └───────────────┘
```

### Implementation (FastAPI)

```python
# api.py
from fastapi import FastAPI
import joblib
from datetime import datetime

app = FastAPI()
model = joblib.load("models/xgb_weather.joblib")

@app.get("/predict")
def predict_delay(
    station: str,
    train_number: str,
    hour: int,
    date: str = None
):
    # 1. Fetch cascading delay from DB API
    # 2. Fetch weather from DWD cache
    # 3. Lookup hist_delay_rate from precomputed table
    # 4. Assemble feature vector
    features = assemble_features(station, train_number, hour, date)
    
    # 5. Predict
    prob = model.predict_proba([features])[0][1]
    delayed = prob > 0.5
    
    return {
        "delayed": bool(delayed),
        "probability": float(prob),
        "confidence": "high" if abs(prob - 0.5) > 0.3 else "medium"
    }
```

### Deployment
```bash
# Dockerfile
FROM python:3.10-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
WORKDIR /app
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t db-delay-predictor .
docker run -p 8000:8000 db-delay-predictor
```

---

## Accuracy Ceiling Estimates

| Approach | Est. Accuracy | Feasibility | Timeline |
|----------|:-------------:|:-----------:|:--------:|
| **Current (baseline)** | 74.7% | ✅ Done | - |
| + Weather extremes | 75.5% | ✅ Easy | 1 day |
| + Event calendar | 76.0% | ✅ Easy | 2 days |
| + LightGBM | 76.5% | ✅ Easy | 1 day |
| + Route weather | 78.5% | ⚠️ Medium | 1 week |
| + Track works | 80.0% | ⚠️ Medium | 2 weeks |
| + First-stop model | 80.5% | ⚠️ Hard | 2 weeks |
| + Optuna tuning | 81.0% | ✅ Easy | 1 day |
| **All improvements** | **~81-82%** | - | **6-8 weeks** |

---

## Beyond 85%: What's Needed?

To break 85% requires **real-time infrastructure data** not publicly available:

1. **Track occupancy** - How many trains currently on each track segment
2. **Signal failures** - Real-time signaling system status
3. **Crew availability** - Driver/conductor staffing levels
4. **Rolling stock issues** - Train mechanical problems
5. **Network delay propagation** - Real-time impact of upstream delays

This data is **internal to Deutsche Bahn** and requires either:
- Partnership with DB
- Access to internal APIs (requires commercial agreement)
- Scraping live delay boards + manual feature engineering

---

## Recommended Priority Order

1. ✅ **Weather extremes** (1 day, +0.8%)
2. ✅ **Event calendar** (2 days, +0.5%)
3. ✅ **LightGBM trial** (1 day, +0.5%)
4. ⏸️ **Route weather** (1 week, +2.0%) - scaffolding exists
5. ⏸️ **Track works** (2 weeks, +1.5%)
6. ✅ **Optuna tuning** (1 day, +0.3%)
7. ⏸️ **First-stop model** (2 weeks, +0.5%)

**Total Time:** ~5-6 weeks for 80%+ accuracy

---

## Questions to Consider

1. **Data freshness:** How often to re-train the model?
   - Recommendation: Weekly retraining with rolling 12-month window
2. **Model versioning:** How to A/B test improvements?
   - Recommendation: Log predictions to `live_predictions` table, backfill actuals, compare offline
3. **Explainability:** Do stakeholders need SHAP explanations?
   - Already have `src/interpret.py` for feature importance
4. **Latency requirements:** < 100ms or < 1s?
   - Current model: <1ms inference, 100-500ms with API calls

---

**Current Status:** ✅ All technical debt cleared, ready for Phase 1 improvements!
