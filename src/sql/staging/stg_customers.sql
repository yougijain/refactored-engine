-- Customers.
create or replace view stg_customers as
select
    customer_id,
    company_name,
    segment,
    industry,
    region,
    country,
    acquisition_channel,
    nullif(sales_rep, '')       as sales_rep,
    cast(signup_date as date)   as signup_date,
    date_trunc('month', cast(signup_date as date))::date as signup_month
from raw_customers;
