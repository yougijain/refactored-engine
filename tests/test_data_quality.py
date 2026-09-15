"""Contract tests for the published marts.

These are the assertions that let the README claim every number on a dashboard is
auditable. They fall into four groups:

  * shape      - the mart exists, has rows, and has a unique key;
  * integrity  - keys resolve, quantities are possible, dates are ordered;
  * identity   - the margin walk adds up, and allocations reconcile to their source;
  * agreement  - two marts that report the same total actually report the same total.

Money is compared with a small tolerance: every mart rounds to pence, so aggregates of
tens of thousands of rounded rows differ from an unrounded total by a few pence.
"""

from __future__ import annotations

import pytest

PENCE = 1.00       # tolerance for sums over rounded rows
ALLOCATION = 5.00  # freight is rounded per line, so reconciliation scales with line count

MARTS = [
    "dim_customer",
    "dim_product",
    "fct_order_items",
    "fct_returns",
    "fct_fulfilment_daily",
    "fct_discount_bands",
    "fct_cohort_repeat",
    "fct_channel_payback",
]

PRIMARY_KEYS = {
    "dim_customer": ["customer_id"],
    "dim_product": ["product_id"],
    "fct_order_items": ["order_item_id"],
    "fct_returns": ["return_id"],
    "fct_fulfilment_daily": ["order_date", "fulfilment_centre", "carrier"],
    "fct_discount_bands": ["order_month", "category", "discount_band"],
    "fct_cohort_repeat": ["cohort_month", "first_order_experience", "period_index"],
    "fct_channel_payback": ["acquisition_channel", "signup_month", "period_index"],
}


def scalar(con, sql: str):
    return con.execute(sql).fetchone()[0]


# ----------------------------------------------------------------------------- shape ---

@pytest.mark.parametrize("mart", MARTS)
def test_mart_is_populated(warehouse, mart):
    assert scalar(warehouse, f"select count(*) from {mart}") > 0


@pytest.mark.parametrize("mart", MARTS)
def test_mart_is_published_as_csv(marts_dir, mart):
    path = marts_dir / f"{mart}.csv"
    assert path.exists(), f"{path.name} missing - run python src/build_marts.py"
    assert path.stat().st_size > 0


@pytest.mark.parametrize("mart,keys", sorted(PRIMARY_KEYS.items()))
def test_primary_key_is_unique(warehouse, mart, keys):
    cols = ", ".join(keys)
    duplicates = scalar(
        warehouse,
        f"select count(*) from (select {cols} from {mart} group by {cols} having count(*) > 1)",
    )
    assert duplicates == 0, f"{mart} has {duplicates} duplicated keys on ({cols})"


@pytest.mark.parametrize("mart,keys", sorted(PRIMARY_KEYS.items()))
def test_primary_key_is_not_null(warehouse, mart, keys):
    for key in keys:
        assert scalar(warehouse, f"select count(*) from {mart} where {key} is null") == 0


# ------------------------------------------------------------------------- integrity ---

def test_order_items_resolve_to_dimensions(warehouse):
    assert scalar(warehouse, """
        select count(*) from fct_order_items f
        left join dim_customer c on c.customer_id = f.customer_id
        left join dim_product  p on p.product_id  = f.product_id
        where c.customer_id is null or p.product_id is null
    """) == 0


def test_returns_resolve_to_order_items(warehouse):
    assert scalar(warehouse, """
        select count(*) from fct_returns r
        left join fct_order_items f on f.order_item_id = r.order_item_id
        where f.order_item_id is null
    """) == 0


def test_returned_quantity_never_exceeds_ordered(warehouse):
    assert scalar(warehouse, "select count(*) from fct_order_items where quantity_returned > quantity") == 0


def test_returns_happen_after_the_order(warehouse):
    assert scalar(warehouse, "select count(*) from fct_returns where return_date < order_date") == 0


def test_delivery_dates_are_ordered(warehouse):
    assert scalar(warehouse, """
        select count(*) from stg_orders
        where is_shipped and delivered_date < shipped_date
    """) == 0


def test_store_collected_orders_are_excluded_from_the_sla(warehouse):
    """Orders with no promise date cannot be late, so they must not dilute the denominator."""
    assert scalar(warehouse, """
        select count(*) from fct_fulfilment_daily where fulfilment_centre = 'Store Pickup'
    """) == 0
    assert scalar(warehouse, """
        select count(*) from stg_orders where not is_shipped and promised_delivery_date is not null
    """) == 0


def test_discount_bands_match_their_boundaries(warehouse):
    assert scalar(warehouse, """
        select count(*) from fct_order_items
        where (discount_rate = 0            and discount_band <> '0%')
           or (discount_rate > 0 and discount_rate < 0.10  and discount_band <> '1-10%')
           or (discount_rate >= 0.10 and discount_rate < 0.20 and discount_band <> '10-20%')
           or (discount_rate >= 0.20 and discount_rate < 0.30 and discount_band <> '20-30%')
           or (discount_rate >= 0.30 and discount_band <> '30%+')
    """) == 0


