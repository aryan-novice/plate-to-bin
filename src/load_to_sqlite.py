"""
load_to_sqlite.py
-----------------
Builds data/mess.db from the cleaned CSVs using sql/schema.sql,
so the questions in sql/business_questions.sql can be run.

Run:  python src/load_to_sqlite.py
"""

import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "mess.db"

meals = pd.read_csv(ROOT / "data/processed/meals_clean.csv")
feedback = pd.read_csv(ROOT / "data/processed/feedback_clean.csv")
dishes = pd.read_csv(ROOT / "data/raw/dishes.csv")
calendar = pd.read_csv(ROOT / "data/raw/academic_calendar.csv")

meals = meals.assign(ran_out=meals.ran_out.astype(int),
                     plate_waste_imputed=meals.plate_waste_imputed.astype(int))
meals = meals[["date", "meal_type", "dish_id", "students_registered", "headcount",
               "food_prepared_kg", "leftover_kg", "plate_waste_kg", "ran_out",
               "plate_waste_imputed"]]
feedback["date"] = pd.to_datetime(feedback["date"]).dt.strftime("%Y-%m-%d")

with sqlite3.connect(DB) as con:
    con.executescript((ROOT / "sql/schema.sql").read_text())
    for name, df in [("dishes", dishes), ("calendar", calendar),
                     ("meals", meals), ("feedback", feedback)]:
        df.to_sql(name, con, if_exists="append", index=False)
        print(f"{name:<9} {len(df):>5} rows loaded")
print(f"\nDatabase ready: {DB.relative_to(ROOT)}")
