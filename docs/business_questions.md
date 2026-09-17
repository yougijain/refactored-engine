# Business questions

The scope of this project, agreed before any modelling. Every mart exists to answer a
question on this page; anything that answers nothing gets deleted.

The business is a mid-size omnichannel retailer: it sells through its own web and mobile
store, through physical stores, and through a third-party marketplace. It ships from three
fulfilment centres using three carriers.

The finance and operations teams share a complaint that motivates the whole project:
**revenue reporting says the business is growing, and the P&L disagrees.** The gap is in
costs that never appear next to revenue in the source systems — discounts, returns,
shipping subsidy, and acquisition spend.

---

## Q1 — Which categories actually make money once returns and shipping are charged to them?

Gross revenue flatters categories with high return rates and heavy items. We need a single
contribution margin per category that nets off discount, COGS, return credits, and the
shipping cost the customer did not pay for.

**Answered by** `fct_order_items` → *Margin Bridge* and *Category Contribution* sheets.
**Decision it drives** Which categories to reprice, renegotiate, or drop.

## Q2 — Is discounting buying incremental volume, or just giving away margin?

Every category gets promoted. Some respond with volume that more than pays for the
discount; some sell the same units at a lower price. We compare units, AOV and contribution
margin rate across discount depth bands, within category.

**Answered by** `fct_discount_bands` → *Discount Elasticity* sheet.
**Decision it drives** Where to cap promotional depth next quarter.

## Q3 — Which fulfilment centre and carrier combinations miss the promised delivery date?

The promise date is shown to the customer at checkout. Missing it is an operational failure
with a measurable commercial cost (Q4). We need on-time rate and average days late by
centre, carrier and week, with volume so that small, noisy lanes are visible as small.

**Answered by** `fct_fulfilment_daily` → *On-Time Delivery* sheet.
**Decision it drives** Carrier mix per fulfilment centre.

## Q4 — What does a bad first order cost in repeat purchase?

The operational question only matters if it changes behaviour. We split each acquisition
cohort by whether the customer's **first** order was delivered late or returned, then track
repeat-purchase rate over the following months. A gap between those curves is the commercial
price of a late delivery.

**Answered by** `fct_cohort_repeat` → *First-Order Experience* sheet.
**Decision it drives** How much it is worth spending to fix late delivery.

## Q5 — Which acquisition channels are profitable after CAC, and when do they pay back?

Channels are currently judged on first-order revenue, which favours channels that buy cheap,
one-off, heavily discounted orders. We charge each cohort its real acquisition spend and
track cumulative contribution margin until it crosses zero.

**Answered by** `fct_channel_payback` → *CAC Payback* sheet.
**Decision it drives** Budget reallocation across channels.

## Q6 — Which products drive returns, and for which reason?

Return rate is a product quality signal and a margin leak. Reasons separate the fixable
(wrong size, damaged in transit) from the structural (changed mind).

**Answered by** `fct_returns` → *Return Reason Pareto* sheet.
**Decision it drives** Which SKUs need better sizing data, packaging, or delisting.

---

## Out of scope

- Inventory, stock-outs and replenishment. No stock data in the source extracts.
- Store-level labour cost. Contribution margin here stops before fixed operating cost.
- Customer lifetime value projections. Payback is measured on realised margin only, not
  forecast, so that every number on a dashboard is auditable.

## Grain and definitions

Settled up front to keep the marts consistent:

- **Revenue** is net of discount and excludes shipping fees charged to the customer.
- **Contribution margin** is revenue − COGS − return credits − net shipping cost. It is
  the lowest line that can be attributed to a single order item without allocation
  assumptions, so it is the deepest line this project reports.
- A **return** is attributed to the period of the original order, not the return date, so
  margin and returns line up in the same row.
- A customer belongs to the **cohort** of their first completed order month, and to the
  acquisition channel recorded at signup.