def test_cohort_rates_are_proportions(warehouse):
    assert scalar(warehouse, """
        select count(*) from fct_cohort_repeat
        where active_rate < 0 or active_rate > 1 or active_customers > cohort_customers
    """) == 0


def test_cohort_size_is_fixed_within_a_cohort(warehouse):
    """The denominator must not move as the cohort ages, or the curve is meaningless."""
    assert scalar(warehouse, """
        select count(*) from (
            select cohort_month, first_order_experience
            from fct_cohort_repeat
            group by 1, 2
            having count(distinct cohort_customers) > 1
        )
    """) == 0


def test_cohort_periods_are_dense(warehouse):
    """Every month between a cohort's first and last observed period must have a row."""
    assert scalar(warehouse, """
        select count(*) from (
            select cohort_month, first_order_experience,
                   max(period_index) - min(period_index) + 1 as expected,
                   count(*) as actual
            from fct_cohort_repeat
            group by 1, 2
            having expected <> actual
        )
    """) == 0


# -------------------------------------------------------------------------- identity ---

def test_contribution_margin_identity(warehouse):
    """CM must equal realised revenue less net COGS less net freight, with nothing hidden."""
    gap = scalar(warehouse, """
        select sum(contribution_margin) - sum(realised_revenue - cogs - net_shipping_cost)
        from fct_order_items
    """)
    assert abs(float(gap)) < PENCE


def test_realised_revenue_identity(warehouse):
    gap = scalar(warehouse, """
        select sum(realised_revenue) - sum(net_revenue - refund_amount) from fct_order_items
    """)
    assert abs(float(gap)) < PENCE


def test_net_revenue_identity(warehouse):
    gap = scalar(warehouse, """
        select sum(net_revenue) - sum(gross_revenue - discount_amount) from fct_order_items
    """)
    assert abs(float(gap)) < PENCE


def test_shipping_allocation_reconciles_to_the_order_header(warehouse):
    """Freight is allocated across lines; the allocation must not create or lose money."""
    gap = scalar(warehouse, """
        select (select sum(net_shipping_cost) from fct_order_items)
             - (select sum(shipping_cost - shipping_fee_charged) from stg_orders)
    """)
    assert abs(float(gap)) < ALLOCATION


def test_cogs_recovery_only_on_restocked_returns(warehouse):
    assert scalar(warehouse, """
        select count(*) from int_order_item_economics
        where not is_restocked and cogs_recovered <> 0
    """) == 0


def test_payback_identity(warehouse):
    assert scalar(warehouse, """
        select count(*) from fct_channel_payback
        where abs(cumulative_margin_net_of_cac
                  - (cumulative_contribution_margin - acquisition_spend)) > 0.01
    """) == 0


def test_fulfilment_counts_add_up(warehouse):
    assert scalar(warehouse, """
        select count(*) from fct_fulfilment_daily where on_time_orders + late_orders <> orders
    """) == 0


# ------------------------------------------------------------------------- agreement ---

def test_marts_agree_on_total_net_revenue(warehouse):
    fact = float(scalar(warehouse, "select sum(net_revenue) from fct_order_items"))
    for mart, column in [("dim_product", "net_revenue"),
                         ("dim_customer", "lifetime_net_revenue"),
                         ("fct_discount_bands", "net_revenue")]:
        other = float(scalar(warehouse, f"select sum({column}) from {mart}"))
        assert abs(fact - other) < PENCE, f"{mart}.{column} disagrees with fct_order_items"


def test_marts_agree_on_total_contribution_margin(warehouse):
    fact = float(scalar(warehouse, "select sum(contribution_margin) from fct_order_items"))
    for mart in ["dim_product", "fct_discount_bands"]:
        other = float(scalar(warehouse, f"select sum(contribution_margin) from {mart}"))
        assert abs(fact - other) < PENCE, f"{mart} disagrees with fct_order_items"


def test_customer_order_counts_agree(warehouse):
    assert scalar(warehouse, """
        select count(*) from (
            select c.customer_id
            from dim_customer c
            left join (select customer_id, count(distinct order_id) n
                       from fct_order_items group by 1) f on f.customer_id = c.customer_id
            where c.orders <> coalesce(f.n, 0)
        )
    """) == 0


def test_every_customer_with_orders_has_a_cohort(warehouse):
    assert scalar(warehouse, "select count(*) from dim_customer where orders > 0 and cohort_month is null") == 0


def test_no_activity_outside_the_source_window(warehouse):
    lo, hi = warehouse.execute("select min(order_date), max(order_date) from stg_orders").fetchone()
    bad = scalar(warehouse, f"""
        select count(*) from fct_order_items where order_date < date '{lo}' or order_date > date '{hi}'
    """)
    assert bad == 0
