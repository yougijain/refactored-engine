-- Monthly product usage per customer.
create or replace view stg_product_usage as
select
    customer_id,
    cast(month as date)                       as month,
    cast(licensed_seats as integer)           as licensed_seats,
    cast(active_users as integer)             as active_users,
    cast(sessions as integer)                 as sessions,
    cast(feature_adoption_score as double)    as feature_adoption_score,
    cast(support_tickets as integer)          as support_tickets,
    cast(csat_score as double)                as csat_score,
    case when cast(licensed_seats as integer) = 0 then 0
         else round(cast(active_users as double) / cast(licensed_seats as double), 4) end as seat_utilization
from raw_product_usage_monthly;
