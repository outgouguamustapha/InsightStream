# team_orchestrator.py
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
