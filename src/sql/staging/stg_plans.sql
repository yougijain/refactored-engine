-- Plan price list.
create or replace view stg_plans as
select
    plan_id,
    plan_name,
    cast(plan_tier as integer)                   as plan_tier,
    cast(list_price_per_seat_month as decimal(10, 2)) as list_price_per_seat_month,
    cast(min_seats as integer)                   as min_seats,
    cast(max_seats as integer)                   as max_seats
from raw_plans;
