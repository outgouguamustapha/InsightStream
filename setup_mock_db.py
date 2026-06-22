import sqlite3
import os
from datetime import datetime

DB_NAME = "enterprise_bi.db"

def setup_database():
    print(f"Initializing database: {DB_NAME}")
    
    # Establish connection
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Drop tables if they exist to start fresh
    cursor.execute("DROP TABLE IF EXISTS monthly_metrics;")
    cursor.execute("DROP TABLE IF EXISTS accounts;")
    
    # Create accounts table
    cursor.execute("""
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY,
        company_name TEXT NOT NULL,
        industry TEXT NOT NULL,
        signup_date TEXT NOT NULL,
        plan_tier TEXT NOT NULL,
        status TEXT NOT NULL
    );
    """)
    
    # Create monthly_metrics table
    cursor.execute("""
    CREATE TABLE monthly_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        log_month TEXT NOT NULL,
        mrr REAL NOT NULL,
        active_users INTEGER NOT NULL,
        api_calls INTEGER NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
    );
    """)
    
    # Mock data for accounts
    accounts_data = [
        (101, "Acme Corp", "Manufacturing", "2025-10-15", "Premium", "Active"),
        (102, "Globex Corporation", "Tech", "2025-11-01", "Enterprise", "Active"),
        (103, "Initech", "Software", "2025-12-10", "Basic", "Active"),
        (104, "Umbrella Corp", "Biotech", "2025-05-20", "Enterprise", "Active"),
        (105, "Hooli", "Tech", "2026-01-15", "Premium", "Active"),
        (106, "Soylent Corp", "Food & Beverage", "2025-08-01", "Basic", "Churned")
    ]
    
    cursor.executemany("""
    INSERT INTO accounts (id, company_name, industry, signup_date, plan_tier, status)
    VALUES (?, ?, ?, ?, ?, ?);
    """, accounts_data)
    
    # Mock data for monthly_metrics (multi-month time series: Jan 2026 to May 2026)
    # columns: id, account_id, log_month, mrr, active_users, api_calls
    metrics_data = [
        # Acme Corp (Plan: Premium)
        (101, "2026-01", 1200.0, 150, 4500),
        (101, "2026-02", 1200.0, 155, 4800),
        (101, "2026-03", 1200.0, 160, 5200),
        (101, "2026-04", 1200.0, 158, 4900),
        (101, "2026-05", 1200.0, 165, 5500),
        
        # Globex Corporation (Plan: Enterprise)
        (102, "2026-01", 5000.0, 520, 25000),
        (102, "2026-02", 5000.0, 540, 27500),
        (102, "2026-03", 5500.0, 580, 31000), # Upgraded/expanded
        (102, "2026-04", 5500.0, 610, 33000),
        (102, "2026-05", 5500.0, 650, 36500),
        
        # Initech (Plan: Basic)
        (103, "2026-01", 200.0, 12, 400),
        (103, "2026-02", 200.0, 14, 450),
        (103, "2026-03", 200.0, 15, 510),
        (103, "2026-04", 200.0, 13, 390),
        (103, "2026-05", 200.0, 16, 550),
        
        # Umbrella Corp (Plan: Enterprise)
        (104, "2026-01", 8000.0, 950, 60000),
        (104, "2026-02", 8000.0, 960, 62000),
        (104, "2026-03", 8000.0, 980, 65000),
        (104, "2026-04", 8000.0, 990, 67000),
        (104, "2026-05", 8000.0, 1020, 71000),
        
        # Hooli (Plan: Premium) - signed up in Jan 2026
        (105, "2026-02", 1500.0, 80, 2100),
        (105, "2026-03", 1500.0, 95, 2900),
        (105, "2026-04", 1500.0, 110, 3400),
        (105, "2026-05", 1500.0, 125, 4100),
        
        # Soylent Corp (Plan: Basic) - churned active in 2025, no 2026 metrics
        (106, "2025-11", 150.0, 8, 150),
        (106, "2025-12", 150.0, 5, 80)
    ]
    
    cursor.executemany("""
    INSERT INTO monthly_metrics (account_id, log_month, mrr, active_users, api_calls)
    VALUES (?, ?, ?, ?, ?);
    """, metrics_data)
    
    conn.commit()
    
    # Verify records
    cursor.execute("SELECT COUNT(*) FROM accounts;")
    accounts_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM monthly_metrics;")
    metrics_count = cursor.fetchone()[0]
    
    print(f"Successfully inserted {accounts_count} accounts.")
    print(f"Successfully inserted {metrics_count} monthly_metrics records.")
    
    conn.close()
    print("Database setup complete.")

if __name__ == "__main__":
    setup_database()
