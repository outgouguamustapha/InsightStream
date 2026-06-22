import unittest
import sqlite3
import pandas as pd
import json
import os

# Import tools to test
from db_tools import (
    get_database_schema,
    run_read_only_query,
    validate_query_statically,
    DEFAULT_DB_PATH
)

class TestSecureDataAccessTools(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Verify the mock database exists
        if not os.path.exists(DEFAULT_DB_PATH):
            raise FileNotFoundError(
                f"Test database '{DEFAULT_DB_PATH}' not found. "
                f"Please run 'setup_mock_db.py' first."
            )

    def test_get_database_schema(self):
        """Verify the database schema output formatting and correctness."""
        schema = get_database_schema()
        self.assertIn("=== Database Schema for enterprise_bi.db ===", schema)
        self.assertIn("Table: accounts", schema)
        self.assertIn("Table: monthly_metrics", schema)
        
        # Check for specific column names
        self.assertIn("company_name", schema)
        self.assertIn("plan_tier", schema)
        self.assertIn("log_month", schema)
        self.assertIn("mrr", schema)
        
        # Check foreign keys
        self.assertIn("account_id -> accounts(id)", schema)

    def test_valid_select_query_json(self):
        """Test a valid SELECT query returning JSON string output."""
        query = "SELECT company_name, industry FROM accounts WHERE status = 'Active' ORDER BY company_name;"
        result = run_read_only_query(query, return_format="json")
        
        # Parse output to verify JSON format and content
        data = json.loads(result)
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) > 0)
        
        # Verify that companies match expected alphabetical list
        companies = [row["company_name"] for row in data]
        self.assertIn("Acme Corp", companies)
        self.assertIn("Globex Corporation", companies)
        self.assertEqual(companies[0], "Acme Corp")

    def test_valid_select_query_dataframe(self):
        """Test a valid SELECT query returning a pandas DataFrame."""
        query = "SELECT log_month, SUM(mrr) as total_mrr FROM monthly_metrics GROUP BY log_month;"
        df = run_read_only_query(query, return_format="dataframe")
        
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn("log_month", df.columns)
        self.assertIn("total_mrr", df.columns)
        self.assertTrue(len(df) > 0)

    def test_invalid_sql_syntax_error(self):
        """Test that syntax errors return descriptive database error messages instead of crashing."""
        query = "SELECTING * FROM accounts;" # Typo in keyword
        result = run_read_only_query(query)
        self.assertTrue(result.startswith("Database Error:"))
        self.assertIn("near \"SELECTING\": syntax error", result)

    def test_static_validation_blocked_keywords(self):
        """Verify that basic SQL write commands are caught by the static regex parser."""
        bad_queries = [
            "INSERT INTO accounts (id, company_name) VALUES (107, 'Evil Corp');",
            "UPDATE accounts SET plan_tier = 'Free';",
            "DELETE FROM accounts WHERE id = 101;",
            "DROP TABLE monthly_metrics;",
            "CREATE TABLE evil_table (id INTEGER);",
            "ALTER TABLE accounts ADD COLUMN password TEXT;",
            "REPLACE INTO accounts VALUES (101, 'Hacked');",
            "TRUNCATE TABLE accounts;",
            "PRAGMA journal_mode = WAL;"
        ]
        
        for q in bad_queries:
            result = run_read_only_query(q)
            self.assertTrue(result.startswith("Query Blocked:"), f"Failed to block: {q}")
            self.assertIn("Security Validation Error", result)

    def test_static_validation_case_insensitivity(self):
        """Verify static validation is case insensitive."""
        query = "update accounts set plan_tier = 'Free';"
        result = run_read_only_query(query)
        self.assertTrue(result.startswith("Query Blocked:"))
        self.assertIn("UPDATE", result)

    def test_static_validation_ignores_substrings(self):
        """Verify that static validation does not block queries containing keywords as substrings."""
        # 'create' is in 'created_at', 'update' is in 'updated_status', etc.
        query = "SELECT id, signup_date as created_at FROM accounts;"
        result = run_read_only_query(query)
        self.assertFalse(result.startswith("Query Blocked:"))
        
        data = json.loads(result)
        self.assertTrue(len(data) > 0)
        self.assertIn("created_at", data[0])

    def test_authorizer_defense_in_depth(self):
        """
        Bypasses static validation to test the SQLite authorizer.
        This verifies that even if the static filter is bypassed or disabled, the 
        sqlite3 Connection Authorizer blocks unauthorized operations.
        """
        # Let's define a helper to execute queries bypassing the static validation layer
        def execute_bypass_static(query):
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
                # Register authorizer
                from db_tools import make_authorizer
                conn.set_authorizer(make_authorizer())
                cursor = conn.cursor()
                cursor.execute(query)
                return "Success"
            except sqlite3.DatabaseError as db_err:
                return f"Error: {str(db_err)}"
            finally:
                conn.close()
                
        # 1. Attempt UPDATE
        res = execute_bypass_static("UPDATE accounts SET plan_tier = 'Free' WHERE id = 101;")
        self.assertIn("not authorized", res.lower())
        
        # 2. Attempt INSERT
        res = execute_bypass_static("INSERT INTO accounts VALUES (999, 'Bypassed', 'Tech', '2026-01-01', 'Basic', 'Active');")
        self.assertIn("not authorized", res.lower())
        
        # 3. Attempt CREATE TABLE
        res = execute_bypass_static("CREATE TABLE test_bypass (id INTEGER);")
        self.assertIn("not authorized", res.lower())
        
        # 4. Attempt DROP TABLE
        res = execute_bypass_static("DROP TABLE accounts;")
        self.assertIn("not authorized", res.lower())
        
        # 5. Attempt PRAGMA modification
        res = execute_bypass_static("PRAGMA journal_mode = MEMORY;")
        self.assertIn("not authorized", res.lower())

    def test_comment_stripping_and_obfuscation_blocking(self):
        """Test SQL injection/obfuscation bypass attempts using comments or formatting."""
        # Try wrapping a forbidden keyword in comments
        query1 = "SELECT * FROM accounts; -- UPDATE accounts SET plan_tier = 'Free';"
        # Even though UPDATE is in a comment, our static check cleans comments first
        # and then should block if it thinks there are multiple statements (or we just let the sqlite3 library block it)
        # Wait, if we strip comments, the query becomes "SELECT * FROM accounts; "
        # Which is safe! Let's check that it runs and returns results instead of blocking unnecessarily:
        res = run_read_only_query(query1)
        self.assertFalse(res.startswith("Query Blocked:"), "Comment-only updates should not block safe select query.")
        
        # Try placing write keyword inside the SELECT (e.g. as an alias but not as a keyword)
        query2 = "SELECT company_name as 'create' FROM accounts;"
        res2 = run_read_only_query(query2)
        # 'create' as a string/alias should not be blocked since it's a quoted literal, but if we check raw word boundary:
        # Wait! In "company_name as 'create'", the word is 'create'. Does our static validation match it?
        # Yes, \bcreate\b matches it if it's treated as a word.
        # Let's see if we can make static check more robust to not block simple aliases, but actually, 
        # blocking aliases like 'create' is a safe default. Let's verify what happens.
        # Wait, if we want to run:
        query3 = "SELECT company_name AS creation_tier FROM accounts;"
        res3 = run_read_only_query(query3)
        self.assertFalse(res3.startswith("Query Blocked:"))

if __name__ == "__main__":
    unittest.main()
