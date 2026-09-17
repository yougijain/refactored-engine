-- The published revenue fact. One row per order line, at the same grain as the source
-- system, with the margin walk and just enough dimensional context to stand alone in
-- Tableau without a join.
--
-- Discount bands are cut here rather than in the workbook so that the elasticity sheet and
-- the margin sheets cannot end up using different boundaries.
create or replace table fct_order_items as
select
    e.order_item_id,
    e.order_id,
    e.customer_id,
    e.product_id,

    e.order_date,
    e.order_month,
    e.order_channel,
    e.order_sequence,
    e.order_sequence = 1                as is_first_order,
    c.acquisition_channel,
    c.region,
    c.cohort_month,

    e.is_shipped,
    e.fulfilment_centre,
    e.carrier,
    e.is_on_time,
    e.days_late,

    e.category,
    e.subcategory,
    e.brand,

    e.quantity,
    e.unit_price,
    e.gross_revenue,
    e.discount_amount,
    e.net_revenue,
    e.discount_rate,
    case
        when e.discount_rate = 0     then '0%'
        when e.discount_rate < 0.10  then '1-10%'
        when e.discount_rate < 0.20  then '10-20%'
        when e.discount_rate < 0.30  then '20-30%'
        else '30%+'
    end                                 as discount_band,
    case
        when e.discount_rate = 0     then 0
        when e.discount_rate < 0.10  then 1
        when e.discount_rate < 0.20  then 2
        when e.discount_rate < 0.30  then 3
        else 4
    end                                 as discount_band_rank,

    e.is_returned,
    e.return_reason,
    e.quantity_returned,
    e.refund_amount,
    e.is_restocked,

    e.cogs_net                          as cogs,
    e.net_shipping_cost,
    e.realised_revenue,
    e.contribution_margin
from int_order_item_economics e
join dim_customer c on c.customer_id = e.customer_id;
