# Analysis notes

Findings from the marts, in the order of [business_questions.md](business_questions.md).
Every figure below is reproducible: rebuild with `python src/build_marts.py` and query
`data/warehouse.duckdb`.

**Period** January 2024 – June 2026 · **9,000 customers** · **15,103 orders** ·
**£4.26M net revenue** · **£967k contribution margin** · **22.7% margin rate**

---

## Q1 — Electronics is a third of revenue and almost none of the margin

| Category | Net revenue | Share of revenue | Contribution margin | Margin rate |
| --- | ---: | ---: | ---: | ---: |
| Electronics | £1,522k | 35.7% | £68k | **4.5%** |
| Home & Kitchen | £649k | 15.2% | £156k | 24.1% |
| Sports & Outdoors | £692k | 16.2% | £202k | 29.1% |
| Footwear | £466k | 10.9% | £149k | 31.9% |
| Apparel | £699k | 16.4% | £267k | 38.2% |
| Beauty | £232k | 5.5% | £125k | **53.9%** |

Electronics generates **more than a third of revenue and 7% of contribution margin**. Beauty
does the opposite: 5.5% of revenue and nearly twice Electronics' margin in absolute terms.

Any report that ranks categories by revenue puts Electronics first and Beauty last. Ranked by
contribution margin, that ordering almost exactly inverts. This is the gap between revenue
reporting and the P&L that motivated the project.

Electronics is thin for structural reasons — 17% list margin against Beauty's 63% — but two
things make it worse than the buying sheet suggests: it is heavy, so freight eats a larger
share, and it is discounted as if it had apparel-like margin to give away. Which leads to Q2.

## Q2 — Discounting Electronics past 10% destroys more margin than it creates

Margin per unit by discount depth, within category:

| Discount band | Apparel margin/unit | Electronics margin/unit |
| --- | ---: | ---: |
| 0% | £29.84 | £32.21 |
| 1–10% | £27.96 | £19.72 |
| 10–20% | £21.83 | **−£5.06** |
| 20–30% | £16.67 | **−£29.33** |
| 30%+ | £7.68 | **−£67.14** |

Units per line barely move in Electronics: 1.23 at full price, 1.29 at 30%+. Apparel moves
from 1.22 to 1.35 — a real, if modest, response.

**1,789 Electronics units sold at 10% discount or deeper produced −£62k of contribution
margin.** Electronics made £68k in total. Almost the entire category margin was given back at
the till by discounting a category that does not respond to discount.

Apparel is the opposite case: margin per unit falls with depth, but units rise enough that
depth is a defensible trade at moderate levels. The recommendation is not "stop discounting" —
it is to cap Electronics depth at 10% and leave Apparel alone.

## Q3 — One lane accounts for two-fifths of all revenue on late parcels

Overall on-time rate is **85.6%**. It is not evenly distributed:

| Lane | Orders | On-time | Revenue on late parcels |
| --- | ---: | ---: | ---: |
| FC-South / Regional Freight | 2,469 | **69.4%** | £206k |
| FC-South / Metro Post | 1,680 | 82.9% | £79k |
| FC-Central / Regional Freight | 1,037 | 83.3% | £47k |
| FC-North / Swiftline | 2,018 | **94.7%** | £25k |

£509k of net revenue rode on parcels that missed their promise date, and **£206k of it —
41% — came from a single lane**: FC-South shipping via Regional Freight. That lane is also
the highest-volume Regional Freight lane, because FC-South routes 45% of its parcels to the
cheapest carrier.

Regional Freight is the cheapest carrier per kilogram, which is presumably why FC-South leans
on it. Q4 is what makes that trade look like a mistake.

## Q4 — A late first order costs 17 points of repeat rate

Repeat rate for customers acquired on or before June 2025, split by how their first order
went:

| First-order experience | Customers | Ever ordered again |
| --- | ---: | ---: |
| Clean | 3,230 | **44.7%** |
| Returned | 1,155 | 40.0% |
| Late and returned | 223 | 28.7% |
| Delivered late | 402 | **27.9%** |

