# db_tools.py
import sqlite3
import re
import os
import json
import pandas as pd

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enterprise_bi.db")

ALLOWED_ACTIONS = {
    getattr(sqlite3, 'SQLITE_READ', 20),
    getattr(sqlite3, 'SQLITE_SELECT', 21),
    getattr(sqlite3, 'SQLITE_TRANSACTION', 22),
    getattr(sqlite3, 'SQLITE_FUNCTION', 31),
    getattr(sqlite3, 'SQLITE_RECURSIVE', 33)
}

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "create", "alter", 
    "replace", "rename", "truncate", "grant", "revoke", "pragma"
]

def make_authorizer():
    def authorizer_callback(action_code, arg1, arg2, dbname, source_trigger_or_view):
        if action_code in ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    return authorizer_callback

def validate_query_statically(sql_query: str) -> None:
    # Strip comments
    query_clean = re.sub(r'/\*.*?\*/', '', sql_query, flags=re.DOTALL)
    query_clean = re.sub(r'--.*$', '', query_clean, flags=re.MULTILINE)
    
    # Check word boundaries for forbidden keywords
    words = re.findall(r'\b[a-zA-Z_]+\b', query_clean.lower())
    for word in words:
        if word in FORBIDDEN_KEYWORDS:
            raise ValueError(
                f"Security Validation Error: Query contains unauthorized keyword '{word.upper()}'. "
                f"Only read-only SELECT queries are allowed."
            )

def get_database_schema(db_path: str = None) -> str:
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if not os.path.exists(db_path):
        return f"Error: Database file not found at {db_path}"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        target_tables = ['accounts', 'monthly_metrics']
        schema_info = ["=== Database Schema for enterprise_bi.db ==="]
        for table in target_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            if not cursor.fetchone():
                schema_info.append(f"\nTable: {table} (Not found in database)")
                continue
            schema_info.append(f"\nTable: {table}")
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            schema_info.append("  Columns:")
            for col in columns:
                cid, name, col_type, notnull, dflt_value, pk = col
                details = []
                if notnull: details.append("NOT NULL")
                if dflt_value is not None: details.append(f"DEFAULT {dflt_value}")
                if pk: details.append(f"PRIMARY KEY")
                details_str = f" ({', '.join(details)})" if details else ""
                schema_info.append(f"    - {name} {col_type or 'BLOB'}{details_str}")
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            fkeys = cursor.fetchall()
            if fkeys:
                schema_info.append("  Foreign Keys:")
                for fk in fkeys:
                    _, _, parent_table, child_col, parent_col, _, on_delete, _ = fk
                    schema_info.append(f"    - {child_col} -> {parent_table}({parent_col}) [ON DELETE: {on_delete}]")
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            ddl_row = cursor.fetchone()
            if ddl_row and ddl_row[0]:
                schema_info.append("  Raw DDL:")
                indented_ddl = "\n".join("    " + line for line in ddl_row[0].strip().split("\n"))
                schema_info.append(indented_ddl)
        conn.close()
        return "\n".join(schema_info)
    except Exception as e:
        return f"Error retrieving database schema: {str(e)}"

def run_read_only_query(sql_query: str, return_format: str = "json", db_path: str = None):
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    if not os.path.exists(db_path):
        return f"Error: Database file not found at {db_path}"
    try:
        validate_query_statically(sql_query)
    except ValueError as val_err:
        return f"Query Blocked: {str(val_err)}"
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.set_authorizer(make_authorizer())
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        df = pd.DataFrame(rows, columns=columns)
        if return_format.lower() == "dataframe":
            return df
        elif return_format.lower() == "json":
            return df.to_json(orient="records", indent=2)
        else:
            return f"Error: Unsupported return format '{return_format}'"
    except sqlite3.DatabaseError as db_err:
        error_msg = str(db_err)
        if "authorized" in error_msg.lower() or "authorizer" in error_msg.lower():
            return f"Security Violation: Query execution denied. Details: {error_msg}"
        return f"Database Error: {error_msg}"
    except Exception as e:
        return f"System Error: {str(e)}"
    finally:
        if conn: conn.close()
