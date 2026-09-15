-- One row per return, carrying the margin the return destroyed rather than just the refund.
-- `margin_lost` is the difference between what the line would have contributed had it been
-- kept and what it actually contributed, so a restocked return costs only the freight.
create or replace table fct_returns as
select
    r.return_id,
    e.order_item_id,
    e.order_id,
    e.customer_id,
    e.product_id,

    e.order_date,
    e.order_month,
    r.return_date,
    date_diff('day', e.order_date, r.return_date)   as days_to_return,

    e.category,
    e.subcategory,
    e.brand,
    e.order_channel,
    e.fulfilment_centre,
    e.carrier,
    e.is_on_time,

    r.return_reason,
    r.is_restocked,
    -- Damaged and faulty units cannot be resold, so the cost of goods is gone as well.
    case when r.is_restocked then 'Recovered' else 'Written off' end as disposition,
    r.quantity_returned,
    e.quantity                                      as quantity_ordered,
    r.refund_amount,

    round(cast(r.refund_amount as double)
          - case when r.is_restocked then cast(e.cogs_recovered as double) else 0 end, 2)
        ::decimal(14, 2) as margin_lost
from stg_returns r
join int_order_item_economics e on e.order_item_id = r.order_item_id;
