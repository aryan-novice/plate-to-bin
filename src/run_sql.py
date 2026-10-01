"""
run_sql.py
----------
Runs every question in sql/business_questions.sql against data/mess.db and
prints the answers as tables. No SQL client needed.

Run:  python src/run_sql.py
"""

import re
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sql = (ROOT / "sql/business_questions.sql").read_text()

# split on the "-- Qn." headers so each question keeps its title
blocks = re.split(r"\n(?=-- Q\d+\.)", sql)
pd.set_option("display.width", 140)

with sqlite3.connect(ROOT / "data/mess.db") as con:
    for block in blocks:
        title = re.search(r"-- (Q\d+\..*)", block)
        if not title:
            continue
        query = "\n".join(l for l in block.splitlines() if not l.strip().startswith("--"))
        print("\n" + title.group(1))
        print("-" * len(title.group(1)))
        print(pd.read_sql_query(query, con).to_string(index=False))
