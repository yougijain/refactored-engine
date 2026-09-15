-- Every month the business traded in. Cohort grids need a dense calendar so that a month
-- with no activity shows as a zero rather than disappearing from the view.
create or replace view int_month_spine as
select cast(range as date) as month
from range(
    (select min(order_month) from stg_orders),
    (select max(order_month) from stg_orders) + interval 1 month,
    interval 1 month
);
