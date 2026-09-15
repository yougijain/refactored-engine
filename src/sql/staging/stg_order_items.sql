-- Order lines from the OMS extract. One row per order line; this is the finest grain
-- available and therefore the grain of the revenue fact.
create or replace view stg_order_items as
select
    order_item_id,
    order_id,
    product_id,
    cast(quantity as integer)                       as quantity,
    cast(unit_price as decimal(12, 2))              as unit_price,
    cast(discount_amount as decimal(12, 2))         as discount_amount,
    cast(unit_price as decimal(12, 2)) * cast(quantity as integer) as gross_revenue,
    cast(unit_price as decimal(12, 2)) * cast(quantity as integer)
        - cast(discount_amount as decimal(12, 2))   as net_revenue,
    round(cast(discount_amount as double)
          / nullif(cast(unit_price as double) * cast(quantity as integer), 0), 4)
        ::decimal(9, 4) as discount_rate
from raw_order_items;
