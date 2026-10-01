"""
simulate_data.py
----------------
Generates a realistic (simulated) dataset for a college hostel mess that
serves ~1,200 students three meals a day, from July 2025 to March 2026.

Why simulated? Mess records are not public. Every assumption used below is
written out in plain numbers so anyone can question it, change it, or replace
the whole thing with real data that follows the same schema.

The raw files are intentionally a little messy (typos, mixed date formats,
duplicates, a broken weighing scale, grams typed as kg) because that is what
real kitchen logs look like. Cleaning them is part of the project.

Run:  python src/simulate_data.py
"""

from pathlib import Path
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

START, END = "2025-07-21", "2026-03-31"
REGISTERED = 1200
PILOT_START = pd.Timestamp("2026-02-01")  # weekend-breakfast opt-in pilot

# ---------------------------------------------------------------- dishes ---
# dish, meal slot, category, cost per kg (INR), plate-waste rate, popularity
DISHES = [
    # breakfast
    ("Poha", "breakfast", "veg", 48, 0.08, 1.00),
    ("Upma", "breakfast", "veg", 45, 0.18, 0.93),
    ("Aloo Paratha", "breakfast", "veg", 62, 0.05, 1.10),
    ("Idli Sambar", "breakfast", "veg", 55, 0.07, 1.02),
    ("Masala Dosa", "breakfast", "veg", 70, 0.05, 1.08),
    ("Bread Omelette", "breakfast", "egg", 75, 0.06, 1.04),
    ("Puri Bhaji", "breakfast", "veg", 58, 0.05, 1.06),
    ("Vermicelli Upma", "breakfast", "veg", 46, 0.17, 0.94),
    # lunch / dinner
    ("Rajma Chawal", "main", "veg", 70, 0.06, 1.05),
    ("Chole Bhature", "main", "veg", 78, 0.04, 1.08),
    ("Paneer Butter Masala", "main", "veg", 160, 0.04, 1.10),
    ("Dal Makhani", "main", "veg", 85, 0.06, 1.03),
    ("Lauki Chana Dal", "main", "veg", 55, 0.20, 0.92),
    ("Mixed Veg", "main", "veg", 65, 0.13, 0.97),
    ("Kadhi Pakoda", "main", "veg", 60, 0.10, 0.99),
    ("Soya Chunk Curry", "main", "veg", 72, 0.16, 0.95),
    ("Veg Biryani", "main", "veg", 90, 0.05, 1.10),
    ("Chicken Curry", "main", "non-veg", 180, 0.03, 1.12),
    ("Egg Curry", "main", "egg", 95, 0.06, 1.02),
    ("Aloo Gobi", "main", "veg", 58, 0.09, 1.00),
    ("Bhindi Masala", "main", "veg", 68, 0.08, 1.01),
    ("Tinda Masala", "main", "veg", 52, 0.24, 0.90),
]
dishes = pd.DataFrame(DISHES, columns=[
    "dish_name", "slot", "food_type", "cost_per_kg", "_plate_waste_rate", "_popularity"])
dishes.insert(0, "dish_id", [f"D{i:02d}" for i in range(1, len(dishes) + 1)])

BREAKFAST = dishes[dishes.slot == "breakfast"].dish_name.tolist()
MAINS = dishes[dishes.slot == "main"].dish_name.tolist()
D = dishes.set_index("dish_name")

# -------------------------------------------------------------- calendar ---
dates = pd.date_range(START, END, freq="D")
WINTER_BREAK = pd.date_range("2025-12-20", "2026-01-04")  # mess closed
cal = pd.DataFrame({"date": dates})
cal = cal[~cal.date.isin(WINTER_BREAK)].reset_index(drop=True)


def label_event(d):
    def between(a, b):
        return pd.Timestamp(a) <= d <= pd.Timestamp(b)
    if between("2025-10-18", "2025-10-26"):
        return "diwali_break"
    if between("2025-09-22", "2025-10-01") or between("2025-11-24", "2025-12-10") \
            or between("2026-02-16", "2026-02-25"):
        return "exams"
    if between("2025-10-30", "2025-11-01") or between("2026-02-06", "2026-02-08"):
        return "fest"
    if d in pd.to_datetime(["2025-08-15", "2025-08-16", "2025-08-17",
                            "2026-01-24", "2026-01-25", "2026-01-26",
                            "2026-03-03", "2026-03-04"]):
        return "long_weekend"
    return "regular"


