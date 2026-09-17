"""Data checks for the output tables. Run the build scripts first."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse.duckdb"
TOLERANCE = 0.01


@pytest.fixture(scope="session")
def con():
    if not WAREHOUSE.exists():
        pytest.skip("warehouse.duckdb not found - run src/generate_raw_data.py then src/build_marts.py")
    connection = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield connection
    connection.close()


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def rows(con, sql):
    return con.execute(sql).fetchall()


def test_mrr_waterfall_reconciles_every_month(con):
    """ending = starting + new + expansion + reactivation - contraction - churned."""
    breaks = rows(con, f"""
        select month,
               round(sum(mrr), 2) as ending,
               round(sum(prior_mrr) + sum(new_mrr) + sum(expansion_mrr) + sum(reactivation_mrr)
                     - sum(contraction_mrr) - sum(churned_mrr), 2) as rebuilt
        from fct_mrr_monthly
        group by 1
        having abs(ending - rebuilt) > {TOLERANCE}
    """)
    assert breaks == [], f"MRR bridge does not reconcile for: {breaks}"


def test_starting_mrr_equals_prior_month_ending(con):
    breaks = rows(con, f"""
        with monthly as (
            select month, sum(mrr) as ending, sum(prior_mrr) as starting
            from fct_mrr_monthly group by 1
        )
        select m.month, m.starting, p.ending
        from monthly m
        join monthly p on p.month = m.month - interval 1 month
        where abs(m.starting - p.ending) > {TOLERANCE}
    """)
    assert breaks == [], f"Opening balance does not match prior close: {breaks}"


def test_fct_mrr_monthly_grain_is_customer_month(con):
    duplicates = scalar(con, """
        select count(*) from (
            select customer_id, month from fct_mrr_monthly group by 1, 2 having count(*) > 1
        )
    """)
    assert duplicates == 0


def test_subscription_validity_windows_never_overlap(con):
    overlaps = scalar(con, """
        select count(*)
        from stg_subscriptions a
        join stg_subscriptions b
          on a.customer_id = b.customer_id
         and a.subscription_id <> b.subscription_id
         and a.start_date < coalesce(b.end_date, date '9999-12-31')
         and b.start_date < coalesce(a.end_date, date '9999-12-31')
    """)
    assert overlaps == 0


def test_movement_components_are_exclusive_and_signed_correctly(con):
    bad = scalar(con, """
        select count(*) from fct_mrr_monthly
        where new_mrr < 0 or expansion_mrr < 0 or contraction_mrr < 0
           or churned_mrr < 0 or reactivation_mrr < 0
           or (new_mrr > 0)::int + (expansion_mrr > 0)::int + (contraction_mrr > 0)::int
              + (churned_mrr > 0)::int + (reactivation_mrr > 0)::int > 1
    """)
    assert bad == 0


def test_movement_type_matches_the_underlying_numbers(con):
    mismatches = scalar(con, """
        select count(*) from fct_mrr_monthly
        where (movement_type = 'Churn'        and not (prior_mrr > 0 and mrr = 0))
           or (movement_type = 'New'          and not (prior_mrr = 0 and mrr > 0 and tenure_months = 0))
           or (movement_type = 'Reactivation' and not (prior_mrr = 0 and mrr > 0 and tenure_months > 0))
           or (movement_type = 'Expansion'    and not (mrr > prior_mrr and prior_mrr > 0))
           or (movement_type = 'Contraction'  and not (mrr < prior_mrr and mrr > 0))
           or (movement_type = 'Retained'     and mrr <> prior_mrr)
    """)
    assert mismatches == 0


def test_retention_mart_agrees_with_mrr_mart(con):
    breaks = rows(con, f"""
        select r.month, r.total_ending, m.total_ending
        from (select month, round(sum(ending_mrr), 2) as total_ending from fct_retention_monthly group by 1) r
        join (select month, round(sum(mrr), 2)        as total_ending from fct_mrr_monthly        group by 1) m
          on m.month = r.month
        where abs(r.total_ending - m.total_ending) > {TOLERANCE}
    """)
    assert breaks == []


def test_ttm_retention_is_built_from_a_closed_base(con):
    assert scalar(con, "select count(*) from fct_retention_ttm where retained_mrr_capped > base_mrr + 0.01") == 0
    assert scalar(con, "select count(*) from fct_retention_ttm where retained_customers > base_customers") == 0
    assert scalar(con, "select count(*) from fct_retention_ttm where retained_mrr_capped > retained_mrr + 0.01") == 0


def test_ttm_base_matches_the_mrr_mart_twelve_months_earlier(con):
    breaks = rows(con, f"""
        select t.month, t.base, m.ending
        from (select month, round(sum(base_mrr), 2) as base from fct_retention_ttm group by 1) t
        join (select month, round(sum(mrr), 2) as ending from fct_mrr_monthly group by 1) m
          on m.month = t.month - interval 12 month
        where abs(t.base - m.ending) > {TOLERANCE}
    """)
    assert breaks == [], f"TTM base does not match MRR twelve months earlier: {breaks}"


def test_cohort_period_zero_matches_cohort_size(con):
    breaks = scalar(con, """
        select count(*) from fct_cohort_retention
        where period_index = 0 and active_customers <> cohort_customers
    """)
    assert breaks == 0


def test_cohort_never_gains_customers(con):
    breaks = scalar(con, """
        select count(*) from fct_cohort_retention where active_customers > cohort_customers
    """)
    assert breaks == 0


def test_dim_customer_current_mrr_matches_latest_month(con):
    breaks = scalar(con, f"""
        with latest as (
            select customer_id, mrr from fct_mrr_monthly
            where month = (select max(month) from fct_mrr_monthly)
        )
        select count(*)
        from dim_customer d
        left join latest l on l.customer_id = d.customer_id
        where abs(d.current_mrr - coalesce(l.mrr, 0)) > {TOLERANCE}
    """)
    assert breaks == 0


def test_every_fact_row_resolves_to_a_customer(con):
    for table in ("fct_mrr_monthly", "fct_account_health", "fct_invoice"):
        orphans = scalar(con, f"""
            select count(*) from {table} f
            left join dim_customer d on d.customer_id = f.customer_id
            where d.customer_id is null
        """)
        assert orphans == 0, f"{table} has rows with no matching customer"


def test_account_health_scores_are_bounded_and_tiered(con):
    assert scalar(con, "select count(*) from fct_account_health where health_score < 0 or health_score > 100") == 0
    mismatched_tiers = scalar(con, """
        select count(*) from fct_account_health
        where risk_tier <> case
            when health_score >= 70 then 'Healthy'
            when health_score >= 55 then 'Watch'
            when health_score >= 40 then 'At Risk'
            else 'Critical' end
    """)
    assert mismatched_tiers == 0


def test_health_score_actually_separates_churn_risk(con):
    by_tier = dict(rows(con, """
        select risk_tier, avg(churned_within_90_days)
        from fct_account_health
        group by 1
    """))
    assert by_tier["Critical"] > 2 * by_tier["Healthy"], (
        f"Critical {by_tier['Critical']:.1%} vs Healthy {by_tier['Healthy']:.1%}"
    )


def test_invoices_are_internally_consistent(con):
    assert scalar(con, "select count(*) from fct_invoice where amount <= 0") == 0
    assert scalar(con, "select count(*) from fct_invoice where paid_date < invoice_date") == 0
    assert scalar(con, "select count(*) from fct_invoice where status not in ('paid', 'failed')") == 0
    assert scalar(con, "select count(*) from fct_invoice where status = 'paid' and paid_date is null") == 0


def test_key_columns_are_never_null(con):
    checks = {
        "fct_mrr_monthly": ["month", "customer_id", "segment", "mrr", "movement_type"],
        "fct_retention_monthly": ["month", "segment", "ending_mrr"],
        "fct_cohort_retention": ["cohort_month", "period_index", "cohort_customers"],
        "fct_account_health": ["customer_id", "month", "health_score", "risk_tier"],
        "dim_customer": ["customer_id", "segment", "cohort_month", "is_active"],
    }
    for table, columns in checks.items():
        for column in columns:
            nulls = scalar(con, f"select count(*) from {table} where {column} is null")
            assert nulls == 0, f"{table}.{column} contains {nulls} nulls"
