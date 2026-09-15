"""Generate the six raw source extracts this project models.

Stdlib only and fully seeded: `python src/generate_raw_data.py` produces byte-identical
CSVs on any machine, which is what lets CI prove the committed extracts match the code.

The generator is deliberately not uniform noise. It encodes the behaviours the analysis is
supposed to find, so that the marts have something real to detect:

  * contribution margin differs by category once returns and shipping are charged to it -
    electronics is high revenue and thin margin, home goods are heavy, apparel is returned;
  * discount response differs by category - apparel and footwear move units on depth,
    electronics does not;
  * on-time delivery depends on the fulfilment centre and carrier pairing, and degrades
    in the November-December peak;
  * a late or returned *first* order suppresses a customer's repeat rate;
  * acquisition channels differ in both what they cost and the quality of what they buy.

Nothing downstream is told about any of this. The marts have to surface it from the rows.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

SEED = 20260915
START = date(2024, 1, 1)
END = date(2026, 6, 30)

# --------------------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------------------

# category -> (gross margin on list, return rate, discount elasticity, weight band kg,
#              share of demand)
CATEGORIES = {
    "Apparel":            dict(margin=0.58, return_rate=0.21, elasticity=1.9, weight=(0.2, 1.2), share=0.28),
    "Footwear":           dict(margin=0.52, return_rate=0.26, elasticity=1.6, weight=(0.8, 2.0), share=0.14),
    "Electronics":        dict(margin=0.17, return_rate=0.07, elasticity=0.4, weight=(0.4, 6.5), share=0.16),
    "Home & Kitchen":     dict(margin=0.39, return_rate=0.09, elasticity=0.8, weight=(1.5, 12.0), share=0.18),
    "Beauty":             dict(margin=0.63, return_rate=0.04, elasticity=0.7, weight=(0.1, 0.5), share=0.13),
    "Sports & Outdoors":  dict(margin=0.44, return_rate=0.12, elasticity=1.1, weight=(1.0, 9.0), share=0.11),
}

SUBCATEGORIES = {
    "Apparel": ["Tops", "Outerwear", "Denim", "Knitwear", "Dresses"],
    "Footwear": ["Trainers", "Boots", "Sandals", "Formal"],
    "Electronics": ["Audio", "Wearables", "Small Appliances", "Accessories"],
    "Home & Kitchen": ["Cookware", "Bedding", "Storage", "Tableware", "Lighting"],
    "Beauty": ["Skincare", "Haircare", "Fragrance", "Cosmetics"],
    "Sports & Outdoors": ["Camping", "Fitness", "Cycling", "Swim"],
}

BRANDS = ["Northvale", "Corda", "Ellery & Co", "Puresel", "Mokkan", "Latitude 54", "Brightpath"]

# channel -> (share of signups, target CAC, repeat propensity, discount appetite)
ACQUISITION_CHANNELS = {
    "Organic Search":  dict(share=0.20, cac=4.0,   repeat=0.62, discount=0.85),
    "Paid Search":     dict(share=0.22, cac=34.0,  repeat=0.52, discount=1.00),
    "Paid Social":     dict(share=0.19, cac=27.0,  repeat=0.33, discount=1.45),
    "Affiliate":       dict(share=0.13, cac=41.0,  repeat=0.38, discount=1.35),
    "Email & CRM":     dict(share=0.11, cac=6.0,   repeat=0.68, discount=1.10),
    "Marketplace":     dict(share=0.15, cac=23.0,  repeat=0.29, discount=0.95),
}

ORDER_CHANNELS = ["Web", "Mobile App", "Store", "Marketplace"]

REGIONS = {
    "North":   dict(cities=["Manchester", "Leeds", "Newcastle", "Sheffield"], centre="FC-North"),
    "Central": dict(cities=["Birmingham", "Nottingham", "Coventry", "Leicester"], centre="FC-Central"),
    "South":   dict(cities=["London", "Bristol", "Brighton", "Reading", "Southampton"], centre="FC-South"),
}

CARRIERS = ["Swiftline", "Metro Post", "Regional Freight"]

# (fulfilment centre, carrier) -> probability the parcel lands on or before the promise date.
# FC-South leans on Regional Freight and is the weak lane the operations dashboard should find.
ON_TIME = {
    ("FC-North", "Swiftline"): 0.96,
    ("FC-North", "Metro Post"): 0.93,
    ("FC-North", "Regional Freight"): 0.88,
    ("FC-Central", "Swiftline"): 0.94,
    ("FC-Central", "Metro Post"): 0.90,
    ("FC-Central", "Regional Freight"): 0.83,
    ("FC-South", "Swiftline"): 0.91,
    ("FC-South", "Metro Post"): 0.84,
    ("FC-South", "Regional Freight"): 0.71,
}

CARRIER_MIX = {
    "FC-North":   [("Swiftline", 0.55), ("Metro Post", 0.30), ("Regional Freight", 0.15)],
    "FC-Central": [("Swiftline", 0.40), ("Metro Post", 0.35), ("Regional Freight", 0.25)],
    "FC-South":   [("Swiftline", 0.25), ("Metro Post", 0.30), ("Regional Freight", 0.45)],
}

# per-kg and fixed cost the business pays the carrier
CARRIER_RATE = {
    "Swiftline": (3.60, 0.85),
    "Metro Post": (2.80, 0.70),
    "Regional Freight": (2.10, 0.55),
}

FREE_SHIPPING_THRESHOLD = 45.0
SHIPPING_FEE = 4.99

RETURN_REASONS = [
    ("Changed mind", 0.30, True),
    ("Wrong size", 0.26, True),
    ("Not as described", 0.16, True),
    ("Damaged in transit", 0.13, False),
    ("Faulty", 0.09, False),
    ("Arrived too late", 0.06, True),
]

PAYMENT_METHODS = [("Card", 0.62), ("Digital Wallet", 0.24), ("Buy Now Pay Later", 0.10), ("Gift Card", 0.04)]

PROMO_CODES = ["", "", "", "WELCOME10", "SAVE15", "FLASH25", "SEASON20", "CLEAR40"]


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    """Weighted choice over (value, weight) pairs."""
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted], k=1)[0]


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def seasonality(d: date) -> float:
    """Retail demand curve: a November-December peak and a January trough."""
    month_factor = {1: 0.78, 2: 0.84, 3: 0.95, 4: 0.98, 5: 1.02, 6: 1.00,
                    7: 0.96, 8: 0.99, 9: 1.06, 10: 1.12, 11: 1.42, 12: 1.38}[d.month]
    return month_factor


def growth(d: date) -> float:
    """Steady underlying growth so cohorts get bigger over time."""
    months = (d.year - START.year) * 12 + (d.month - START.month)
    return 1.0 + 0.021 * months


def money(x: float) -> str:
    return f"{x:.2f}"


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    path = RAW / name
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {name:<28} {len(rows):>7,} rows")


# --------------------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------------------

def build_products(rng: random.Random) -> list[dict]:
    products = []
    pid = 0
    for category, spec in CATEGORIES.items():
        # SKU count roughly tracks demand share, floored so every category is shoppable.
        n = max(12, round(spec["share"] * 190))
        for _ in range(n):
            pid += 1
            sub = rng.choice(SUBCATEGORIES[category])
            brand = rng.choice(BRANDS)
            lo, hi = spec["weight"]
            weight = round(rng.uniform(lo, hi), 2)

            if category == "Electronics":
                list_price = round(rng.uniform(39, 480), 2)
            elif category == "Home & Kitchen":
                list_price = round(rng.uniform(18, 210), 2)
            elif category == "Footwear":
                list_price = round(rng.uniform(35, 165), 2)
            elif category == "Beauty":
                list_price = round(rng.uniform(9, 78), 2)
            elif category == "Sports & Outdoors":
                list_price = round(rng.uniform(22, 290), 2)
            else:
                list_price = round(rng.uniform(14, 135), 2)

            # Realised margin wobbles around the category norm.
            margin = min(0.82, max(0.05, rng.gauss(spec["margin"], 0.05)))
            unit_cost = round(list_price * (1 - margin), 2)

            products.append(dict(
                product_id=f"P{pid:05d}",
                sku=f"{category[:3].upper()}-{sub[:3].upper()}-{pid:05d}",
                product_name=f"{brand} {sub[:-1] if sub.endswith('s') else sub} {rng.randint(100, 999)}",
                category=category,
                subcategory=sub,
                brand=brand,
                unit_cost=unit_cost,
                list_price=list_price,
                weight_kg=weight,
            ))
    return products


def build_customers(rng: random.Random) -> list[dict]:
    customers = []
    channel_names = list(ACQUISITION_CHANNELS)
    total_days = (END - START).days

    # Signups are spread by the growth * seasonality curve rather than uniformly.
    day_weights = []
    for offset in range(total_days - 30):  # leave a tail so late signups can still order
        d = START + timedelta(days=offset)
        day_weights.append(growth(d) * seasonality(d))

    n_customers = 9000
    offsets = rng.choices(range(len(day_weights)), weights=day_weights, k=n_customers)
    offsets.sort()

    for i, offset in enumerate(offsets, start=1):
        signup = START + timedelta(days=offset)
        # Paid Social ramps over the period at the expense of Affiliate - a real budget shift.
        months_in = (signup.year - START.year) * 12 + (signup.month - START.month)
        shares = []
        for name in channel_names:
            share = ACQUISITION_CHANNELS[name]["share"]
            if name == "Paid Social":
                share *= 1 + 0.030 * months_in
            if name == "Affiliate":
                share *= max(0.35, 1 - 0.028 * months_in)
            shares.append((name, share))
        channel = pick(rng, shares)

        region = pick(rng, [("North", 0.28), ("Central", 0.30), ("South", 0.42)])
        customers.append(dict(
            customer_id=f"C{i:06d}",
            signup_date=signup,
            acquisition_channel=channel,
            country="United Kingdom",
            region=region,
            city=rng.choice(REGIONS[region]["cities"]),
            marketing_opt_in=1 if rng.random() < 0.63 else 0,
            # not published - drives generation only
            _favourite=pick(rng, [(c, s["share"]) for c, s in CATEGORIES.items()]),
            _repeat=ACQUISITION_CHANNELS[channel]["repeat"] * rng.uniform(0.6, 1.4),
            _discount=ACQUISITION_CHANNELS[channel]["discount"],
        ))
    return customers


def build_orders(rng: random.Random, customers: list[dict], products: list[dict]):
    by_category: dict[str, list[dict]] = {}
    for p in products:
        by_category.setdefault(p["category"], []).append(p)
    category_weights = [(c, s["share"]) for c, s in CATEGORIES.items()]

    orders: list[dict] = []
    items: list[dict] = []
    returns: list[dict] = []
    order_seq = 0
    item_seq = 0
    return_seq = 0

    for customer in customers:
        centre = REGIONS[customer["region"]]["centre"]
        order_date = customer["signup_date"] + timedelta(days=rng.randint(0, 4))
        repeat_p = customer["_repeat"]
        sequence = 0

        while order_date <= END:
            sequence += 1
            order_seq += 1
            order_id = f"O{order_seq:07d}"

            # ---- channel ------------------------------------------------------------
            if customer["acquisition_channel"] == "Marketplace":
                channel = pick(rng, [("Marketplace", 0.78), ("Web", 0.13), ("Mobile App", 0.09)])
            else:
                channel = pick(rng, [("Web", 0.44), ("Mobile App", 0.34), ("Store", 0.13), ("Marketplace", 0.09)])
            is_shipped = 0 if channel == "Store" else 1

            # ---- basket -------------------------------------------------------------
            n_lines = rng.choices([1, 2, 3, 4, 5], weights=[42, 28, 17, 9, 4], k=1)[0]
            order_lines = []
            for _ in range(n_lines):
                # Customers skew to a favourite category but do not live in it.
                category = customer["_favourite"] if rng.random() < 0.45 else pick(rng, category_weights)
                product = rng.choice(by_category[category])
                spec = CATEGORIES[category]

                # Discount depth: promo appetite by channel, deeper in the peak and in sale months.
                appetite = customer["_discount"] * (1.25 if order_date.month in (1, 6, 11, 12) else 1.0)
                if rng.random() < min(0.72, 0.30 * appetite):
                    depth = min(0.55, abs(rng.gauss(0.18, 0.11)) * appetite)
                else:
                    depth = 0.0
                depth = round(depth, 4)

                # Elastic categories buy more units as depth increases; inelastic ones do not.
                lift = 1 + spec["elasticity"] * depth
                quantity = 1
                if rng.random() < min(0.55, 0.16 * lift):
                    quantity = rng.choices([2, 3, 4], weights=[68, 24, 8], k=1)[0]

                gross = round(product["list_price"] * quantity, 2)
                discount = round(gross * depth, 2)
                order_lines.append((product, quantity, gross, discount))

            net_revenue = sum(g - d for _, _, g, d in order_lines)

            # ---- fulfilment ---------------------------------------------------------
            if is_shipped:
                fulfilment_centre = centre
                carrier = pick(rng, CARRIER_MIX[centre])
                promise_days = rng.choices([2, 3, 4, 5], weights=[14, 38, 30, 18], k=1)[0]
                promised = order_date + timedelta(days=promise_days)

                on_time_p = ON_TIME[(fulfilment_centre, carrier)]
                if order_date.month in (11, 12):      # peak degrades every lane
                    on_time_p -= 0.09
                if net_revenue > 250:                  # high-value parcels get handled better
                    on_time_p += 0.03
                on_time_p = min(0.99, max(0.40, on_time_p))

                dispatch_lag = rng.choices([0, 1, 2], weights=[62, 30, 8], k=1)[0]
                shipped = order_date + timedelta(days=dispatch_lag)
                if rng.random() < on_time_p:
                    delivered = promised - timedelta(days=rng.choices([0, 1, 2], weights=[52, 33, 15], k=1)[0])
                    delivered = max(delivered, shipped + timedelta(days=1))
                else:
                    delivered = promised + timedelta(days=rng.choices([1, 2, 3, 4, 6, 9],
                                                                     weights=[34, 26, 16, 11, 8, 5], k=1)[0])
                was_late = delivered > promised

                weight = sum(p["weight_kg"] * q for p, q, _, _ in order_lines)
                fixed, per_kg = CARRIER_RATE[carrier]
                shipping_cost = round(fixed + per_kg * weight, 2)
                shipping_fee = 0.0 if net_revenue >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
            else:
                fulfilment_centre = "Store Pickup"
                carrier = ""
                promised = shipped = delivered = None
                was_late = False
                shipping_cost = 0.0
                shipping_fee = 0.0

            orders.append(dict(
                order_id=order_id,
                customer_id=customer["customer_id"],
                order_date=order_date,
                order_channel=channel,
                order_sequence=sequence,
                is_shipped=is_shipped,
                fulfilment_centre=fulfilment_centre,
                carrier=carrier,
                promised_delivery_date=promised,
                shipped_date=shipped,
                delivered_date=delivered,
                shipping_fee_charged=shipping_fee,
                shipping_cost=shipping_cost,
                payment_method=pick(rng, PAYMENT_METHODS),
                promo_code=rng.choice(PROMO_CODES),
                order_status="Delivered" if is_shipped else "Collected",
            ))

            # ---- lines and returns ---------------------------------------------------
            had_return = False
            for product, quantity, gross, discount in order_lines:
                item_seq += 1
                item_id = f"OI{item_seq:07d}"
                items.append(dict(
                    order_item_id=item_id,
                    order_id=order_id,
                    product_id=product["product_id"],
                    quantity=quantity,
                    unit_price=product["list_price"],
                    discount_amount=discount,
                ))

                spec = CATEGORIES[product["category"]]
                return_p = spec["return_rate"]
                if was_late:
                    return_p *= 1.55            # late parcels get sent back more often
                if gross and discount / gross > 0.30:
                    return_p *= 1.18            # deep-discount buying is less considered
                if rng.random() < return_p:
                    had_return = True
                    return_seq += 1
                    if was_late and rng.random() < 0.30:
                        reason, restock = "Arrived too late", True
                    else:
                        reason = pick(rng, [(r, w) for r, w, _ in RETURN_REASONS])
                        restock = {r: s for r, _, s in RETURN_REASONS}[reason]
                    qty_returned = quantity if quantity == 1 or rng.random() < 0.72 else 1
                    line_net = gross - discount
                    refund = round(line_net * qty_returned / quantity, 2)
                    base = delivered or order_date
                    returns.append(dict(
                        return_id=f"R{return_seq:06d}",
                        order_item_id=item_id,
                        return_date=base + timedelta(days=rng.randint(2, 28)),
                        quantity_returned=qty_returned,
                        return_reason=reason,
                        restocked=1 if restock else 0,
                        refund_amount=refund,
                    ))

            # ---- will they come back? -------------------------------------------------
            p = repeat_p
            if sequence == 1:
                # The signal Q4 exists to measure.
                if was_late:
                    p *= 0.62
                if had_return:
                    p *= 0.82
                repeat_p = p
            p *= 0.93 ** (sequence - 1)   # natural decay with order count

            if rng.random() >= p:
                break
            gap = int(rng.lognormvariate(math.log(58), 0.62))
            order_date = order_date + timedelta(days=max(6, min(gap, 420)))

    return orders, items, returns


def build_marketing_spend(rng: random.Random, customers: list[dict]) -> list[dict]:
    """Spend is generated per channel-month around the channel's target CAC.

    Acquisition cost is therefore a property of the source data, not something the marts
    assume - `fct_channel_payback` still has to divide spend by cohort size to recover it.
    """
    signups: dict[tuple[date, str], int] = {}
    for c in customers:
        signups[(month_start(c["signup_date"]), c["acquisition_channel"])] = \
            signups.get((month_start(c["signup_date"]), c["acquisition_channel"]), 0) + 1

    campaigns = {
        "Paid Search": ["Brand", "Generic", "Shopping"],
        "Paid Social": ["Prospecting", "Retargeting", "Creator"],
        "Affiliate": ["Cashback", "Content", "Voucher"],
        "Email & CRM": ["Lifecycle", "Winback"],
        "Marketplace": ["Sponsored Listings"],
        "Organic Search": ["SEO Content"],
    }
    cpc = {"Paid Search": 0.95, "Paid Social": 0.42, "Affiliate": 0.68,
           "Email & CRM": 0.12, "Marketplace": 0.55, "Organic Search": 0.05}

    rows = []
    month = month_start(START)
    while month <= END:
        for channel, spec in ACQUISITION_CHANNELS.items():
            new_customers = signups.get((month, channel), 0)
            if new_customers == 0:
                continue
            # Paid Social efficiency decays as the budget scales into it.
            drift = 1.0
            if channel == "Paid Social":
                months_in = (month.year - START.year) * 12 + (month.month - START.month)
                drift = 1 + 0.016 * months_in
            monthly_spend = new_customers * spec["cac"] * drift * rng.uniform(0.92, 1.09)

            names = campaigns[channel]
            splits = [rng.uniform(0.6, 1.4) for _ in names]
            total = sum(splits)
            days_in_month = (add_months(month, 1) - month).days

            for name, split in zip(names, splits):
                campaign_spend = monthly_spend * split / total
                # Spread across the month with a mild weekend dip.
                weights = []
                for day in range(days_in_month):
                    d = month + timedelta(days=day)
                    weights.append(0.72 if d.weekday() >= 5 else 1.0)
                wsum = sum(weights)
                for day in range(days_in_month):
                    d = month + timedelta(days=day)
                    if d > END:
                        continue
                    spend = campaign_spend * weights[day] / wsum
                    if spend < 0.01:
                        continue
                    clicks = max(1, int(spend / cpc[channel] * rng.uniform(0.9, 1.1)))
                    rows.append(dict(
                        spend_date=d,
                        channel=channel,
                        campaign=f"{channel.split()[0]} - {name}",
                        spend=round(spend, 2),
                        impressions=int(clicks * rng.uniform(28, 74)),
                        clicks=clicks,
                    ))
        month = add_months(month, 1)
    return rows


# --------------------------------------------------------------------------------------

def main() -> None:
    rng = random.Random(SEED)
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"Generating raw extracts for {START} .. {END} (seed {SEED})")

    products = build_products(rng)
    customers = build_customers(rng)
    orders, items, returns = build_orders(rng, customers, products)
    spend = build_marketing_spend(rng, customers)

    write_csv("products.csv",
              ["product_id", "sku", "product_name", "category", "subcategory", "brand",
               "unit_cost", "list_price", "weight_kg"],
              [[p["product_id"], p["sku"], p["product_name"], p["category"], p["subcategory"],
                p["brand"], money(p["unit_cost"]), money(p["list_price"]), f"{p['weight_kg']:.2f}"]
               for p in products])

    write_csv("customers.csv",
              ["customer_id", "signup_date", "acquisition_channel", "country", "region",
               "city", "marketing_opt_in"],
              [[c["customer_id"], c["signup_date"].isoformat(), c["acquisition_channel"],
                c["country"], c["region"], c["city"], c["marketing_opt_in"]]
               for c in customers])

    write_csv("orders.csv",
              ["order_id", "customer_id", "order_date", "order_channel", "order_sequence",
               "is_shipped", "fulfilment_centre", "carrier", "promised_delivery_date",
               "shipped_date", "delivered_date", "shipping_fee_charged", "shipping_cost",
               "payment_method", "promo_code", "order_status"],
              [[o["order_id"], o["customer_id"], o["order_date"].isoformat(), o["order_channel"],
                o["order_sequence"], o["is_shipped"], o["fulfilment_centre"], o["carrier"],
                o["promised_delivery_date"].isoformat() if o["promised_delivery_date"] else "",
                o["shipped_date"].isoformat() if o["shipped_date"] else "",
                o["delivered_date"].isoformat() if o["delivered_date"] else "",
                money(o["shipping_fee_charged"]), money(o["shipping_cost"]),
                o["payment_method"], o["promo_code"], o["order_status"]]
               for o in orders])

    write_csv("order_items.csv",
              ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_amount"],
              [[i["order_item_id"], i["order_id"], i["product_id"], i["quantity"],
                money(i["unit_price"]), money(i["discount_amount"])] for i in items])

    write_csv("returns.csv",
              ["return_id", "order_item_id", "return_date", "quantity_returned",
               "return_reason", "restocked", "refund_amount"],
              [[r["return_id"], r["order_item_id"], r["return_date"].isoformat(),
                r["quantity_returned"], r["return_reason"], r["restocked"],
                money(r["refund_amount"])] for r in returns])

    write_csv("marketing_spend.csv",
              ["spend_date", "channel", "campaign", "spend", "impressions", "clicks"],
              [[s["spend_date"].isoformat(), s["channel"], s["campaign"], money(s["spend"]),
                s["impressions"], s["clicks"]] for s in spend])


if __name__ == "__main__":
    main()
