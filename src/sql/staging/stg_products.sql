-- Product master from the merchandising system. One row per product.
-- List margin is the headline the buying team quotes; the marts test it against reality.
create or replace view stg_products as
select
    product_id,
    sku,
    product_name,
    category,
    subcategory,
    brand,
    cast(unit_cost as decimal(12, 2))   as unit_cost,
    cast(list_price as decimal(12, 2))  as list_price,
    cast(weight_kg as decimal(8, 2))    as weight_kg,
    round((cast(list_price as double) - cast(unit_cost as double))
          / nullif(cast(list_price as double), 0), 4) as list_margin_rate
from raw_products;
