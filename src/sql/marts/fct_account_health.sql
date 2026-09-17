-- Monthly usage, health score and 90-day churn flag per customer.
create or replace table fct_account_health as
with churn_events as (
    select customer_id, month as churn_month
    from fct_mrr_monthly
    where movement_type = 'Churn'
),
scored as (
    select
        u.customer_id,
        u.month,
        c.company_name,
        c.segment,
        c.industry,
        c.region,
        c.acquisition_channel,
        f.plan_name,
        f.billing_period,
        f.tenure_months,
        f.mrr,
        u.licensed_seats,
        u.active_users,
        u.seat_utilization,
        u.sessions,
        case when u.active_users = 0 then 0
             else round(u.sessions::double / u.active_users, 2) end as sessions_per_active_user,
        u.feature_adoption_score,
        u.support_tickets,
        u.csat_score,
        round(100 * greatest(0, least(1,
              0.40 * least(u.seat_utilization, 1.0)
            + 0.25 * (u.csat_score / 5.0)
            + 0.25 * (u.feature_adoption_score / 100.0)
            + 0.10 * least(f.tenure_months / 24.0, 1.0)
            - 0.15 * least(u.support_tickets / 12.0, 1.0)
        )), 1) as health_score
    from stg_product_usage u
    join stg_customers c on c.customer_id = u.customer_id
    join fct_mrr_monthly f on f.customer_id = u.customer_id and f.month = u.month
    where f.mrr > 0
)
select
    s.*,
    case
        when s.health_score >= 70 then 'Healthy'
        when s.health_score >= 55 then 'Watch'
        when s.health_score >= 40 then 'At Risk'
        else 'Critical'
    end as risk_tier,
    case
        when s.health_score >= 70 then 1
        when s.health_score >= 55 then 2
        when s.health_score >= 40 then 3
        else 4
    end as risk_tier_rank,
    case when exists (
        select 1 from churn_events e
        where e.customer_id = s.customer_id
          and e.churn_month > s.month
          and e.churn_month <= date_add(s.month, to_months(3))
    ) then 1 else 0 end as churned_within_90_days
from scored s;
