-- The backbone of the project: one row per order line, carrying the full walk from list
-- price down to contribution margin.
--
-- Three decisions are made here once, so that no mart can quietly disagree with another:
--
--  1. Shipping is an ORDER-level cost but margin is reported at LINE level, so freight is
--     allocated across the lines of a basket by share of net revenue. A fully discounted
--     basket has no revenue to share by, so it falls back to an even split.
--  2. A return reverses revenue in full (the refund), but only recovers COGS when the unit
--     was restocked. Damaged and faulty returns therefore cost the full cost of goods.
--  3. Returns are attributed to the ORDER month, not the return month, so that margin and
--     the returns that eroded it appear in the same row.
create or replace view int_order_item_economics as
with basket as (
    select
        oi.*,
        sum(oi.net_revenue) over (partition by oi.order_id) as order_net_revenue,
        count(*)            over (partition by oi.order_id) as order_line_count
    from stg_order_items oi
),
allocated as (
    select
        b.order_item_id,
        b.order_id,
        b.product_id,
        b.quantity,
        b.unit_price,
        b.discount_amount,
        b.gross_revenue,
        b.net_revenue,
        b.discount_rate,
        case
            when b.order_net_revenue > 0 then cast(b.net_revenue as double) / cast(b.order_net_revenue as double)
            else 1.0 / b.order_line_count
        end as revenue_share
    from basket b
)
select
    a.order_item_id,
    a.order_id,
    a.product_id,
    o.customer_id,

    o.order_date,
    o.order_month,
    o.order_channel,
    o.order_sequence,
    o.is_shipped,
    o.fulfilment_centre,
    o.carrier,
    o.is_on_time,
    o.days_late,
    o.promo_code,

    p.category,
    p.subcategory,
    p.brand,
    p.weight_kg,

    a.quantity,
    a.unit_price,
    a.gross_revenue,
    a.discount_amount,
    a.net_revenue,
    a.discount_rate,

    -- Returns, attributed back to the order month.
    r.return_id is not null                                   as is_returned,
    r.return_reason,
    coalesce(r.quantity_returned, 0)                          as quantity_returned,
    coalesce(r.refund_amount, 0)::decimal(12, 2)              as refund_amount,
    coalesce(r.is_restocked, false)                           as is_restocked,
    r.return_date,

    -- Cost of goods, net of units that came back in resaleable condition.
    round(cast(p.unit_cost as double) * a.quantity, 2)        as cogs_gross,
    round(cast(p.unit_cost as double)
          * case when coalesce(r.is_restocked, false) then coalesce(r.quantity_returned, 0) else 0 end,
          2)                                                  as cogs_recovered,
    round(cast(p.unit_cost as double)
          * (a.quantity - case when coalesce(r.is_restocked, false)
                               then coalesce(r.quantity_returned, 0) else 0 end),
          2)                                                  as cogs_net,

    -- Freight, allocated from the order header.
    round(cast(o.shipping_cost as double) * a.revenue_share, 2)         as shipping_cost_allocated,
    round(cast(o.shipping_fee_charged as double) * a.revenue_share, 2)  as shipping_fee_allocated,
    round((cast(o.shipping_cost as double) - cast(o.shipping_fee_charged as double))
          * a.revenue_share, 2)                                         as net_shipping_cost,

    -- Revenue the business actually kept.
    round(cast(a.net_revenue as double) - coalesce(cast(r.refund_amount as double), 0), 2) as realised_revenue,

    -- Contribution margin = realised revenue - net COGS - net freight.
    round(
        cast(a.net_revenue as double) - coalesce(cast(r.refund_amount as double), 0)
        - cast(p.unit_cost as double)
          * (a.quantity - case when coalesce(r.is_restocked, false)
                               then coalesce(r.quantity_returned, 0) else 0 end)
        - (cast(o.shipping_cost as double) - cast(o.shipping_fee_charged as double)) * a.revenue_share,
        2)                                                    as contribution_margin
from allocated a
join stg_orders o      on o.order_id = a.order_id
join stg_products p    on p.product_id = a.product_id
left join stg_returns r on r.order_item_id = a.order_item_id;
