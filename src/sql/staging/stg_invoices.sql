-- Invoices.
create or replace view stg_invoices as
select
    invoice_id,
    customer_id,
    subscription_id,
    cast(invoice_date as date)            as invoice_date,
    date_trunc('month', cast(invoice_date as date))::date as invoice_month,
    cast(period_start as date)            as period_start,
    cast(period_end as date)              as period_end,
    billing_period,
    cast(amount as decimal(12, 2))        as amount,
    status,
    try_cast(nullif(paid_date, '') as date) as paid_date,
    payment_method,
    cast(attempts as integer)             as attempts
from raw_invoices;
