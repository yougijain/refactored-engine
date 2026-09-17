# Dashboard guide

`tableau/retail_margin_intelligence.twb` contains 10 worksheets across 4 dashboards. The
workbook connects to `data/marts/*.csv` by relative path, so a fresh clone opens without any
configuration. It uses the Tableau 2026.1 document format and needs Tableau Desktop or Tableau
Public 2026.1 or later.

Each dashboard answers questions from [business_questions.md](business_questions.md).

---

## 1 · Margin Reality — *where the margin actually is*

Answers **Q1**.

| Sheet | Mark | Reads as |
| --- | --- | --- |
| **Category Contribution** | Bar | Contribution margin by category. The `Margin Basis` parameter switches it to net revenue — the point of the dashboard is that the two orderings disagree |
| **Promised vs Realised Margin** | Scatter | Each product plotted as list margin (x) against realised contribution margin rate (y), sized by revenue. Points below the diagonal lost margin between the buying sheet and the P&L |
| **Margin Trend by Category** | Area | Contribution margin over time, stacked by category |

**How to read it.** Use the *Margin Basis* control at the top right of the dashboard. Switch it
to *Net Revenue* and note the category ordering.
Switch back to *Contribution Margin*. Any category that moves a long way between the two
views is one where revenue reporting has been misleading the business.

## 2 · Pricing & Discounting — *what discount depth buys*

Answers **Q2**.

| Sheet | Mark | Reads as |
| --- | --- | --- |
| **Discount Elasticity** | Bar | Margin per unit at each discount band, nested inside category |
| **Units per Line by Depth** | Line | Units per line across discount bands, one line per category. The slope *is* the elasticity |

**How to read it.** A category earns its discount only if the line in the right-hand chart
rises steeply enough to offset the bars falling in the left-hand chart. A flat line beside
collapsing bars means the discount bought nothing.

## 3 · Fulfilment & Its Cost — *late parcels and what they cost*

Answers **Q3** and **Q4**.

| Sheet | Mark | Reads as |
| --- | --- | --- |
| **On-Time Rate by Lane** | Heatmap | On-time rate for every fulfilment centre and carrier pairing |
| **Revenue on Late Parcels** | Bar | Net revenue riding on parcels that missed the promise, by month and carrier |
| **First-Order Experience** | Line | Repeat rate over the 12 months after a customer's first order, split four ways by how that first order went |

**How to read it.** The heatmap finds the weak lane; the bar chart sizes it in revenue; the
line chart converts it into retention. The vertical gap between the `Clean` and
`Delivered late` lines is the commercial price of a missed promise date, and it is what
justifies spending money on the lane the heatmap identified.

## 4 · Acquisition & Returns — *what each channel costs, and what comes back*

Answers **Q5** and **Q6**.

| Sheet | Mark | Reads as |
| --- | --- | --- |
| **CAC Payback by Channel** | Line | Cumulative contribution margin net of acquisition cost, per customer, by months since signup. The zero line is breakeven |
| **Return Reasons by Margin Lost** | Bar | Return reasons ranked by margin destroyed, coloured by whether the unit was recovered or written off |

**How to read it.** In the payback chart, a channel is only healthy once its line crosses
zero, and how quickly it crosses matters as much as how high it ends. In the returns chart,
note that ranking by margin gives a different top reason than ranking by count would — the
expensive returns are the ones where the stock is written off, not the frequent ones.

---

## Calculated fields

All calculations live in the workbook, defined per datasource, and are listed in
`tools/generate_workbook.py` in the `CALCS` table. They are aggregate-level by design: rates
are always `SUM(numerator) / SUM(denominator)` so that they re-aggregate correctly when a
filter or a dimension changes. Row-level averages of rates are not used anywhere.

## Parameter

**Margin Basis** — `Contribution Margin` or `Net Revenue`. Drives the *Category
Contribution* sheet. Its control is shown at the top right of dashboard 1 and beside the
sheet itself; a test fails if any parameter has no control on a dashboard.

## Rebuilding the workbook

`python tools/generate_workbook.py` regenerates the .twb from the live mart schemas. It
**overwrites** the file, so once the workbook has been styled in Tableau Desktop, the .twb
becomes the source of truth and the generator should only be used deliberately, after a
schema change.

`tests/test_workbook_integrity.py` checks the workbook without needing Tableau installed:
every connection resolves to a mart that exists, every column ordinal matches the CSV header,
every calculated field references a field that exists, every pill on a shelf was declared,
every dashboard zone points at a real sheet, no zones overlap, and every parameter has a
control.

`tests/test_workbook_schema.py` validates the file against Tableau's published schema for the
2026.1 format, vendored in `tableau/schema/` — see the README there for provenance, and for
how to move to a newer format. CI regenerates the workbook on every push and fails if the
result differs from what is committed.
