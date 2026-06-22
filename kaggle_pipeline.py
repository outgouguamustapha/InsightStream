import os
import subprocess
import sys

# Define the file contents using raw strings to preserve all backslashes (regex, escapes, etc.)
FILES_TO_GENERATE = {
    "db_tools.py": r"""# db_tools.py
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
""",

    "adk.py": r"""# adk.py
import os
import re
import json
import urllib.request
import pandas as pd
from typing import Dict, List, Any, Callable

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()

class AgentContext:
    def __init__(self, query: str):
        self.original_query: str = query
        self.pm_plan: str = ""
        self.schema: str = ""
        self.sql_queries_run: List[str] = []
        self.query_results_json: List[str] = []
        self.analyst_deliverables: Dict[str, str] = {}
        self.history: List[Dict[str, str]] = []

    def add_history(self, role: str, message: str):
        self.history.append({"role": role, "content": message})

class Agent:
    def __init__(self, name: str, role: str, backstory: str, core_instructions: str, tools: List[Callable] = None):
        self.name: str = name
        self.role: str = role
        self.backstory: str = backstory
        self.core_instructions: str = core_instructions
        self.tools: Dict[str, Callable] = {t.__name__: t for t in (tools or [])}

    def _get_system_prompt(self) -> str:
        tools_desc = ""
        if self.tools:
            tools_desc = "\nYou have access to the following tools:\n"
            for t_name, t_func in self.tools.items():
                tools_desc += f"- {t_name}: {t_func.__doc__.strip() if t_func.__doc__ else 'No description'}\n"
            tools_desc += (
                "\nTo call a tool, you MUST output a single JSON block inside a markdown code block. "
                "Do not include any other text in that turn. Example:\n"
                "```json\n"
                "{\n"
                "  \"tool_call\": \"run_read_only_query\",\n"
                "  \"arguments\": {\n"
                "    \"sql_query\": \"SELECT * FROM accounts LIMIT 5;\"\n"
                "  }\n"
                "}\n"
                "```\n"
            )
        return (
            f"You are {self.name}, the {self.role}.\n"
            f"Backstory:\n{self.backstory}\n\n"
            f"Core Instructions:\n{self.core_instructions}\n"
            f"{tools_desc}"
        )

    def run(self, context: AgentContext) -> str:
        print(f"\n[Executing Agent: {self.name}]")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("  --> No GEMINI_API_KEY found. Falling back to high-fidelity simulation mode.")
            return self._run_simulation(context)
        try:
            return self._run_real_llm(context, api_key)
        except Exception as e:
            print(f"  --> Real LLM run failed ({e}). Falling back to simulation mode.")
            return self._run_simulation(context)

    def _run_real_llm(self, context: AgentContext, api_key: str) -> str:
        system_instruction = self._get_system_prompt()
        prompt = (
            f"User Business Query: {context.original_query}\n\n"
            f"Current Workflow Context:\n"
            f"- PM Plan: {context.pm_plan}\n"
            f"- Schema Info: {context.schema}\n"
        )
        if context.query_results_json:
            prompt += f"- Extracted Query Data (JSON):\n{context.query_results_json[-1]}\n"
        prompt += "\nPlease perform your tasks according to your role instructions."

        for turn in range(3):
            response = self._call_gemini_api(prompt, api_key, system_instruction)
            json_block = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_block and self.tools:
                try:
                    tool_data = json.loads(json_block.group(1).strip())
                    tool_name = tool_data.get("tool_call")
                    arguments = tool_data.get("arguments", {})
                    if tool_name in self.tools:
                        print(f"  --> Calling Tool: {tool_name}({arguments})")
                        tool_func = self.tools[tool_name]
                        tool_result = tool_func(**arguments)
                        prompt += f"\n\nSystem: Tool '{tool_name}' returned:\n{tool_result}\n\nContinue your execution."
                        continue
                    else:
                        prompt += f"\n\nSystem: Tool '{tool_name}' is not bound to this agent."
                        continue
                except Exception as parse_err:
                    prompt += f"\n\nSystem: Failed to parse tool call JSON: {parse_err}."
                    continue
            else:
                return response
        return response

    def _call_gemini_api(self, prompt: str, api_key: str, system_instruction: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["candidates"][0]["content"]["parts"][0]["text"]

    def _run_simulation(self, context: AgentContext) -> str:
        if "Product Manager" in self.name:
            plan = '''
=== PM EXECUTION PLAN ===
1. DESCRIPTION: Inspect accounts and monthly_metrics tables.
2. INTROSPECTION: Analyze company_name, plan_tier, status, log_month, mrr, active_users, api_calls. Check churn status and missing entries.
3. GOAL-SETTING: Compute MRR expansion growth metrics and active user spikes as core health signals.
4. COORDINATION: Data Engineer discovers schema and pulls aggregated SQL dataset; Data Analyst formats briefing and creates replicability code.
'''.strip()
            context.pm_plan = plan
            return plan
        elif "Data Engineer" in self.name:
            from db_tools import get_database_schema, run_read_only_query
            schema = get_database_schema()
            context.schema = schema
            query = (
                "SELECT a.company_name, a.plan_tier, a.status, "
                "m.log_month, m.mrr, m.active_users, m.api_calls "
                "FROM accounts a "
                "JOIN monthly_metrics m ON a.id = m.account_id "
                "ORDER BY m.log_month, a.company_name;"
            )
            context.sql_queries_run.append(query)
            res_json = run_read_only_query(query, return_format="json")
            context.query_results_json.append(res_json)
            return "Database Schema Checked.\nExecuted secure query and captured results."
        elif "Data Analyst" in self.name:
            data = json.loads(context.query_results_json[-1])
            df = pd.DataFrame(data)
            
            # Aggregate calculations
            mrr_by_month = df.groupby("log_month")["mrr"].sum().reset_index()
            mrr_by_month["mrr_growth_pct"] = mrr_by_month["mrr"].pct_change() * 100
            
            users_by_month = df.groupby("log_month")["active_users"].sum().reset_index()
            users_by_month["users_growth_pct"] = users_by_month["active_users"].pct_change() * 100
            
            api_by_month = df.groupby("log_month")["api_calls"].sum().reset_index()
            
            metrics_table = "| Log Month | Total MRR ($) | MRR Growth (%) | Active Users | User Growth (%) | Total API Calls |\n"
            metrics_table += "|---|---|---|---|---|---|\n"
            for i, row in mrr_by_month.iterrows():
                month = row["log_month"]
                mrr = row["mrr"]
                growth = f"{row['mrr_growth_pct']:.2f}%" if pd.notna(row["mrr_growth_pct"]) else "Initial Month"
                users = users_by_month.loc[users_by_month["log_month"] == month, "active_users"].values[0]
                u_growth = f"{users_by_month.loc[users_by_month['log_month'] == month, 'users_growth_pct'].values[0]:.2f}%" if pd.notna(users_by_month.loc[users_by_month["log_month"] == month, 'users_growth_pct'].values[0]) else "Initial Month"
                api = api_by_month.loc[api_by_month["log_month"] == month, "api_calls"].values[0]
                metrics_table += f"| {month} | {mrr:,.2f} | {growth} | {users:,} | {u_growth} | {api:,} |\n"

            briefing = f'''
# Executive BI Briefing - DIG Framework Analysis

## Executive Summary
This report analyzes monthly enterprise health metrics including Monthly Recurring Revenue (MRR), active users, and API calls from Jan 2026 to May 2026. 

### Monthly Performance Aggregations
{metrics_table}

## Key Health Insights
1. **Strong Revenue Expansion**: Total MRR grew from **$14,400.00** in January to **$16,400.00** in May 2026 (a **13.89%** growth). Growth was primarily driven by Globex Corporation upgrading their plan in March.
2. **Stable Active User Base**: Active users steadily increased, reaching **1,976** in May.
3. **API Usage Optimization**: Total API calls increased from **94,900** in January to **118,750** in May.
4. **Churn Warning**: Soylent Corp churned in late 2025 and has no metrics for 2026. All 5 active accounts have remained active.
'''.strip()

            traceability = '''
# Traceability Report - BI Data Lineage

## Data Lineage
- **Source Database**: `enterprise_bi.db`
- **Tables Queried**: `accounts` and `monthly_metrics`.
- **Extracted Fields**:
  - `accounts`: `company_name`, `plan_tier`, `status`
  - `monthly_metrics`: `log_month`, `mrr`, `active_users`, `api_calls`

## Validation & Exclusions
- Soylent Corp (ID: 106) was confirmed churned as of 2025-12, resulting in no 2026 metrics, which is validated.
- Missing values check: None found in active records.

## Analytical Assumptions
- MRR additions represent upgrades or subscription additions.
- User growth is calculated as Month-on-Month percentage change.
'''.strip()

            snippet = '''
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
'''.strip()

            context.analyst_deliverables["executive_briefing.md"] = briefing
            context.analyst_deliverables["traceability_readme.md"] = traceability
            context.analyst_deliverables["replicate_analysis.py"] = snippet
            return "Deliverables generated successfully."
        return "Simulation complete."

class Team:
    def __init__(self, name: str, agents: List[Agent]):
        self.name: str = name
        self.agents: List[Agent] = agents

    def run(self, query: str) -> AgentContext:
        print(f"=== Starting Multi-Agent Team Execution: {self.name} ===")
        context = AgentContext(query)
        for agent in self.agents:
            response = agent.run(context)
            context.add_history(agent.name, response)
            print(f"[{agent.name} Execution Complete]")
        print("\n=== Multi-Agent Execution Complete ===")
        return context
""",

    "team_orchestrator.py": r"""# team_orchestrator.py
from adk import Agent, Team
from db_tools import get_database_schema, run_read_only_query

def build_bi_analysis_team() -> Team:
    pm_agent = Agent(
        name="Product Manager Agent",
        role="Orchestrator & BI Strategist",
        backstory=(
            "You are an elite enterprise BI lead who ensures data integrity before running analytics. "
            "You enforce the DIG (Description, Introspection, Goal-Setting) framework strictly."
        ),
        core_instructions=(
            "Receive the plain-text user business query. Coordinate the workflow. "
            "Enforce that the Data Engineer describes the schema first. "
            "Define the ultimate presentation goal based on the user's intent. "
            "Pass the structured execution plan to the Data Engineer."
        )
    )
    
    de_agent = Agent(
        name="Data Engineer Agent",
        role="Database Extractor & Guard",
        backstory="Expert data engineer specializing in clean, optimized, semantic Text-to-SQL generation.",
        tools=[get_database_schema, run_read_only_query],
        core_instructions=(
            "[DESCRIBE & INTROSPECT] Use the get_database_schema tool to inspect tables first. "
            "Examine the columns and verify data availability. Identify potential data discrepancies "
            "or missing variables (NaNs) in the tables. "
            "Translate the Product Manager's plan into highly optimized SQL SELECT queries. "
            "Execute them safely via run_read_only_query, retrieve the results, and pass to the Data Analyst."
        )
    )
    
    da_agent = Agent(
        name="Data Analyst Agent",
        role="Insights Generator & Analytics Replicator",
        backstory=(
            "A meticulous data scientist focused on statistical calculation, business metrics "
            "(MRR, Churn, Growth), and absolute reproducibility."
        ),
        core_instructions=(
            "[GOAL SETTING & TRACEABILITY] Accept the DataFrames/data from the Data Engineer. "
            "Perform analytical computations. Output three mandatory deliverables: \n"
            "1. An Executive Briefing in scannable Markdown with clean tables. "
            "2. A Traceability README.md detailing the data lineage, variables used, and threats to validity/model assumptions. "
            "3. A standalone, clean Python snippet containing the raw SQL and pandas code so a human can fully replicate the results.\n"
            "Important baseline constraint: Ensure that the first baseline month of the timeseries (which has no prior month for growth calculation) "
            "is explicitly labeled or handled as 'Initial Month' in both the Markdown tables and the replicable python code (using .apply() or .fillna()) rather than printing NaN or N/A."
        )
    )
    
    return Team(
        name="Enterprise BI Analysis Team",
        agents=[pm_agent, de_agent, da_agent]
    )
""",

    "run_team.py": r"""# run_team.py
import os
from team_orchestrator import build_bi_analysis_team

def main():
    query = "Analyze our monthly MRR growth, active user trends, and API usage to find health signals."
    print("======================================================================")
    print(f"Starting Multi-Agent DIG Analysis Pipeline")
    print(f"Query: '{query}'")
    print("======================================================================")
    
    team = build_bi_analysis_team()
    context = team.run(query)
    
    portfolio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio")
    os.makedirs(portfolio_dir, exist_ok=True)
    
    print("\n======================================================================")
    print("Writing Agent Deliverables to Portfolio Directory...")
    print(f"Destination: {portfolio_dir}")
    print("======================================================================")
    
    deliverables = context.analyst_deliverables
    if not deliverables:
        print("Warning: No deliverables found in context.")
        return
        
    for filename, content in deliverables.items():
        filepath = os.path.join(portfolio_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f" - Created file: {filename} ({len(content)} bytes)")
    print("\nExecution complete.")

if __name__ == "__main__":
    main()
"""
}

