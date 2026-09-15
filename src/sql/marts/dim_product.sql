-- One row per product, with the margin the buying team quoted (list_margin_rate) next to
-- the margin the product actually delivered after discount, returns and freight. The gap
-- between those two columns is the whole point of the table.
create or replace table dim_product as
with performance as (
    select
        e.product_id,
        count(*)                                        as order_lines,
        sum(e.quantity)                                 as units_sold,
        sum(e.quantity_returned)                        as units_returned,
        round(sum(e.gross_revenue), 2)                  as gross_revenue,
        round(sum(e.discount_amount), 2)                as discount_amount,
        round(sum(e.net_revenue), 2)                    as net_revenue,
        round(sum(e.refund_amount), 2)                  as refund_amount,
        round(sum(e.cogs_net), 2)                       as cogs,
        round(sum(e.net_shipping_cost), 2)              as net_shipping_cost,
        round(sum(e.contribution_margin), 2)            as contribution_margin
    from int_order_item_economics e
    group by e.product_id
)
select
    p.product_id,
    p.sku,
    p.product_name,
    p.category,
    p.subcategory,
    p.brand,
    p.unit_cost,
    p.list_price,
    p.weight_kg,
    p.list_margin_rate,

    coalesce(pf.order_lines, 0)          as order_lines,
    coalesce(pf.units_sold, 0)           as units_sold,
    coalesce(pf.units_returned, 0)       as units_returned,
    coalesce(pf.gross_revenue, 0)        as gross_revenue,
    coalesce(pf.discount_amount, 0)      as discount_amount,
    coalesce(pf.net_revenue, 0)          as net_revenue,
    coalesce(pf.refund_amount, 0)        as refund_amount,
    coalesce(pf.cogs, 0)                 as cogs,
    coalesce(pf.net_shipping_cost, 0)    as net_shipping_cost,
    coalesce(pf.contribution_margin, 0)  as contribution_margin,

    round(pf.discount_amount / nullif(pf.gross_revenue, 0), 4)        as avg_discount_rate,
    round(pf.units_returned * 1.0 / nullif(pf.units_sold, 0), 4)      as unit_return_rate,
    round(pf.contribution_margin / nullif(pf.net_revenue, 0), 4)      as contribution_margin_rate,
    -- Negative means the product sold for less margin than the buying sheet promised.
    round(pf.contribution_margin / nullif(pf.net_revenue, 0) - p.list_margin_rate, 4) as margin_rate_vs_list
from stg_products p
left join performance pf on pf.product_id = p.product_id;
