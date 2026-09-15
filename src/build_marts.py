"""Build the analytics warehouse: raw CSV extracts -> staging -> intermediate -> marts.

Run with `python src/build_marts.py`. The DuckDB file is a build artifact and is not
committed; the CSVs in data/marts are the published interface the Tableau workbook reads.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MARTS_DIR = ROOT / "data" / "marts"
SQL_DIR = Path(__file__).resolve().parent / "sql"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"

RAW_SOURCES = {
    "raw_customers": "customers.csv",
    "raw_products": "products.csv",
    "raw_orders": "orders.csv",
    "raw_order_items": "order_items.csv",
    "raw_returns": "returns.csv",
    "raw_marketing_spend": "marketing_spend.csv",
}

# Dependency order is listed rather than inferred. It is short, and an explicit list fails
# loudly when a model is added without being wired in.
MODELS = [
    "staging/stg_customers.sql",
    "staging/stg_products.sql",
    "staging/stg_orders.sql",
    "staging/stg_order_items.sql",
    "staging/stg_returns.sql",
    "staging/stg_marketing_spend.sql",
    "intermediate/int_order_item_economics.sql",
    "intermediate/int_month_spine.sql",
    "intermediate/int_customer_first_order.sql",
]

PUBLISHED_MARTS: list[str] = []


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
        # all_varchar keeps type coercion in the staging layer, where it is visible and tested.
        con.execute(
            f"create or replace view {view} as "
            f"select * from read_csv_auto('{path}', header=true, all_varchar=true)"
        )


def run_models(con: duckdb.DuckDBPyConnection) -> None:
    for relative in MODELS:
        con.execute((SQL_DIR / relative).read_text(encoding="utf-8"))
        print(f"  built {relative}")


def export_marts(con: duckdb.DuckDBPyConnection) -> None:
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    for table in PUBLISHED_MARTS:
        target = (MARTS_DIR / f"{table}.csv").as_posix()
        con.execute(f"copy (select * from {table}) to '{target}' (header, delimiter ',')")
        rows = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  {table + '.csv':<32} {rows:>7,} rows")


def main() -> None:
    con = connect()
    try:
        register_raw(con)
        print(f"Building models in {WAREHOUSE.name}")
        run_models(con)
        if PUBLISHED_MARTS:
            print(f"\nExporting marts to {MARTS_DIR}")
            export_marts(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
