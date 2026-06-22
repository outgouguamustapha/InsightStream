# skills.md — Agent Skills & Tool Registry

This document catalogues the functional capabilities (skills) and operational tools available to the multi-agent team within the **InsightStream** BI pipeline. 

---

## 🛠️ Global Tool Registry

These tools interface directly with the database layer via an engine-level sandboxed connection authorizer, enforcing absolute read-only safety.

| Tool Name | Bound Agent | Inputs | Return Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `get_database_schema` | Data Engineer | None | `str` (JSON/Text) | Retrieves structural metadata, constraints, and column data types for database tables. |
| `run_read_only_query` | Data Engineer | `sql_query` (str) | `pandas.DataFrame` | Executes a verified, non-mutating SQL SELECT statement against the data warehouse. |

---

## 🤖 Agent-Specific Skill Profiles

### 1. Product Manager Agent (Orchestrator)
The PM Agent acts as the semantic layer router and business logic anchor.

* **Skill: Query Decomposition & Goal-Setting**
    * *Capability:* Translates ambiguous, high-level business queries (e.g., *"Why did our retention or revenue change over the last few quarters?"*) into a structured sequence of analytical milestones.
    * *Implementation:* Enforces the **DIG framework**. Restricts downstream agents from pulling raw data until data definitions and structural constraints are explicitly established.

### 2. Data Engineer Agent (Database Guard)
The Data Engineer acts as the secure execution interface between natural language plans and relational data.

* **Skill: Semantic Text-to-SQL Conversion**
    * *Capability:* Translates abstract parameters (like "MRR growth" or "User churn") into precise, performant SQLite dialects featuring recursive CTEs, conditional joins, and window functions.
* **Skill: Data Description & Introspection**
    * *Capability:* Scans database schemas to proactively catch data anomalies, missing data values (`NaN` fields), or data discrepancies before executing massive pipelines.

### 3. Data Analyst Agent (Reproducibility Lead)
The Data Analyst acts as the quantitative execution engine and compliance inspector.

* **Skill: Quantitative Python Analytics**
    * *Capability:* Consumes structured data frames to calculate operational metrics (MoM variations, active usage velocity, and data distributions) using standard math arrays (`pandas`, `numpy`).
* **Skill: Deterministic Traceability Mapping**
    * *Capability:* Compiles isolated, runtime-ready replication scripts (`replicate_analysis.py`) and standard markdown tables, removing the "black box" variable of standard generative AI outputs.

---

## 📈 Skill Execution Pipeline Flow

1. **User Input** ➔ Raw text prompt received.
2. **PM Agent** ➔ Activates *Goal-Setting Skill* to set analytical constraints.
3. **Data Engineer Agent** ➔ Invokes `get_database_schema` tool ➔ Activates *Introspection Skill* to evaluate schema ➔ Executes code via `run_read_only_query`.
4. **Data Analyst Agent** ➔ Consumes DataFrames ➔ Activates *Quantitative Skill* ➔ Synthesizes final Brief, Traceability logs, and the Python Replication asset.