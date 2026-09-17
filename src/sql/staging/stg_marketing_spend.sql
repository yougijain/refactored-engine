-- Daily paid-media spend by channel and campaign, from the ad-platform exports.
create or replace view stg_marketing_spend as
select
    cast(spend_date as date)                              as spend_date,
    date_trunc('month', cast(spend_date as date))::date   as spend_month,
    channel                                               as acquisition_channel,
    campaign,
    cast(spend as decimal(12, 2))                         as spend,
    cast(impressions as bigint)                           as impressions,
    cast(clicks as bigint)                                as clicks
from raw_marketing_spend;
