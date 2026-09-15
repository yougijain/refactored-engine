-- One row per customer who has ordered, describing their first order and how it went.
--
-- The experience flags are the independent variable behind Q4: they classify a customer by
-- something that happened to them once, so repeat behaviour afterwards can be compared
-- across otherwise similar cohorts.
create or replace view int_customer_first_order as
with first_order as (
    select
        o.customer_id,
        o.order_id,
        o.order_date,
        o.order_month,
        o.order_channel,
        o.is_shipped,
        o.fulfilment_centre,
        o.carrier,
        o.is_on_time,
        o.days_late,
        row_number() over (partition by o.customer_id order by o.order_date, o.order_id) as rn
    from stg_orders o
),
first_order_returns as (
    select
        e.order_id,
        max(case when e.is_returned then 1 else 0 end) = 1 as had_return,
        sum(e.net_revenue)                                 as first_order_net_revenue,
        sum(e.contribution_margin)                         as first_order_margin
    from int_order_item_economics e
    group by e.order_id
)
select
    f.customer_id,
    f.order_id                            as first_order_id,
    f.order_date                          as first_order_date,
    f.order_month                         as cohort_month,
    f.order_channel                       as first_order_channel,
    f.fulfilment_centre                   as first_order_fulfilment_centre,
    f.carrier                             as first_order_carrier,
    coalesce(f.is_on_time, true)          as first_order_on_time,
    coalesce(f.days_late, 0)              as first_order_days_late,
    coalesce(r.had_return, false)         as first_order_returned,
    coalesce(r.first_order_net_revenue, 0)::decimal(12, 2) as first_order_net_revenue,
    coalesce(r.first_order_margin, 0)::decimal(12, 2)      as first_order_margin,

    -- The four-way split the First-Order Experience sheet colours by.
    case
        when not coalesce(f.is_on_time, true) and coalesce(r.had_return, false) then 'Late and returned'
        when not coalesce(f.is_on_time, true)                                   then 'Delivered late'
        when coalesce(r.had_return, false)                                      then 'Returned'
        else 'Clean'
    end as first_order_experience
from first_order f
left join first_order_returns r on r.order_id = f.order_id
where f.rn = 1;
