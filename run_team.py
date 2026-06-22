# run_team.py
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