cal["academic_event"] = cal.date.apply(label_event)
rain_prob = cal.date.dt.month.map({7: .5, 8: .45, 9: .35, 10: .15, 11: .05,
                                   12: .03, 1: .03, 2: .04, 3: .05})
cal["weather"] = np.where(RNG.random(len(cal)) < rain_prob, "rain", "clear")
cal["day_of_week"] = cal.date.dt.day_name()

# ------------------------------------------------------- assumptions -----
BASE_RATE = {"breakfast": 0.62, "lunch": 0.78, "dinner": 0.84}
PLANNED_RATE = {"breakfast": 0.70, "lunch": 0.82, "dinner": 0.85}  # kitchen's fixed rule
PORTION_KG = {"breakfast": 0.30, "lunch": 0.45, "dinner": 0.45}
BUFFER = 0.08
DOW = {  # (meal, weekday) attendance multipliers
    ("breakfast", "Saturday"): 0.60, ("breakfast", "Sunday"): 0.48,
    ("lunch", "Sunday"): 0.92, ("dinner", "Saturday"): 0.86,
    ("dinner", "Sunday"): 0.72, ("dinner", "Friday"): 0.92,
}
EVENT = {
    "exams": {"breakfast": 1.18, "lunch": 1.06, "dinner": 1.13},
    "fest": {"breakfast": 0.95, "lunch": 0.75, "dinner": 0.55},
    "long_weekend": {"breakfast": 0.50, "lunch": 0.55, "dinner": 0.55},
    "diwali_break": {"breakfast": 0.25, "lunch": 0.25, "dinner": 0.25},
    "regular": {"breakfast": 1, "lunch": 1, "dinner": 1},
}
KITCHEN_KNOWS = {"diwali_break": 0.30}  # the only event the kitchen plans for

# ------------------------------------------------------------ meal log ---
rows, b_i, m_i = [], 0, 0
for _, day in cal.iterrows():
    for meal in ("breakfast", "lunch", "dinner"):
        if meal == "breakfast":
            dish = BREAKFAST[b_i % len(BREAKFAST)]; b_i += 1   # 8-day rotation
        else:
            k, pos = divmod(m_i, len(MAINS))                    # 14-meal rotation that
            dish = MAINS[(pos + k) % len(MAINS)]; m_i += 1    # shifts a slot every week

        rate = BASE_RATE[meal] * DOW.get((meal, day.day_of_week), 1.0)
        rate *= EVENT[day.academic_event][meal]
        rate *= D.loc[dish, "_popularity"]
        if day.weather == "rain" and meal != "breakfast":
            rate *= 1.07
        rate = float(np.clip(rate + RNG.normal(0, 0.025), 0.05, 0.98))
        headcount = int(RNG.binomial(REGISTERED, rate))

        portion = PORTION_KG[meal] * RNG.normal(1, 0.04)
        pilot = (day.date >= PILOT_START and meal == "breakfast"
                 and day.day_of_week in ("Saturday", "Sunday"))
        if pilot:  # students opt in the night before; kitchen cooks for them
            optins = headcount * RNG.normal(1.04, 0.03)
            prepared = optins * PORTION_KG[meal] * 1.05
        else:
            planned = PLANNED_RATE[meal] * KITCHEN_KNOWS.get(day.academic_event, 1)
            prepared = REGISTERED * planned * PORTION_KG[meal] * (1 + BUFFER)
            prepared *= RNG.normal(1, 0.03)

        demand = headcount * portion
        served = min(prepared, demand)
        shortage = demand > prepared * 1.0
        leftover = max(prepared - served, 0) + abs(RNG.normal(0, 2))
        pw_rate = max(D.loc[dish, "_plate_waste_rate"] * RNG.normal(1, 0.15), 0.01)
        plate_waste = served * pw_rate

        rows.append({
            "date": day.date.strftime("%Y-%m-%d"),
            "meal_type": meal,
            "dish_name": dish,
            "students_registered": REGISTERED,
            "headcount": headcount,
            "food_prepared_kg": round(prepared, 1),
            "leftover_kg": round(leftover, 1),
            "plate_waste_kg": round(plate_waste, 1),
            "ran_out": "Y" if shortage else "N",
        })

