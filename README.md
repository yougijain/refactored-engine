# SaaS Revenue Analytics

Tableau dashboards for a B2B SaaS business: MRR, retention, cohorts, churn and account health.
Data is synthetic, built with Python and DuckDB.

## Run

```bash
pip install -r requirements.txt
python src/generate_raw_data.py
python src/build_marts.py
pytest -q
```

Open `tableau/saas_revenue_intelligence.twb` in Tableau Desktop or Tableau Public (2022.4+).

## Dashboards

- **Executive Summary**: MRR trend, MRR movement, net revenue retention
- **Retention & Churn**: cohort retention, churn reasons, churn by health tier
- **Account Health**: at-risk accounts by usage and revenue

## Structure

```
src/        data generator, SQL models, build script
data/       raw CSVs and output tables for Tableau
tableau/    workbook
tests/      data checks and workbook checks
tools/      rebuilds the workbook from the table schemas
docs/       metric definitions and findings
```

## Key findings

- $76.4M ARR, 938 customers
- Net revenue retention is 104.5%, but gross retention is only 80.2%
- Low product adoption is the biggest cause of lost revenue
- About 24% of churn comes from failed payments
- Accounts in the lowest health tier churn 3.3x more often than healthy ones
