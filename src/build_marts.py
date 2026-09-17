"""Build DuckDB tables from data/raw and export them to data/marts for Tableau."""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MARTS_DIR = ROOT / "data" / "marts"
SQL_DIR = Path(__file__).resolve().parent / "sql"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"

RAW_SOURCES = {
    "raw_plans": "plans.csv",
    "raw_customers": "customers.csv",
    "raw_subscriptions": "subscriptions.csv",
    "raw_invoices": "invoices.csv",
    "raw_product_usage_monthly": "product_usage_monthly.csv",
}

# Run in this order.
MODELS = [
    "staging/stg_plans.sql",
    "staging/stg_customers.sql",
    "staging/stg_subscriptions.sql",
    "staging/stg_invoices.sql",
    "staging/stg_product_usage.sql",
    "intermediate/int_month_spine.sql",
    "intermediate/int_customer_month.sql",
    "intermediate/int_customer_month_grid.sql",
    "marts/fct_mrr_monthly.sql",
    "marts/fct_retention_monthly.sql",
    "marts/fct_retention_ttm.sql",
    "marts/fct_cohort_retention.sql",
    "marts/fct_account_health.sql",
    "marts/dim_customer.sql",
    "marts/fct_invoice.sql",
]

PUBLISHED_MARTS = [
    "dim_customer",
    "fct_mrr_monthly",
    "fct_retention_monthly",
    "fct_retention_ttm",
    "fct_cohort_retention",
    "fct_account_health",
    "fct_invoice",
]


def connect() -> duckdb.DuckDBPyConnection:
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    if WAREHOUSE.exists():
        WAREHOUSE.unlink()
    return duckdb.connect(str(WAREHOUSE))


def register_raw(con: duckdb.DuckDBPyConnection) -> None:
    missing = [name for name in RAW_SOURCES.values() if not (RAW_DIR / name).exists()]
    if missing:
        raise SystemExit(
            f"Missing raw extracts: {', '.join(missing)}. Run `python src/generate_raw_data.py` first."
        )
    for view, filename in RAW_SOURCES.items():
        path = (RAW_DIR / filename).as_posix()
        con.execute(
            f"create or replace view {view} as "
            f"select * from read_csv_auto('{path}', header=true, all_varchar=true)"
        )


def run_models(con: duckdb.DuckDBPyConnection) -> None:
    for relative in MODELS:
        sql_path = SQL_DIR / relative
        con.execute(sql_path.read_text(encoding="utf-8"))
        print(f"  built {relative}")


def export_marts(con: duckdb.DuckDBPyConnection) -> None:
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    for table in PUBLISHED_MARTS:
        target = (MARTS_DIR / f"{table}.csv").as_posix()
        con.execute(f"copy (select * from {table}) to '{target}' (header, delimiter ',')")
        rows = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  {table + '.csv':<30} {rows:>7,} rows")


def summarise(con: duckdb.DuckDBPyConnection) -> None:
    latest = con.execute("select max(month) from fct_mrr_monthly").fetchone()[0]
    mrr, customers = con.execute(
        """
        select sum(ending_mrr), sum(active_customers)
        from fct_retention_monthly
        where month = (select max(month) from fct_retention_monthly)
        """
    ).fetchone()
    nrr, grr = con.execute(
        """
        select sum(retained_mrr) / sum(base_mrr), sum(retained_mrr_capped) / sum(base_mrr)
        from fct_retention_ttm
        where month = (select max(month) from fct_retention_ttm)
        """
    ).fetchone()
    print(
        f"\nLatest month {latest}: ${mrr:,.0f} MRR across {customers:,} customers | "
        f"trailing-12m NRR {nrr:.1%} | GRR {grr:.1%}"
    )


def main() -> None:
    con = connect()
    try:
        register_raw(con)
        print(f"Building models in {WAREHOUSE.name}")
        run_models(con)
        print(f"\nExporting marts to {MARTS_DIR}")
        export_marts(con)
        summarise(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
