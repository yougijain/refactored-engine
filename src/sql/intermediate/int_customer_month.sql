-- Active subscription per customer per month.
create or replace view int_customer_month as
select
    m.month_start as month,
    s.customer_id,
    s.subscription_id,
    s.plan_id,
    s.plan_name,
    s.plan_tier,
    s.billing_period,
    s.seats,
    s.discount_pct,
    s.mrr
from int_month_spine m
join stg_subscriptions s
  on m.month_start >= s.start_date
 and (s.end_date is null or m.month_start < s.end_date);
