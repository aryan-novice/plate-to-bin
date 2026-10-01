"""
clean_data.py
-------------
Turns the messy kitchen log into an analysis-ready table and prints a short
report of every fix, so the cleaning is auditable.

Run:  python src/clean_data.py
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

log = pd.read_csv(RAW / "meal_log_raw.csv")
dishes = pd.read_csv(RAW / "dishes.csv")
cal = pd.read_csv(RAW / "academic_calendar.csv", parse_dates=["date"])
report = []

# 1. Dates: two formats in the same column (YYYY-MM-DD and DD-MM-YYYY)
iso = pd.to_datetime(log["date"], format="%Y-%m-%d", errors="coerce")
dmy = pd.to_datetime(log["date"], format="%d-%m-%Y", errors="coerce")
report.append(f"Dates written as DD-MM-YYYY fixed: {iso.isna().sum()}")
log["date"] = iso.fillna(dmy)

# 2. Meal type casing
log["meal_type"] = log["meal_type"].str.strip().str.lower()

# 3. Dish names: trim, fix case, map known spelling variants
SPELLING = {"Chole Bature": "Chole Bhature", "Idly Sambar": "Idli Sambar",
            "Aloo Gobhi": "Aloo Gobi"}
before = log["dish_name"].nunique()
log["dish_name"] = log["dish_name"].str.strip().str.title().replace(SPELLING)
unknown = set(log["dish_name"]) - set(dishes["dish_name"])
assert not unknown, f"Unmapped dish names: {unknown}"
report.append(f"Dish name variants merged: {before} -> {log['dish_name'].nunique()}")

# 4. Exact duplicate rows (same meal logged twice)
dupes = log.duplicated().sum()
log = log.drop_duplicates()
report.append(f"Duplicate rows removed: {dupes}")

# 5. Leftover typed in grams: can't throw away more than was cooked
grams = log["leftover_kg"] > log["food_prepared_kg"]
log.loc[grams, "leftover_kg"] = log.loc[grams, "leftover_kg"] / 1000
report.append(f"Leftover values entered in grams converted to kg: {grams.sum()}")

# 6. Missing plate waste (scale not working): impute with that dish's
#    median plate-waste share of food served, not a global average
log["served_kg"] = log["food_prepared_kg"] - log["leftover_kg"]
share = (log["plate_waste_kg"] / log["served_kg"]).groupby(log["dish_name"]).transform("median")
missing = log["plate_waste_kg"].isna()
log["plate_waste_imputed"] = missing
log.loc[missing, "plate_waste_kg"] = (log.loc[missing, "served_kg"] * share[missing]).round(1)
report.append(f"Missing plate-waste values imputed (dish median): {missing.sum()}")

# 7. Enrich: join dish + calendar, add derived metrics
log = (log.merge(dishes, on="dish_name", how="left")
          .merge(cal, on="date", how="left"))
log["ran_out"] = log["ran_out"].eq("Y")
log["total_waste_kg"] = log["leftover_kg"] + log["plate_waste_kg"]
log["waste_pct"] = (log["total_waste_kg"] / log["food_prepared_kg"] * 100).round(2)
log["attendance_pct"] = (log["headcount"] / log["students_registered"] * 100).round(2)
log["waste_cost_inr"] = (log["total_waste_kg"] * log["cost_per_kg"]).round(0)
log["is_weekend"] = log["day_of_week"].isin(["Saturday", "Sunday"])
log["month"] = log["date"].dt.to_period("M").astype(str)
log["meal_type"] = pd.Categorical(log["meal_type"], ["breakfast", "lunch", "dinner"], ordered=True)
log = log.sort_values(["date", "meal_type"]).reset_index(drop=True)

# Sanity checks
assert log.duplicated(["date", "meal_type"]).sum() == 0, "one row per meal expected"
assert (log["leftover_kg"] <= log["food_prepared_kg"]).all()
assert log.isna().sum().sum() == 0, log.isna().sum()

log.to_csv(OUT / "meals_clean.csv", index=False)
fb = pd.read_csv(RAW / "student_feedback.csv", parse_dates=["date"])
fb["comment_tag"] = fb["comment_tag"].fillna("")
fb.to_csv(OUT / "feedback_clean.csv", index=False)

print("Cleaning report")
print("-" * 40)
for line in report:
    print(" •", line)
print(f"\nFinal table: {len(log)} meals, {log.shape[1]} columns -> data/processed/meals_clean.csv")
