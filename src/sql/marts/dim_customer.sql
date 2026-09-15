-- One row per customer. Carries the acquisition context, the first-order experience that
-- Q4 splits on, and realised lifetime economics - realised, never forecast, so that every
-- figure on a dashboard can be traced to rows in data/raw.
create or replace table dim_customer as
with lifetime as (
    select
        e.customer_id,
        count(distinct e.order_id)                                  as orders,
        count(*)                                                    as order_lines,
        sum(e.quantity)                                             as units,
        round(sum(e.net_revenue), 2)                                as lifetime_net_revenue,
        round(sum(e.realised_revenue), 2)                           as lifetime_realised_revenue,
        round(sum(e.contribution_margin), 2)                        as lifetime_contribution_margin,
        round(sum(e.refund_amount), 2)                              as lifetime_refunds,
        sum(case when e.is_returned then 1 else 0 end)              as returned_lines,
        min(e.order_date)                                           as first_order_date,
        max(e.order_date)                                           as last_order_date
    from int_order_item_economics e
    group by e.customer_id
),
horizon as (select max(order_date) as as_of_date from stg_orders)
select
    c.customer_id,
    c.signup_date,
    c.signup_month,
    c.acquisition_channel,
    c.region,
    c.city,
    c.is_marketing_opt_in,

    f.cohort_month,
    f.first_order_date,
    f.first_order_channel,
    f.first_order_experience,
    f.first_order_on_time,
    f.first_order_returned,
    f.first_order_net_revenue,

    coalesce(l.orders, 0)                       as orders,
    coalesce(l.units, 0)                        as units,
    coalesce(l.lifetime_net_revenue, 0)         as lifetime_net_revenue,
    coalesce(l.lifetime_contribution_margin, 0) as lifetime_contribution_margin,
    coalesce(l.lifetime_refunds, 0)             as lifetime_refunds,
    round(coalesce(l.lifetime_net_revenue, 0) / nullif(l.orders, 0), 2)      as avg_order_value,
    round(coalesce(l.returned_lines, 0) * 1.0 / nullif(l.order_lines, 0), 4) as return_line_rate,

    l.last_order_date,
    coalesce(l.orders, 0) > 1                                                as is_repeat_customer,
    date_diff('month', f.cohort_month, h.as_of_date)                         as tenure_months,
    date_diff('day', l.last_order_date, h.as_of_date)                        as days_since_last_order,
    coalesce(date_diff('day', l.last_order_date, h.as_of_date) <= 180, false) as is_active
from stg_customers c
left join int_customer_first_order f on f.customer_id = c.customer_id
left join lifetime l                 on l.customer_id = c.customer_id
cross join horizon h;
