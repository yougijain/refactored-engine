-- Repeat purchase by cohort month x first-order experience x months since first order.
--
-- This is the mart that turns an operations metric into a commercial one. Each customer is
-- pinned to the cohort of their first order AND to how that first order went, then tracked
-- forward. Comparing the 'Clean' and 'Delivered late' curves prices a late delivery.
--
-- The grid is dense: a cohort-period cell with no orders is a zero, not a missing row, so
-- the retention curve does not silently skip months.
create or replace table fct_cohort_repeat as
with base as (
    select customer_id, cohort_month, first_order_experience, acquisition_channel
    from dim_customer
    where cohort_month is not null
),
cohort_size as (
    select cohort_month, first_order_experience, count(*) as cohort_customers
    from base
    group by cohort_month, first_order_experience
),
activity as (
    select
        b.cohort_month,
        b.first_order_experience,
        f.order_month,
        count(distinct f.customer_id)   as active_customers,
        count(distinct f.order_id)      as orders,
        sum(f.net_revenue)              as net_revenue,
        sum(f.contribution_margin)      as contribution_margin
    from fct_order_items f
    join base b on b.customer_id = f.customer_id
    group by b.cohort_month, b.first_order_experience, f.order_month
),
grid as (
    select
        cs.cohort_month,
        cs.first_order_experience,
        cs.cohort_customers,
        s.month                                                as activity_month,
        date_diff('month', cs.cohort_month, s.month)           as period_index
    from cohort_size cs
    join int_month_spine s on s.month >= cs.cohort_month
)
select
    g.cohort_month,
    g.first_order_experience,
    g.activity_month,
    g.period_index,
    g.cohort_customers,

    coalesce(a.active_customers, 0)                             as active_customers,
    coalesce(a.orders, 0)                                       as orders,
    round(coalesce(a.net_revenue, 0), 2)                        as net_revenue,
    round(coalesce(a.contribution_margin, 0), 2)                as contribution_margin,

    round(coalesce(a.active_customers, 0) * 1.0 / g.cohort_customers, 4) as active_rate,

    round(sum(coalesce(a.contribution_margin, 0)) over (
        partition by g.cohort_month, g.first_order_experience
        order by g.period_index
        rows between unbounded preceding and current row), 2)   as cumulative_contribution_margin,

    round(sum(coalesce(a.contribution_margin, 0)) over (
        partition by g.cohort_month, g.first_order_experience
        order by g.period_index
        rows between unbounded preceding and current row) / g.cohort_customers, 2)
                                                                as cumulative_margin_per_customer
from grid g
left join activity a
       on a.cohort_month = g.cohort_month
      and a.first_order_experience = g.first_order_experience
      and a.order_month = g.activity_month;
