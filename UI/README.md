To build the database:

python Script/seed_db.py --reset
python Script/load_ml_output.py --ml-dir RESULT_4

This creates data/waste.db in two steps:

seed_db.py loads cities, monthly history, starting bin counts and demo users.
load_ml_output.py loads the model results from RESULT_4/.

Re-running seed_db.py --reset deletes all tables, so run load_ml_output.py again afterwards.

To run the dashboard:

streamlit run UI/app.py

Open http://localhost:8501 and sign in with a demo account:

Username	Password
admin	admin123
officer	officer123