A late first delivery is associated with a **16.8 percentage point drop in repeat rate** — a
37% relative fall. A return, on its own, costs less than five points. Late delivery is by far
the more damaging first experience, and the effect persists: by month six the clean cohort is
still active at 5.8% against 1.4% for the late cohort.

This is an association, not a controlled experiment — nothing here rules out the possibility
that some third factor drives both. But the size and consistency of the gap are enough to
justify treating the promise date as a retention metric rather than an operations metric.

**The trade FC-South is making.** The lane carries £157k of contribution margin and delivers
late 30% of the time. Moving its Regional Freight volume to Metro Post would cost more per
parcel and recover roughly 14 points of on-time rate on 2,469 orders — worth doing if the
retention effect above is even partly causal.

## Q5 — Affiliate and Paid Social buy customers that barely pay back

Twelve months after signup, by channel:

| Channel | CAC | Margin per customer | Payback multiple |
| --- | ---: | ---: | ---: |
| Organic Search | £4.03 | £154.02 | 38.3× |
| Email & CRM | £6.04 | £152.14 | 25.2× |
| Marketplace | £23.36 | £103.41 | 4.4× |
| Paid Search | £34.07 | £129.17 | 3.8× |
| Paid Social | £31.05 | £66.34 | **2.1×** |
| Affiliate | £42.38 | £77.52 | **1.8×** |

The paid channels separate on quality, not just price. Paid Search costs slightly more than
Paid Social per customer but returns nearly double the margin, because Paid Social customers
discount harder and repeat less. Affiliate is the worst of both: the highest CAC and the
second-lowest margin per customer.

Paid Social is also getting worse: its share of signups has grown steadily while its
efficiency has drifted down, which is the usual signature of scaling a channel past its
efficient frontier.

## Q6 — The most expensive returns are not the most frequent ones

£287k of contribution margin was destroyed by returns.

| Reason | Margin lost | Returns | Lost per return |
| --- | ---: | ---: | ---: |
| Damaged in transit | **£72.0k** | 563 | £128 |
| Changed mind | £56.8k | 1,317 | £43 |
| Wrong size | £55.3k | 1,198 | £46 |
| Faulty | £49.0k | 411 | **£119** |
| Not as described | £31.1k | 743 | £42 |
| Arrived too late | £22.9k | 544 | £42 |

Ranked by count, *Changed mind* looks like the problem at 1,317 returns. Ranked by margin,
the top reason is *Damaged in transit* from less than half as many returns — because damaged
and faulty units cannot be restocked, so the cost of goods is written off along with the
refund. Those two reasons are 20% of returns and **42% of the margin lost**.

That also makes them the most fixable: packaging and handling are within the company's
control in a way that a customer changing their mind is not.

---

## What I would do next

1. **Cap Electronics discount depth at 10%** and re-measure in a quarter. This is the single
   largest recoverable number in the analysis — roughly £62k of annualised margin.
2. **Move FC-South volume off Regional Freight**, and track on-time rate against the repeat
   rate of the cohorts acquired afterwards, so the retention claim in Q4 gets tested rather
   than assumed.
3. **Re-baseline channel budgets on payback multiple**, not first-order revenue. Affiliate at
   1.8× is a candidate for renegotiation or exit.
4. **Audit packaging on the SKUs behind damaged-in-transit returns.** 20% of returns, 42% of
   the margin lost, and no customer-behaviour component to argue about.

## Caveats

- The dataset is synthetic. The structure and the relationships are realistic and the
  pipeline is production-shaped, but the numbers describe a business that does not exist.
- Returns are attributed to the order month, so the most recent two months are slightly
  optimistic — their returns have not all landed yet.
- Contribution margin stops before fixed operating cost. A category with a positive
  contribution margin is not necessarily profitable after overhead.
- Cohorts from late 2025 onward have short observation windows; the payback table is
  restricted to cohorts with at least 12 months of history.
