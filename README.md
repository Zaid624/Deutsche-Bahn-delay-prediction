# DB Delay Predictor

Predicting Deutsche Bahn train delays — an end-to-end ML portfolio project for data/business analyst roles.

**Live App:** [Streamlit Deployment](https://deutsche-bahn-delay-prediction-iw3k3wm753zsuyuw2srinq.streamlit.app/)

## Overview

An XGBoost-based classifier that predicts the probability of a Deutsche Bahn ICE train being delayed at a given station, using historical delay data, weather conditions, and real-time DB API data.

## Features

- **Real-time predictions** — fetches live timetable and delay data from the Deutsche Bahn API
- **Weather-aware** — integrates hourly weather observations (temperature, precipitation, wind, cloud cover) from DWD open data
- **Historical ML model** — trained on 17 months of ICE delay records (July 2024 – November 2025)
- **Interactive UI** — Streamlit app with probability gauge, feature importance, and model comparison

## Tech Stack

- **Model:** XGBoost, scikit-learn
- **Data:** Deutsche Bahn Timetables API (real-time), [piebro/deutsche-bahn-data](https://huggingface.co/datasets/piebro/deutsche-bahn-data) (historical, CC BY 4.0), DWD weather data
- **Database:** Supabase (PostgreSQL)
- **Frontend:** Streamlit, Plotly, AgGrid
- **Deployment:** Streamlit Cloud

## Project Structure

```
├── app.py                  # Streamlit app entry point
├── components/             # UI components (sidebar, charts, cards, tables)
├── src/
│   ├── predictor.py        # DelayPredictor class (live prediction logic)
│   ├── db_api.py           # Deutsche Bahn API client
│   ├── features.py         # Feature engineering pipeline
│   ├── train.py            # Model training script
│   ├── database.py         # Supabase/PostgreSQL connection
│   ├── weather.py          # DWD weather data fetcher
│   ├── eva_lookup.py       # Station name → EVA number resolution
│   └── route_cache.py      # SQLite route caching
├── models/                 # Trained model files
├── data/                   # Parquet files (gitignored)
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with:

```
DATABASE_URL=your_supabase_connection_string
DB_CLIENT_ID=your_db_api_client_id
DB_CLIENT_SECRET=your_db_api_client_secret
```

## License

Data: CC BY 4.0 © Deutsche Bahn AG
