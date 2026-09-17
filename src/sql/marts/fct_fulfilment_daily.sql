-- Delivery performance at order-date x fulfilment centre x carrier. Daily grain so that
-- Tableau can roll up to week or month without the mart having to pick one.
--
-- Store-collected orders are excluded: they have no promise date, so including them would
-- inflate the on-time rate with orders that could never have been late.
create or replace table fct_fulfilment_daily as
with order_value as (
    select order_id, sum(net_revenue) as net_revenue, sum(contribution_margin) as contribution_margin
    from int_order_item_economics
    group by order_id
)
select
    o.order_date,
    o.order_month,
    o.fulfilment_centre,
    o.carrier,

    count(*)                                                        as orders,
    sum(case when o.is_on_time then 1 else 0 end)                   as on_time_orders,
    sum(case when o.is_on_time then 0 else 1 end)                   as late_orders,
    sum(case when o.days_late >= 3 then 1 else 0 end)               as badly_late_orders,

    sum(o.days_late)                                                as days_late_total,
    round(avg(o.days_late), 3)                                      as avg_days_late,
    round(avg(o.days_to_deliver), 3)                                as avg_days_to_deliver,
    round(avg(o.transit_days), 3)                                   as avg_transit_days,

    round(sum(o.shipping_cost), 2)                                  as shipping_cost,
    round(sum(o.shipping_fee_charged), 2)                           as shipping_fee_charged,
    round(sum(o.shipping_cost - o.shipping_fee_charged), 2)         as net_shipping_cost,

    round(sum(v.net_revenue), 2)                                    as net_revenue,
    round(sum(v.contribution_margin), 2)                            as contribution_margin,
    -- Revenue riding on parcels that missed the promise date - the number that sizes the problem.
    round(sum(case when o.is_on_time then 0 else v.net_revenue end), 2) as late_net_revenue
from stg_orders o
join order_value v on v.order_id = o.order_id
where o.is_shipped
  and o.delivered_date is not null
group by o.order_date, o.order_month, o.fulfilment_centre, o.carrier;
