-- Retention by signup cohort and months since signup.
create or replace table fct_cohort_retention as
with cohort_base as (
    select
        customer_id,
        cohort_month,
        segment,
        region,
        acquisition_channel,
        mrr as initial_mrr
    from fct_mrr_monthly
    where month = cohort_month
      and mrr > 0
),
cohort_size as (
    select
        cohort_month,
        segment,
        count(*)            as cohort_customers,
        sum(initial_mrr)    as cohort_initial_mrr
    from cohort_base
    group by 1, 2
),
activity as (
    select
        b.cohort_month,
        b.segment,
        date_diff('month', b.cohort_month, f.month) as period_index,
        count(distinct f.customer_id) filter (where f.mrr > 0) as active_customers,
        sum(f.mrr)                                             as retained_mrr
    from cohort_base b
    join fct_mrr_monthly f
      on f.customer_id = b.customer_id
     and f.month >= b.cohort_month
    group by 1, 2, 3
)
select
    a.cohort_month,
    date_trunc('quarter', a.cohort_month)::date as cohort_quarter,
    a.segment,
    a.period_index,
    date_add(a.cohort_month, to_months(cast(a.period_index as integer)))::date as activity_month,
    s.cohort_customers,
    round(s.cohort_initial_mrr, 2)  as cohort_initial_mrr,
    a.active_customers,
    round(coalesce(a.retained_mrr, 0), 2) as retained_mrr
from activity a
join cohort_size s
  on s.cohort_month = a.cohort_month and s.segment = a.segment
order by 1, 2, 3;
