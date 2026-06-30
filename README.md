# InsightStream: Secure Autonomous Multi-Agent BI Pipeline

InsightStream is a state-of-the-art agentic business intelligence (BI) portal designed to run autonomous analysis pipelines on customer MRR, active users, and API usage data. Utilizing a multi-agent structure and a strict database security sandboxing framework, it provides secure, fully reproducible business analytics.

---

## 🛠️ Architecture & Core Components

The project consists of the following key layers:

### 1. The Multi-Agent Team (DIG Framework)
Defined in `adk.py` and configured in `team_orchestrator.py`:
*   **Product Manager Agent**: Receives raw queries, structures the execution strategy, and defines key metrics and presentation goals.
*   **Data Engineer Agent**: Inspects database schemas, validates table structures, and generates optimized SELECT-only SQL queries to extract data.
*   **Data Analyst Agent**: Runs calculations on the retrieved data to measure metrics (MoM MRR growth, active user trends, API velocity spikes, and churned accounts) and writes out three deliverables:
    1.  *Executive Analytical Briefing* (Markdown)
    2.  *Traceability Report* (Data lineage & threats to validity)
    3.  *Human Verification Script* (Standalone Python script using SQL and pandas)

### 2. Security Sandbox & Database Guard
Located in `db_tools.py`:
*   **Static Regex Sanitization**: Blocks any query containing forbidden write keywords (e.g. `INSERT`, `UPDATE`, `DELETE`, `DROP`, `PRAGMA`).
*   **SQLite Connection Authorizer**: Dynamically blocks write actions at the database layer. Only `SELECT` operations are authorized.

### 3. Interactive Web Portal
Designed in `ui_app.py`:
*   A premium, modern Streamlit UI displaying execution status, agent logs, generated briefings, interactive MRR trend visualizations, and human-replicable verification scripts.
*   Equipped with a `SafeStream` wrapper preventing system pipe disconnection issues (`WinError 233`) under Windows environments.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.8+
*   Dependencies listed in requirements (including `streamlit`, `pandas`, and `sqlite3` built-in library).

### Setup and Running the UI
1.  **Initialize the Database**:
    Initialize the mock database containing customer records and monthly time-series metrics by running:
    ```bash
    python setup_mock_db.py
    ```
2.  **Run the Streamlit App**:
    Start the interactive dashboard locally:
    ```bash
    streamlit run ui_app.py
    ```
3.  **Run CLI Team Execution (Alternative)**:
    Execute the multi-agent pipeline from the CLI and output reports directly to the `portfolio/` directory:
    ```bash
    python run_team.py
    ```

---

## 🧪 Testing and Verification

To verify security restrictions and database access functions:
1.  Run the suite of automated tests:
    ```bash
    python -m unittest test_db_tools.py
    ```
2.  The unit tests in `test_db_tools.py` validate schema reads, output serialization formats, SQL injection defenses, and the connection authorizer's defense-in-depth policy.

---

## 📦 Notebook & Kaggle Deployment

For portable notebook runs or Kaggle deployments:
*   `kaggle_pipeline.py` contains a self-contained pipeline wrapper that unpacks all required files and runs the multi-agent validation suite inline.
