-- One row per reporting month.
create or replace view int_month_spine as
select distinct month as month_start
from stg_product_usage
order by 1;
