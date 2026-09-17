-- Subscription history with MRR. One row per change.
create or replace view stg_subscriptions as
select
    s.subscription_id,
    s.customer_id,
    s.plan_id,
    p.plan_name,
    p.plan_tier,
    s.billing_period,
    cast(s.seats as integer)              as seats,
    cast(s.discount_pct as decimal(5, 3)) as discount_pct,
    cast(s.start_date as date)            as start_date,
    try_cast(nullif(s.end_date, '') as date) as end_date,
    nullif(s.end_reason, '')              as end_reason,
    nullif(s.churn_type, '')              as churn_type,
    nullif(s.churn_reason, '')            as churn_reason,
    round(p.list_price_per_seat_month * cast(s.seats as integer) * (1 - cast(s.discount_pct as double)), 2) as mrr
from raw_subscriptions s
join stg_plans p on p.plan_id = s.plan_id;
