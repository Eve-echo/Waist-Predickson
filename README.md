# Waste Generation Forecasting System (INNOVATE Hackathon)

Forecasts waste generated per city/area so municipalities can see hotspots and plan bin placement.

## Structure
- Backend/forecaster.py - data loading, forecasting, hotspot ranking, bin recommendations
- Script/train.py - runs the pipeline, prints backtest metric
- UI/app.py - Streamlit dashboard
- data/waste.csv - put the Kaggle dataset here (not committed)

## Run
```bash
pip install -r requirements.txt
python Script/train.py --data data/waste.csv
streamlit run UI/app.py
```

Dataset: Kaggle, *Waste Management and Recycling in Indian Cities*.

## Database
```bash
python Script/seed_db.py --data data/waste.csv --reset   # creates data/waste.db
```
Tables: users, regions, waste_records, forecasts, bin_capacity.
The model script saves predictions with `Backend.db.save_forecasts(conn, df, model_name).
