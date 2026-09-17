-- One row per customer with lifetime and current metrics.
create or replace table dim_customer as
with revenue as (
    select
        customer_id,
        min(cohort_month)                                   as cohort_month,
        max(month) filter (where mrr > 0)                   as last_active_month,
        count(*) filter (where mrr > 0)                     as active_months,
        sum(mrr)                                            as lifetime_recognised_mrr,
        max(mrr)                                            as peak_mrr,
        arg_min(mrr, month) filter (where mrr > 0)          as initial_mrr,
        arg_max(mrr, month) filter (where mrr > 0)          as latest_mrr,
        arg_max(plan_name, month) filter (where mrr > 0)    as latest_plan_name,
        arg_max(billing_period, month) filter (where mrr > 0) as latest_billing_period,
        arg_max(seats, month) filter (where mrr > 0)        as latest_seats,
        count(*) filter (where movement_type = 'Expansion') as expansion_events,
        count(*) filter (where movement_type = 'Contraction') as contraction_events
    from fct_mrr_monthly
    group by 1
),
churn as (
    select customer_id, max(month) as churn_month,
           arg_max(churn_reason, month) as churn_reason,
           arg_max(churn_type, month)   as churn_type
    from fct_mrr_monthly
    where movement_type = 'Churn'
    group by 1
),
billings as (
    select
        customer_id,
        sum(amount) filter (where status = 'paid')   as lifetime_billings,
        sum(amount) filter (where status = 'failed') as failed_billings,
        count(*) filter (where status = 'failed')    as failed_invoices,
        avg(date_diff('day', invoice_date, paid_date)) filter (where paid_date is not null) as avg_days_to_pay
    from stg_invoices
    group by 1
),
engagement as (
    select
        customer_id,
        avg(seat_utilization)           as avg_seat_utilization,
        avg(csat_score)                 as avg_csat,
        sum(support_tickets)            as total_support_tickets,
        arg_max(health_score, month)    as latest_health_score,
        arg_max(risk_tier, month)       as latest_risk_tier
    from fct_account_health
    group by 1
),
reporting_window as (
    select max(month) as latest_month from fct_mrr_monthly
)
select
    c.customer_id,
    c.company_name,
    c.segment,
    c.industry,
    c.region,
    c.country,
    c.acquisition_channel,
    c.sales_rep,
    c.signup_month,
    r.cohort_month,
    r.last_active_month,
    r.active_months,
    case when r.last_active_month = w.latest_month then 1 else 0 end as is_active,
    ch.churn_month,
    ch.churn_reason,
    ch.churn_type,
    round(r.initial_mrr, 2)                                  as initial_mrr,
    round(case when r.last_active_month = w.latest_month then r.latest_mrr else 0 end, 2) as current_mrr,
    round(r.peak_mrr, 2)                                     as peak_mrr,
    round(r.lifetime_recognised_mrr, 2)                      as lifetime_recognised_revenue,
    round(coalesce(b.lifetime_billings, 0), 2)               as lifetime_billings,
    round(coalesce(b.failed_billings, 0), 2)                 as failed_billings,
    coalesce(b.failed_invoices, 0)                           as failed_invoices,
    round(coalesce(b.avg_days_to_pay, 0), 1)                 as avg_days_to_pay,
    r.latest_plan_name,
    r.latest_billing_period,
    r.latest_seats,
    r.expansion_events,
    r.contraction_events,
    round(case when r.initial_mrr = 0 then null else r.latest_mrr / r.initial_mrr end, 3) as net_expansion_ratio,
    round(e.avg_seat_utilization, 3)                         as avg_seat_utilization,
    round(e.avg_csat, 2)                                     as avg_csat,
    e.total_support_tickets,
    e.latest_health_score,
    e.latest_risk_tier
from stg_customers c
join revenue r          on r.customer_id = c.customer_id
left join churn ch      on ch.customer_id = c.customer_id
left join billings b    on b.customer_id = c.customer_id
left join engagement e  on e.customer_id = c.customer_id
cross join reporting_window w;
