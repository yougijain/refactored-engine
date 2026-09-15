-- Returns from the reverse-logistics extract. One row per return; a line can be returned
-- at most once in this source system, which int_order_item_economics asserts by joining
-- one-to-one rather than aggregating.
create or replace view stg_returns as
select
    return_id,
    order_item_id,
    cast(return_date as date)                   as return_date,
    cast(quantity_returned as integer)          as quantity_returned,
    return_reason,
    cast(restocked as integer) = 1              as is_restocked,
    cast(refund_amount as decimal(12, 2))       as refund_amount
from raw_returns;
