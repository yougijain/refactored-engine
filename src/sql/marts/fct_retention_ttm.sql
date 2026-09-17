-- Trailing 12-month net and gross revenue retention by segment.
create or replace table fct_retention_ttm as
with base as (
    select month, customer_id, segment, mrr
    from fct_mrr_monthly
    where mrr > 0
),
paired as (
    select
        date_add(b.month, to_months(12))::date as month,
        b.segment,
        b.mrr                                  as base_mrr,
        coalesce(l.mrr, 0)                     as current_mrr
    from base b
    left join fct_mrr_monthly l
      on l.customer_id = b.customer_id
     and l.month = date_add(b.month, to_months(12))::date
    where date_add(b.month, to_months(12))::date <= (select max(month) from fct_mrr_monthly)
)
select
    month,
    segment,
    round(sum(base_mrr), 2)                     as base_mrr,
    round(sum(current_mrr), 2)                  as retained_mrr,
    round(sum(least(current_mrr, base_mrr)), 2) as retained_mrr_capped,
    count(*)                                    as base_customers,
    count(*) filter (where current_mrr > 0)     as retained_customers
from paired
group by 1, 2;
