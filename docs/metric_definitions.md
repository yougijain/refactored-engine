# Metric definitions

One definition per metric, in one place. If a number on a dashboard disagrees with this
page, the dashboard is wrong.

## The margin walk

Every money metric in this project is a step on the same walk, computed at order-line grain
in `int_order_item_economics` and published in `fct_order_items`.

| Step | Column | Definition |
| --- | --- | --- |
| Gross revenue | `gross_revenue` | `unit_price × quantity`, at list price |
| less discount | `discount_amount` | Promotional and markdown discount on the line |
| **Net revenue** | `net_revenue` | `gross_revenue − discount_amount`. Excludes shipping fees charged to the customer |
| less refunds | `refund_amount` | Value refunded when the line was returned |
| **Realised revenue** | `realised_revenue` | `net_revenue − refund_amount` |
| less cost of goods | `cogs` | `unit_cost × quantity`, **less** `unit_cost × quantity_returned` when the return was restocked |
| less net freight | `net_shipping_cost` | Carrier cost less the shipping fee the customer paid, allocated to the line |
| **Contribution margin** | `contribution_margin` | `realised_revenue − cogs − net_shipping_cost` |

Contribution margin is the deepest line this project reports. It stops before fixed
operating cost, marketing, and overhead, because those cannot be attributed to an order line
without assumptions that would make the number unauditable.

### Rates

- **Contribution margin rate** = `SUM(contribution_margin) / SUM(net_revenue)`. Always
  aggregate then divide; averaging per-row rates weights a small line the same as a large one.
- **Discount rate** = `discount_amount / gross_revenue`, per line.
- **List margin rate** = `(list_price − unit_cost) / list_price`. The margin the buying sheet
  promised, before anything happened to it.

## Allocation and attribution rules

**Freight is allocated by revenue share.** Shipping is charged per order but margin is
reported per line, so each line carries `order_shipping × (line_net_revenue /
order_net_revenue)`. A basket discounted to zero net revenue falls back to an even split.
The allocation is tested to reconcile to the order header across all 30k lines.

**Returns are attributed to the order month, not the return month.** A February order
returned in March erodes February's margin. This keeps margin and the returns that caused it
on the same row, at the cost of making the most recent months slightly optimistic until
their returns land.

**Cost of goods is only recovered on restocked returns.** Damaged and faulty units cannot be
resold, so the cost of goods is gone as well as the revenue. `disposition` in `fct_returns`
splits `Recovered` from `Written off`.

**Store-collected orders are excluded from delivery metrics.** They carry no promise date, so
counting them would inflate on-time rate with orders that could never be late. They are
included in every revenue and margin metric.

## Delivery

- **On-time** — `delivered_date <= promised_delivery_date`. The promise date is the one shown
  to the customer at checkout, not an internal target.
- **On-time rate** = `SUM(on_time_orders) / SUM(orders)`, over shipped, delivered orders.
- **Days late** — `MAX(delivered_date − promised_delivery_date, 0)`. Early deliveries count as
  zero, not as negative days that would cancel out a late one.
- **Badly late** — three or more days past the promise date.
- **Revenue on late parcels** — net revenue of orders that missed the promise date. It sizes
  the exposure; it is not a loss figure.

## Customers and cohorts

- **Cohort month** — the month of a customer's first order, used for repeat analysis.
- **Signup month** — the month a customer registered, used for acquisition payback, because
  that is what the media spend bought. Customers who never order stay in the denominator.
- **First-order experience** — a four-way label fixed at the first order and never revised:
  `Clean`, `Returned`, `Delivered late`, `Late and returned`.
- **Repeat rate** at period *n* = `SUM(active_customers) / SUM(cohort_customers)` where
  `period_index = n`. The denominator is fixed at cohort size and never moves.
- **Active** — ordered within 180 days of the last date in the data.

## Acquisition

- **CAC** = `acquisition_spend / cohort_customers` for a channel and signup month.
- **Cumulative margin net of CAC** = running contribution margin for the cohort, minus what it
  cost to acquire. Below zero means the cohort has not repaid its acquisition cost.
- **Payback multiple** = `cumulative_contribution_margin / acquisition_spend`. A multiple of
  1.0 is breakeven.

Payback is measured on realised margin only. Nothing is forecast or extrapolated, so a young
cohort has simply not paid back yet rather than being projected to.