log = pd.DataFrame(rows)

# ----------------------------------------- make it look like a real log ---
def corrupt(df):
    df = df.copy()
    n = len(df)
    # 1) inconsistent dish names
    typo_map = {"Chole Bhature": "Chole Bature", "Paneer Butter Masala": "paneer butter masala",
                "Rajma Chawal": " Rajma Chawal ", "Idli Sambar": "Idly Sambar",
                "Tinda Masala": "TINDA MASALA", "Aloo Gobi": "Aloo gobhi"}
    idx = RNG.choice(n, int(n * 0.06), replace=False)
    df.loc[idx, "dish_name"] = df.loc[idx, "dish_name"].map(lambda x: typo_map.get(x, x))
    # 2) mixed meal_type casing
    idx = RNG.choice(n, int(n * 0.05), replace=False)
    df.loc[idx, "meal_type"] = df.loc[idx, "meal_type"].str.upper()
    idx = RNG.choice(n, int(n * 0.04), replace=False)
    df.loc[idx, "meal_type"] = df.loc[idx, "meal_type"].str.title()
    # 3) some dates typed as DD-MM-YYYY by a different staff member
    idx = RNG.choice(n, int(n * 0.04), replace=False)
    df.loc[idx, "date"] = pd.to_datetime(df.loc[idx, "date"]).dt.strftime("%d-%m-%Y")
    # 4) weighing scale broken -> missing plate waste
    idx = RNG.choice(n, int(n * 0.025), replace=False)
    df.loc[idx, "plate_waste_kg"] = np.nan
    # 5) leftover typed in grams instead of kg
    idx = RNG.choice(n, 6, replace=False)
    df.loc[idx, "leftover_kg"] = df.loc[idx, "leftover_kg"] * 1000
    # 6) duplicated entries (logged twice)
    dupes = df.sample(12, random_state=7)
    df = pd.concat([df, dupes]).sample(frac=1, random_state=3).reset_index(drop=True)
    return df


raw_log = corrupt(log)

# -------------------------------------------------------------- feedback ---
fb_rows, fb_id = [], 1
# taste isn't the only reason people leave food (portion size, habits), so
# each dish gets its own small rating offset on top of the waste link
TASTE_OFFSET = dict(zip(dishes.dish_name, RNG.normal(0, 0.3, len(dishes))))
TAGS_BAD = ["too oily", "bland", "undercooked", "cold food", "repetitive menu"]
TAGS_GOOD = ["tasty", "good quantity", "fresh"]
for r in log.itertuples():
    n = RNG.poisson(max(r.headcount * 0.012, 1))  # ~1% scan the QR code
    base = 4.6 - 9 * D.loc[r.dish_name, "_plate_waste_rate"] + TASTE_OFFSET[r.dish_name]
    for _ in range(n):
        rating = int(np.clip(round(RNG.normal(base, 0.8)), 1, 5))
        tag = (RNG.choice(TAGS_BAD) if rating <= 2 else
               RNG.choice(TAGS_GOOD) if rating >= 4 else "")
        if RNG.random() < 0.4:
            tag = ""
        fb_rows.append({"feedback_id": fb_id, "date": r.date, "meal_type": r.meal_type,
                        "rating": rating, "comment_tag": tag})
        fb_id += 1
feedback = pd.DataFrame(fb_rows)

# ---------------------------------------------------------------- write ---
dishes.drop(columns=["slot", "_plate_waste_rate", "_popularity"]).to_csv(RAW / "dishes.csv", index=False)
cal.assign(date=cal.date.dt.strftime("%Y-%m-%d"))[
    ["date", "day_of_week", "academic_event", "weather"]].to_csv(RAW / "academic_calendar.csv", index=False)
raw_log.to_csv(RAW / "meal_log_raw.csv", index=False)
feedback.to_csv(RAW / "student_feedback.csv", index=False)

print(f"meal_log_raw.csv      {len(raw_log):>6} rows")
print(f"student_feedback.csv  {len(feedback):>6} rows")
print(f"academic_calendar.csv {len(cal):>6} rows")
print(f"dishes.csv            {len(dishes):>6} rows")
