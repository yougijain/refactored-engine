# Data dictionary

Two layers are documented: the **raw extracts** in `data/raw`, which stand in for source
systems, and the **published marts** in `data/marts`, which are the interface Tableau reads.
Staging and intermediate models are implementation detail and are documented in the SQL.

Formulas for every derived measure are in [metric_definitions.md](metric_definitions.md).

---

## Raw extracts

### `customers.csv` — 9,000 rows, one per customer

| Column | Type | Notes |
| --- | --- | --- |
| `customer_id` | string | Primary key |
| `signup_date` | date | Registration, not first order |
| `acquisition_channel` | string | Organic Search, Paid Search, Paid Social, Affiliate, Email & CRM, Marketplace |
| `country`, `region`, `city` | string | Region determines which fulfilment centre serves the order |
| `marketing_opt_in` | 0/1 | Consent flag |

### `products.csv` — 190 rows, one per product

| Column | Type | Notes |
| --- | --- | --- |
| `product_id` | string | Primary key |
| `sku`, `product_name`, `brand` | string | |
| `category`, `subcategory` | string | Six categories with materially different economics |
| `unit_cost`, `list_price` | decimal | Landed cost, and list price before any discount |
| `weight_kg` | decimal | Drives carrier cost |

### `orders.csv` — 15,103 rows, one per order

| Column | Type | Notes |
| --- | --- | --- |
| `order_id` | string | Primary key |
| `customer_id` | string | References `customers` |
| `order_date` | date | |
| `order_channel` | string | Web, Mobile App, Store, Marketplace |
| `order_sequence` | integer | 1 for the customer's first order |
| `is_shipped` | 0/1 | 0 for store collection; delivery columns are then empty |
| `fulfilment_centre` | string | FC-North, FC-Central, FC-South, or Store Pickup |
| `carrier` | string | Swiftline, Metro Post, Regional Freight; empty for collection |
| `promised_delivery_date` | date | Shown to the customer at checkout — the SLA baseline |
| `shipped_date`, `delivered_date` | date | |
| `shipping_fee_charged` | decimal | What the customer paid; zero above the free-shipping threshold |
| `shipping_cost` | decimal | What the carrier charged the business |
| `payment_method`, `promo_code`, `order_status` | string | |

### `order_items.csv` — 30,832 rows, one per order line

| Column | Type | Notes |
| --- | --- | --- |
| `order_item_id` | string | Primary key |
| `order_id`, `product_id` | string | References `orders`, `products` |
| `quantity` | integer | |
| `unit_price` | decimal | List price at time of sale |
| `discount_amount` | decimal | Total discount on the line, not per unit |

### `returns.csv` — 4,776 rows, one per return

| Column | Type | Notes |
| --- | --- | --- |
| `return_id` | string | Primary key |
| `order_item_id` | string | References `order_items`; a line is returned at most once |
| `return_date` | date | |
| `quantity_returned` | integer | Never exceeds the quantity ordered on the line |
| `return_reason` | string | Changed mind, Wrong size, Not as described, Damaged in transit, Faulty, Arrived too late |
| `restocked` | 0/1 | 0 for damaged and faulty — cost of goods is not recovered |
| `refund_amount` | decimal | |

### `marketing_spend.csv` — 11,466 rows, one per channel-campaign-day

| Column | Type | Notes |
| --- | --- | --- |
| `spend_date` | date | |
| `channel` | string | Matches `customers.acquisition_channel` |
| `campaign` | string | |
| `spend`, `impressions`, `clicks` | numeric | |

---

## Published marts

### `dim_customer` — 9,000 rows, grain: customer

Acquisition context, the first-order experience that the retention analysis splits on, and
realised lifetime economics. Customers who never ordered are present with zero measures and a
null cohort, so acquisition analysis can still count what was paid for them.

Key columns: `customer_id` · `signup_month` · `acquisition_channel` · `cohort_month` ·
`first_order_experience` · `first_order_on_time` · `first_order_returned` · `orders` ·
`lifetime_net_revenue` · `lifetime_contribution_margin` · `avg_order_value` ·
`return_line_rate` · `is_repeat_customer` · `tenure_months` · `is_active`

### `dim_product` — 190 rows, grain: product

Carries `list_margin_rate` — what the buying sheet promised — beside
`contribution_margin_rate`, what the product delivered. `margin_rate_vs_list` is the gap
between them; negative means the product underperformed its own buying assumption.

### `fct_order_items` — 30,832 rows, grain: order line

The revenue fact, at source-system grain, with the full margin walk and enough dimensional
context to stand alone in Tableau without a join. `discount_band` and `discount_band_rank`
are cut here so the elasticity mart and the margin sheets cannot use different boundaries.

### `fct_returns` — 4,776 rows, grain: return

Returns with order and product context. `margin_lost` is the margin the return destroyed —
the refund, plus the cost of goods when the unit could not be restocked. `disposition` splits
`Recovered` from `Written off`.

### `fct_fulfilment_daily` — 6,151 rows, grain: order date × fulfilment centre × carrier

Delivery performance, daily so Tableau can roll up to week or month. Excludes store-collected
orders, which have no promise date. `late_net_revenue` is the revenue riding on parcels that
missed the promise.

### `fct_discount_bands` — 900 rows, grain: order month × category × discount band

Discount response, held within category so that a mix shift towards cheaper categories cannot
masquerade as price elasticity.

### `fct_cohort_repeat` — 1,859 rows, grain: cohort month × first-order experience × period

A dense cohort grid: a month with no orders is a zero, not a missing row. `cohort_customers`
is fixed for the life of the cohort, and `active_rate` is the repeat rate at that period.

### `fct_channel_payback` — 2,784 rows, grain: channel × signup month × period

Acquisition payback. `cumulative_margin_net_of_cac` below zero means the cohort has not yet
repaid what it cost. Cohorts are cut on signup month, not first-order month, and include
customers who never ordered.
