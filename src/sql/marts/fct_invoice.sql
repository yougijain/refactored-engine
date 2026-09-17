-- Invoices with payment status.
create or replace table fct_invoice as
select
    i.invoice_id,
    i.customer_id,
    c.company_name,
    c.segment,
    c.region,
    i.subscription_id,
    s.plan_name,
    i.invoice_date,
    i.invoice_month,
    i.period_start,
    i.period_end,
    i.billing_period,
    i.amount,
    i.status,
    i.paid_date,
    i.payment_method,
    i.attempts,
    case when i.status = 'paid' then i.amount else 0 end   as collected_amount,
    case when i.status = 'failed' then i.amount else 0 end as at_risk_amount,
    case when i.paid_date is null then null
         else date_diff('day', i.invoice_date, i.paid_date) end as days_to_pay,
    case when i.status = 'failed' then 1 else 0 end as is_failed,
    case when i.attempts > 1 and i.status = 'paid' then 1 else 0 end as is_dunning_recovered
from stg_invoices i
join stg_customers c on c.customer_id = i.customer_id
left join stg_subscriptions s on s.subscription_id = i.subscription_id;
