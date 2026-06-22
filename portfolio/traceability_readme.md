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