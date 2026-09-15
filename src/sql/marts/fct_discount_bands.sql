-- Discount response at order month x category x discount band.
--
-- The question is not "does discounting sell more units" - it does - but whether the extra
-- units cover the margin given away. Holding category constant is what makes the comparison
-- fair: a mix shift towards cheap categories would otherwise look like elasticity.
create or replace table fct_discount_bands as
select
    f.order_month,
    f.category,
    f.discount_band,
    f.discount_band_rank,

    count(*)                                                    as order_lines,
    count(distinct f.order_id)                                  as orders,
    sum(f.quantity)                                             as units,
    round(avg(f.quantity), 3)                                   as units_per_line,

    round(sum(f.gross_revenue), 2)                              as gross_revenue,
    round(sum(f.discount_amount), 2)                            as discount_given,
    round(sum(f.net_revenue), 2)                                as net_revenue,
    round(sum(f.contribution_margin), 2)                        as contribution_margin,

    round(avg(f.discount_rate), 4)                              as avg_discount_rate,
    round(sum(f.net_revenue) / nullif(sum(f.quantity), 0), 2)   as net_revenue_per_unit,
    round(sum(f.contribution_margin) / nullif(sum(f.quantity), 0), 2) as margin_per_unit,
    round(sum(f.contribution_margin) / nullif(sum(f.net_revenue), 0), 4) as contribution_margin_rate,

    sum(case when f.is_returned then 1 else 0 end)              as returned_lines,
    round(sum(case when f.is_returned then 1.0 else 0 end) / count(*), 4) as return_line_rate
from fct_order_items f
group by f.order_month, f.category, f.discount_band, f.discount_band_rank;
