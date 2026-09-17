-- Monthly MRR movement and customer counts by segment.
create or replace table fct_retention_monthly as
select
    month,
    segment,
    round(sum(prior_mrr), 2)          as starting_mrr,
    round(sum(mrr), 2)                as ending_mrr,
    round(sum(new_mrr), 2)            as new_mrr,
    round(sum(expansion_mrr), 2)      as expansion_mrr,
    round(sum(reactivation_mrr), 2)   as reactivation_mrr,
    round(sum(contraction_mrr), 2)    as contraction_mrr,
    round(sum(churned_mrr), 2)        as churned_mrr,
    round(sum(case when prior_mrr > 0 then prior_mrr else 0 end), 2) as retention_base_mrr,
    round(sum(case when prior_mrr > 0 then mrr else 0 end), 2)       as retention_base_ending_mrr,
    count(distinct customer_id) filter (where mrr > 0)                          as active_customers,
    count(distinct customer_id) filter (where prior_mrr > 0)                    as starting_customers,
    count(distinct customer_id) filter (where movement_type = 'New')            as new_customers,
    count(distinct customer_id) filter (where movement_type = 'Churn')          as churned_customers,
    count(distinct customer_id) filter (where movement_type = 'Reactivation')   as reactivated_customers,
    count(distinct customer_id) filter (where movement_type = 'Expansion')      as expanded_customers,
    count(distinct customer_id) filter (where movement_type = 'Contraction')    as contracted_customers
from fct_mrr_monthly
group by 1, 2;