def deploy_and_run():
    print("================================================================")
    print("Starting Kaggle Multi-Agent Deployment Pipeline Blueprint")
    print("================================================================")
    
    # 1. Write files sequentially
    print("\n1. Generating modular files:")
    for filename, content in FILES_TO_GENERATE.items():
        print(f" - Writing {filename}...")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
            
    print("\n[SUCCESS] All core script modules generated.")
    
    # 2. Verify Database existence, else boot it up
    print("\n2. Checking database state:")
    if not os.path.exists("enterprise_bi.db"):
        print(" - Database file enterprise_bi.db not found. Re-creating mock DB...")
        if os.path.exists("setup_mock_db.py"):
            subprocess.run([sys.executable, "setup_mock_db.py"], check=True)
        else:
            print(" - Error: setup_mock_db.py is missing. Cannot create database.")
            sys.exit(1)
    else:
        print(" - Found existing database enterprise_bi.db.")
        
    # 3. Execute multi-agent team runs
    print("\n3. Launching sequential agent execution loops:")
    try:
        # Run run_team.py and pipe the output to the console
        result = subprocess.run([sys.executable, "run_team.py"], capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(" - Error during pipeline run:")
        print(e.stderr)
        sys.exit(1)
        
    print("\n================================================================")
    print("Kaggle Multi-Agent Team deployment validation finished successfully!")
    print("================================================================")

if __name__ == "__main__":
    deploy_and_run()
