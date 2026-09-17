-- MRR and movement type per customer per month.
create or replace table fct_mrr_monthly as
with monthly as (
    select
        g.customer_id,
        g.month,
        g.first_billed_month,
        coalesce(cm.mrr, 0)        as mrr,
        cm.plan_name,
        cm.plan_tier,
        cm.billing_period,
        cm.seats,
        cm.subscription_id
    from int_customer_month_grid g
    left join int_customer_month cm
      on cm.customer_id = g.customer_id and cm.month = g.month
),
lagged as (
    select
        *,
        coalesce(lag(mrr) over (partition by customer_id order by month), 0) as prior_mrr,
        lag(plan_name)  over (partition by customer_id order by month)       as prior_plan_name,
        lag(seats)      over (partition by customer_id order by month)       as prior_seats
    from monthly
),
classified as (
    select
        *,
        case
            when prior_mrr = 0 and mrr > 0 and month = first_billed_month then 'New'
            when prior_mrr = 0 and mrr > 0                                then 'Reactivation'
            when prior_mrr > 0 and mrr = 0                                then 'Churn'
            when mrr > prior_mrr and prior_mrr > 0                        then 'Expansion'
            when mrr < prior_mrr and mrr > 0                              then 'Contraction'
            else 'Retained'
        end as movement_type
    from lagged
)
select
    c.month,
    c.customer_id,
    cust.company_name,
    cust.segment,
    cust.industry,
    cust.region,
    cust.country,
    cust.acquisition_channel,
    cust.sales_rep,
    c.first_billed_month                                        as cohort_month,
    date_diff('month', c.first_billed_month, c.month)           as tenure_months,
    coalesce(c.plan_name, c.prior_plan_name)                    as plan_name,
    coalesce(c.billing_period, 'n/a')                           as billing_period,
    coalesce(c.seats, 0)                                        as seats,
    coalesce(c.seats, 0) - coalesce(c.prior_seats, 0)           as seat_change,
    round(c.mrr, 2)                                             as mrr,
    round(c.prior_mrr, 2)                                       as prior_mrr,
    round(c.mrr - c.prior_mrr, 2)                               as net_change_mrr,
    c.movement_type,
    round(case when c.movement_type = 'New'           then c.mrr else 0 end, 2)            as new_mrr,
    round(case when c.movement_type = 'Reactivation'  then c.mrr else 0 end, 2)            as reactivation_mrr,
    round(case when c.movement_type = 'Expansion'     then c.mrr - c.prior_mrr else 0 end, 2) as expansion_mrr,
    round(case when c.movement_type = 'Contraction'   then c.prior_mrr - c.mrr else 0 end, 2) as contraction_mrr,
    round(case when c.movement_type = 'Churn'         then c.prior_mrr else 0 end, 2)      as churned_mrr,
    case when c.mrr > 0 then 1 else 0 end                       as is_active,
    churn.churn_type,
    churn.churn_reason
from classified c
join stg_customers cust on cust.customer_id = c.customer_id
left join (
    select customer_id, end_date as churn_month, churn_type, churn_reason
    from stg_subscriptions
    where end_reason = 'churn'
) churn on churn.customer_id = c.customer_id and churn.churn_month = c.month
where c.mrr > 0 or c.prior_mrr > 0;
