-- Customer master from the CRM extract. One row per customer.
create or replace view stg_customers as
select
    customer_id,
    cast(signup_date as date)                             as signup_date,
    date_trunc('month', cast(signup_date as date))::date  as signup_month,
    acquisition_channel,
    country,
    region,
    city,
    cast(marketing_opt_in as integer) = 1                 as is_marketing_opt_in
from raw_customers;
