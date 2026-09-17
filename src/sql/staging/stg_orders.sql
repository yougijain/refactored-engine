-- Order header from the OMS extract. One row per order.
--
-- Store-collected orders carry no promise or delivery dates, so every delivery measure is
-- left null rather than defaulted. Downstream models filter on is_shipped so that the
-- on-time denominator only ever contains parcels that could actually be late.
create or replace view stg_orders as
select
    order_id,
    customer_id,
    cast(order_date as date)                              as order_date,
    date_trunc('month', cast(order_date as date))::date   as order_month,
    order_channel,
    cast(order_sequence as integer)                       as order_sequence,
    cast(is_shipped as integer) = 1                       as is_shipped,
    fulfilment_centre,
    nullif(carrier, '')                                   as carrier,
    cast(nullif(promised_delivery_date, '') as date)      as promised_delivery_date,
    cast(nullif(shipped_date, '') as date)                as shipped_date,
    cast(nullif(delivered_date, '') as date)              as delivered_date,
    cast(shipping_fee_charged as decimal(12, 2))          as shipping_fee_charged,
    cast(shipping_cost as decimal(12, 2))                 as shipping_cost,
    payment_method,
    nullif(promo_code, '')                                as promo_code,
    order_status,

    -- Delivery performance, defined once here so no mart can disagree about it.
    date_diff('day', cast(nullif(shipped_date, '') as date),
                     cast(nullif(delivered_date, '') as date))   as transit_days,
    date_diff('day', cast(order_date as date),
                     cast(nullif(delivered_date, '') as date))   as days_to_deliver,
    greatest(date_diff('day', cast(nullif(promised_delivery_date, '') as date),
                              cast(nullif(delivered_date, '') as date)), 0) as days_late,
    case
        when nullif(delivered_date, '') is null then null
        when cast(delivered_date as date) <= cast(promised_delivery_date as date) then true
        else false
    end as is_on_time
from raw_orders;
