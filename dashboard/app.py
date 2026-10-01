"""
Mess waste dashboard for the mess committee.

Run:  streamlit run dashboard/app.py
"""

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
LEFTOVER, PLATE, STEEL, LEAF = "#D4962A", "#B5452F", "#6B7780", "#4E7D4A"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["breakfast", "lunch", "dinner"]

st.set_page_config(page_title="Plate to Bin: mess waste", page_icon="🍛", layout="wide")


@st.cache_data
def load():
    df = pd.read_csv(ROOT / "data/processed/meals_clean.csv", parse_dates=["date"])
    return df


df = load()

# ---------------------------------------------------------------- filters
st.sidebar.header("Filters")
start, end = st.sidebar.date_input(
    "Date range", (df.date.min().date(), df.date.max().date()),
    min_value=df.date.min().date(), max_value=df.date.max().date())
meals = st.sidebar.multiselect("Meals", MEALS, default=MEALS)
events = st.sidebar.multiselect("Campus events", sorted(df.academic_event.unique()),
                                default=sorted(df.academic_event.unique()))

f = df[df.date.between(pd.Timestamp(start), pd.Timestamp(end))
       & df.meal_type.isin(meals) & df.academic_event.isin(events)]

st.title("Plate to Bin")
st.caption("Where the hostel mess's food goes · simulated data, Jul 2025 to Mar 2026")

if f.empty:
    st.info("No meals match these filters. Widen the date range or add a meal type.")
    st.stop()

# ------------------------------------------------------------------- KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Food wasted", f"{f.total_waste_kg.sum() / 1000:,.1f} t")
k2.metric("Share of food cooked", f"{f.total_waste_kg.sum() / f.food_prepared_kg.sum():.1%}")
k3.metric("Cost of waste", f"₹{f.waste_cost_inr.sum() / 1e5:,.1f} lakh")
k4.metric("Meals that ran out", f"{int(f.ran_out.sum())} of {len(f)}")

# ------------------------------------------------------------ weekly trend
weekly = (f.set_index("date")[["leftover_kg", "plate_waste_kg"]].resample("W").sum()
          .rename(columns={"leftover_kg": "Leftover (never served)",
                           "plate_waste_kg": "Plate waste (served, not eaten)"}))
fig = px.bar(weekly, barmode="stack", labels={"value": "kg wasted", "date": "", "variable": ""},
             color_discrete_sequence=[LEFTOVER, PLATE], title="Food wasted each week")
fig.add_vline(x=pd.Timestamp("2026-02-01").timestamp() * 1000, line_dash="dash",
              annotation_text="weekend opt-in starts")
fig.update_layout(legend=dict(orientation="h", y=-0.15), margin=dict(t=50, b=10))
st.plotly_chart(fig, width="stretch")

# ------------------------------------------------- when / what side by side
left, right = st.columns(2)
heat = (f.pivot_table(index="meal_type", columns="day_of_week", values="leftover_kg", aggfunc="mean")
        .reindex(index=[m for m in MEALS if m in meals], columns=DAYS))
hfig = px.imshow(heat.round(0), text_auto=True, color_continuous_scale="YlOrBr", aspect="auto",
                 labels=dict(color="kg"), title="Average leftover per meal (kg)")
hfig.update_layout(xaxis_title="", yaxis_title="", margin=dict(t=50, b=10))
left.plotly_chart(hfig, width="stretch")

dish = (f.groupby("dish_name")
        .agg(plate_waste_kg=("plate_waste_kg", "sum"), served_kg=("served_kg", "sum"),
             ran_out=("ran_out", "mean"), served=("date", "count"), cost=("waste_cost_inr", "sum"))
        .assign(plate_waste_pct=lambda d: d.plate_waste_kg / d.served_kg * 100,
                ran_out_pct=lambda d: d.ran_out * 100)
        .sort_values("plate_waste_pct"))
dfig = px.bar(dish.tail(10), x="plate_waste_pct", y=dish.tail(10).index, orientation="h",
              color_discrete_sequence=[PLATE], title="Dishes students leave on the plate",
              labels={"plate_waste_pct": "% of served food thrown away", "y": ""})
dfig.update_layout(margin=dict(t=50, b=10))
right.plotly_chart(dfig, width="stretch")

# -------------------------------------------------------------- dish table
st.subheader("Every dish at a glance")
st.dataframe(
    dish[["served", "plate_waste_pct", "ran_out_pct", "cost"]]
    .sort_values("cost", ascending=False)
    .rename(columns={"served": "Times served", "plate_waste_pct": "Plate waste %",
                     "ran_out_pct": "Ran out %", "cost": "Waste cost (₹)"})
    .style.format({"Plate waste %": "{:.1f}", "Ran out %": "{:.0f}", "Waste cost (₹)": "₹{:,.0f}"}),
    width="stretch")
