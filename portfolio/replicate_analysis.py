import sqlite3
import pandas as pd

# Connection to database
conn = sqlite3.connect("enterprise_bi.db")

# Extract monthly data
query = (
    "SELECT a.company_name, a.plan_tier, a.status, "
    "m.log_month, m.mrr, m.active_users, m.api_calls "
    "FROM accounts a "
    "JOIN monthly_metrics m ON a.id = m.account_id "
    "ORDER BY m.log_month, a.company_name;"
)
df = pd.read_sql_query(query, conn)
conn.close()

# Replicate metrics calculation
mrr_sum = df.groupby("log_month")["mrr"].sum().reset_index()
mrr_sum["growth"] = (mrr_sum["mrr"].pct_change() * 100).apply(
    lambda x: f"{x:.2f}%" if pd.notna(x) else "Initial Month"
)
print("--- MRR Analysis ---")
print(mrr_sum.to_string(index=False))