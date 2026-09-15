-- Acquisition payback by channel x signup cohort x months since signup.
--
-- Cohorts here are cut on SIGNUP month, not first-order month, because that is what the
-- media spend actually bought. Customers who never order stay in the denominator - dropping
-- them would flatter every paid channel by hiding what it paid for silence.
--
-- Payback is measured on realised contribution margin only. Nothing is forecast, so a
-- cohort that has not yet paid back simply has not paid back yet.
create or replace table fct_channel_payback as
with cohort as (
    select acquisition_channel, signup_month, count(*) as cohort_customers
    from dim_customer
    group by acquisition_channel, signup_month
),
spend as (
    select acquisition_channel, spend_month, round(sum(spend), 2) as acquisition_spend
    from stg_marketing_spend
    group by acquisition_channel, spend_month
),
activity as (
    select
        c.acquisition_channel,
        c.signup_month,
        f.order_month,
        count(distinct f.customer_id)   as active_customers,
        sum(f.net_revenue)              as net_revenue,
        sum(f.contribution_margin)      as contribution_margin
    from fct_order_items f
    join dim_customer c on c.customer_id = f.customer_id
    group by c.acquisition_channel, c.signup_month, f.order_month
),
grid as (
    select
        co.acquisition_channel,
        co.signup_month,
        co.cohort_customers,
        coalesce(sp.acquisition_spend, 0)                       as acquisition_spend,
        s.month                                                 as activity_month,
        date_diff('month', co.signup_month, s.month)            as period_index
    from cohort co
    left join spend sp on sp.acquisition_channel = co.acquisition_channel
                      and sp.spend_month = co.signup_month
    join int_month_spine s on s.month >= co.signup_month
)
select
    g.acquisition_channel,
    g.signup_month,
    g.activity_month,
    g.period_index,
    g.cohort_customers,
    g.acquisition_spend,
    round(g.acquisition_spend / g.cohort_customers, 2)          as cac,

    coalesce(a.active_customers, 0)                             as active_customers,
    round(coalesce(a.net_revenue, 0), 2)                        as net_revenue,
    round(coalesce(a.contribution_margin, 0), 2)                as contribution_margin,

    round(sum(coalesce(a.contribution_margin, 0)) over (
        partition by g.acquisition_channel, g.signup_month
        order by g.period_index
        rows between unbounded preceding and current row), 2)   as cumulative_contribution_margin,

    -- Below zero means the cohort has not yet repaid what it cost to acquire.
    round(sum(coalesce(a.contribution_margin, 0)) over (
        partition by g.acquisition_channel, g.signup_month
        order by g.period_index
        rows between unbounded preceding and current row) - g.acquisition_spend, 2)
                                                                as cumulative_margin_net_of_cac,

    round(sum(coalesce(a.contribution_margin, 0)) over (
        partition by g.acquisition_channel, g.signup_month
        order by g.period_index
        rows between unbounded preceding and current row) / nullif(g.acquisition_spend, 0), 4)
                                                                as payback_ratio
from grid g
left join activity a
       on a.acquisition_channel = g.acquisition_channel
      and a.signup_month = g.signup_month
      and a.order_month = g.activity_month;
