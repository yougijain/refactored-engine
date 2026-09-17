-- Every month from a customer's first billed month on, so churn shows up as zero MRR.
create or replace view int_customer_month_grid as
with first_month as (
    select customer_id, min(month) as first_billed_month
    from int_customer_month
    group by 1
)
select
    f.customer_id,
    m.month_start as month,
    f.first_billed_month
from first_month f
join int_month_spine m on m.month_start >= f.first_billed_month;
