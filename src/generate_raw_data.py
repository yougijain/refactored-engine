"""Generate synthetic SaaS source data (customers, subscriptions, invoices, usage) into data/raw."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SEED = 20260101
FIRST_MONTH = date(2023, 1, 1)
LAST_MONTH = date(2026, 8, 1)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

PLANS = [
    {"plan_id": "PLN-STARTER", "plan_name": "Starter", "plan_tier": 1,
     "list_price_per_seat_month": 25, "min_seats": 2, "max_seats": 25},
    {"plan_id": "PLN-GROWTH", "plan_name": "Growth", "plan_tier": 2,
     "list_price_per_seat_month": 45, "min_seats": 10, "max_seats": 90},
    {"plan_id": "PLN-SCALE", "plan_name": "Scale", "plan_tier": 3,
     "list_price_per_seat_month": 75, "min_seats": 40, "max_seats": 350},
    {"plan_id": "PLN-ENTERPRISE", "plan_name": "Enterprise", "plan_tier": 4,
     "list_price_per_seat_month": 110, "min_seats": 150, "max_seats": 1500},
]
PLAN_BY_TIER = {p["plan_tier"]: p for p in PLANS}

SEGMENTS = [("SMB", 0.58), ("Mid-Market", 0.30), ("Enterprise", 0.12)]
SEGMENT_TIER_MIX = {
    "SMB": [(1, 0.62), (2, 0.38)],
    "Mid-Market": [(2, 0.55), (3, 0.45)],
    "Enterprise": [(3, 0.45), (4, 0.55)],
}
SEGMENT_MONTHLY_CHURN = {"SMB": 0.030, "Mid-Market": 0.016, "Enterprise": 0.0075}
SEGMENT_EXPANSION = {"SMB": 0.055, "Mid-Market": 0.080, "Enterprise": 0.095}

CHANNELS = {
    "SMB": [("Self-Serve", 0.45), ("Inbound", 0.30), ("Marketplace", 0.15), ("Partner", 0.10)],
    "Mid-Market": [("Inbound", 0.40), ("Outbound", 0.30), ("Partner", 0.20), ("Marketplace", 0.10)],
    "Enterprise": [("Outbound", 0.55), ("Partner", 0.25), ("Inbound", 0.20)],
}
INDUSTRIES = [
    ("Software & Technology", 0.22), ("Financial Services", 0.14), ("Healthcare", 0.12),
    ("Retail & E-commerce", 0.12), ("Manufacturing", 0.10), ("Professional Services", 0.10),
    ("Media & Entertainment", 0.07), ("Logistics & Transport", 0.07), ("Education", 0.06),
]
GEOS = [
    ("North America", "United States", 0.42), ("North America", "Canada", 0.07),
    ("EMEA", "United Kingdom", 0.10), ("EMEA", "Germany", 0.07), ("EMEA", "France", 0.05),
    ("EMEA", "Netherlands", 0.04), ("EMEA", "Sweden", 0.03),
    ("APAC", "Australia", 0.06), ("APAC", "Singapore", 0.04), ("APAC", "Japan", 0.04),
    ("APAC", "India", 0.03), ("LATAM", "Brazil", 0.03), ("LATAM", "Mexico", 0.02),
]
SALES_REPS = [
    "A. Okafor", "B. Lindqvist", "C. Moreau", "D. Ferreira", "E. Nakamura", "F. Whitfield",
    "G. Almeida", "H. Kowalski", "I. Castellanos", "J. Petersen", "K. Rahman", "L. Duarte",
]
VOLUNTARY_CHURN_REASONS = [
    ("Price / budget cuts", 0.26), ("Low adoption", 0.22), ("Missing functionality", 0.18),
    ("Switched to competitor", 0.16), ("Company acquired or closed", 0.10),
    ("Poor support experience", 0.08),
]
NAME_PARTS_A = [
    "Northwind", "Vertex", "Lumen", "Harbor", "Quartz", "Cobalt", "Summit", "Aster", "Ridge",
    "Beacon", "Orchid", "Falcon", "Granite", "Pioneer", "Zephyr", "Onyx", "Meridian", "Crestline",
    "Tidal", "Juniper", "Sable", "Halcyon", "Nimbus", "Bluefin", "Ironwood", "Corvus", "Lyra",
    "Maple", "Basalt", "Solstice",
]
NAME_PARTS_B = [
    "Peak", "River", "Field", "Point", "Gate", "Bridge", "Stone", "Arbor", "Vale", "Cove",
    "Forge", "Harbour", "Cross", "Watch", "Court",
]
NAME_PARTS_C = [
    "Analytics", "Logistics", "Health", "Financial", "Systems", "Labs", "Group", "Partners",
    "Industries", "Technologies", "Media", "Retail", "Energy", "Networks", "Solutions",
]
ACQUISITION_SEASONALITY = {
    1: 1.05, 2: 1.00, 3: 1.16, 4: 1.02, 5: 0.98, 6: 1.06,
    7: 0.84, 8: 0.80, 9: 1.12, 10: 1.08, 11: 1.06, 12: 1.20,
}
CHURN_SEASONALITY = {
    1: 1.25, 2: 1.05, 3: 1.00, 4: 0.95, 5: 0.95, 6: 1.00,
    7: 0.95, 8: 0.95, 9: 1.00, 10: 1.00, 11: 1.05, 12: 1.30,
}


def add_months(anchor: date, n: int) -> date:
    total = anchor.year * 12 + (anchor.month - 1) + n
    return date(total // 12, total % 12 + 1, 1)


def month_diff(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def all_months() -> list[date]:
    return [add_months(FIRST_MONTH, i) for i in range(month_diff(FIRST_MONTH, LAST_MONTH) + 1)]


def weighted_choice(rng: random.Random, options):
    """options is a sequence of (value, weight) or (a, b, weight) tuples."""
    total = sum(o[-1] for o in options)
    draw = rng.random() * total
    running = 0.0
    for option in options:
        running += option[-1]
        if draw <= running:
            return option[0] if len(option) == 2 else option[:-1]
    return options[-1][0] if len(options[-1]) == 2 else options[-1][:-1]


def bates(rng: random.Random, n: int = 4) -> float:
    """Bell-shaped value in [0, 1]; uses only random() so output is stable across Python versions."""
    return sum(rng.random() for _ in range(n)) / n


def normal(rng: random.Random, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Normal draw via Box-Muller."""
    u1 = max(rng.random(), 1e-12)
    u2 = rng.random()
    return mu + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def poisson(rng: random.Random, lam: float) -> int:
    limit = math.exp(-lam)
    k, product = 0, rng.random()
    while product > limit:
        k += 1
        product *= rng.random()
    return k


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class Customer:
    customer_id: str
    company_name: str
    segment: str
    industry: str
    region: str
    country: str
    acquisition_channel: str
    sales_rep: str
    signup_month: date
    quality: float
    trajectory: str
    billing_period: str
    plan_tier: int
    seats: int
    discount_pct: float


def seats_for(rng: random.Random, tier: int) -> int:
    plan = PLAN_BY_TIER[tier]
    low, high = plan["min_seats"], plan["max_seats"]
    draw = math.exp(rng.uniform(math.log(low), math.log(high * 0.55)))
    return int(clamp(round(draw), low, high))


def discount_for(rng: random.Random, segment: str, billing_period: str) -> float:
    base = {"SMB": 0.0, "Mid-Market": 0.04, "Enterprise": 0.09}[segment]
    if billing_period == "annual":
        base += 0.10
    return round(clamp(base + rng.uniform(-0.03, 0.08), 0.0, 0.32), 3)


def build_customers(rng: random.Random) -> list[Customer]:
    customers: list[Customer] = []
    used_names: set[str] = set()
    for index, month in enumerate(all_months()):
        expected = 16 * (1.032 ** index) * ACQUISITION_SEASONALITY[month.month]
        count = max(1, int(round(expected * rng.uniform(0.85, 1.15))))
        for _ in range(count):
            segment = weighted_choice(rng, SEGMENTS)
            region, country = weighted_choice(rng, GEOS)
            channel = weighted_choice(rng, CHANNELS[segment])
            tier = weighted_choice(rng, SEGMENT_TIER_MIX[segment])
            annual_odds = {"SMB": 0.18, "Mid-Market": 0.42, "Enterprise": 0.72}[segment]
            billing_period = "annual" if rng.random() < annual_odds else "monthly"

            while True:
                name = f"{rng.choice(NAME_PARTS_A)} {rng.choice(NAME_PARTS_B)} {rng.choice(NAME_PARTS_C)}"
                if name not in used_names:
                    used_names.add(name)
                    break

            customers.append(Customer(
                customer_id=f"CUS-{len(customers) + 1:05d}",
                company_name=name,
                segment=segment,
                industry=weighted_choice(rng, INDUSTRIES),
                region=region,
                country=country,
                acquisition_channel=channel,
                sales_rep="" if channel == "Self-Serve" else rng.choice(SALES_REPS),
                signup_month=month,
                quality=clamp(0.18 + 0.82 * bates(rng), 0.05, 0.98),
                trajectory=weighted_choice(rng, [("improving", 0.25), ("stable", 0.50), ("declining", 0.25)]),
                billing_period=billing_period,
                plan_tier=tier,
                seats=seats_for(rng, tier),
                discount_pct=discount_for(rng, segment, billing_period),
            ))
    return customers


def mrr_for(tier: int, seats: int, discount_pct: float) -> float:
    return round(PLAN_BY_TIER[tier]["list_price_per_seat_month"] * seats * (1 - discount_pct), 2)


def health_index(utilization: float, csat: float, adoption: float, tickets: int) -> float:
    ticket_drag = clamp(tickets / 12.0, 0.0, 1.0)
    return clamp(0.45 * utilization + 0.25 * (csat / 5.0) + 0.25 * (adoption / 100.0) - 0.15 * ticket_drag, 0.0, 1.0)


def simulate(rng: random.Random, customers: list[Customer]):
    """Simulate each customer month by month."""
    subscriptions: list[dict] = []
    usage: list[dict] = []
    invoices: list[dict] = []
    months = all_months()

    for customer in customers:
        tier = customer.plan_tier
        seats = customer.seats
        discount = customer.discount_pct
        utilization = clamp(0.42 + 0.42 * customer.quality + rng.uniform(-0.08, 0.08), 0.08, 0.99)
        drift = {"improving": 0.012, "stable": 0.000, "declining": -0.038}[customer.trajectory]

        active = True
        sub_index = 0
        sub_start = customer.signup_month
        billing_anchor = customer.signup_month
        churn_after: date | None = None
        involuntary = False
        reactivate_on: date | None = None

        start_index = months.index(customer.signup_month)
        for month in months[start_index:]:
            if not active:
                if reactivate_on is not None and month == reactivate_on:
                    active = True
                    sub_index += 1
                    sub_start = month
                    seats = max(PLAN_BY_TIER[tier]["min_seats"], int(round(seats * rng.uniform(0.6, 1.1))))
                    utilization = clamp(utilization + rng.uniform(0.10, 0.25), 0.15, 0.99)
                    drift = 0.004
                    billing_anchor = month
                    reactivate_on = None
                else:
                    continue

            tenure = month_diff(customer.signup_month, month)
            utilization = clamp(utilization + drift + normal(rng, 0, 0.035), 0.03, 1.0)
            active_users = max(1, min(seats, int(round(seats * utilization))))
            adoption = clamp(100 * (0.35 + 0.45 * customer.quality + 0.35 * (utilization - 0.5)) + normal(rng, 0, 6), 3, 100)
            tickets = poisson(rng, 0.8 + 2.4 * (1 - customer.quality) + 1.6 * max(0.0, 0.45 - utilization))
            csat = clamp(3.1 + 1.7 * customer.quality + 0.9 * (utilization - 0.5) - 0.06 * tickets + normal(rng, 0, 0.25), 1.0, 5.0)
            health = health_index(utilization, csat, adoption, tickets)

            usage.append({
                "customer_id": customer.customer_id,
                "month": month.isoformat(),
                "licensed_seats": seats,
                "active_users": active_users,
                "sessions": max(active_users, int(round(active_users * rng.uniform(6, 26) * (0.6 + utilization)))),
                "feature_adoption_score": round(adoption, 1),
                "support_tickets": tickets,
                "csat_score": round(csat, 2),
            })

            contract_month = month_diff(billing_anchor, month)
            due_invoice = customer.billing_period == "monthly" or contract_month % 12 == 0
            if due_invoice:
                periods = 12 if customer.billing_period == "annual" else 1
                amount = round(mrr_for(tier, seats, discount) * periods, 2)
                failed = rng.random() < (0.045 if customer.segment == "SMB" else 0.022)
                recovered = failed and rng.random() < 0.68
                status = "paid" if (not failed or recovered) else "failed"
                attempts = 1 if not failed else (rng.randint(2, 3) if recovered else 3)
                paid_date = ""
                if status == "paid":
                    lag = rng.randint(0, 3) if customer.billing_period == "monthly" else rng.randint(0, 21)
                    lag += 0 if not failed else rng.randint(4, 12)
                    paid_date = date.fromordinal(month.toordinal() + lag).isoformat()
                invoices.append({
                    "invoice_id": f"INV-{len(invoices) + 1:06d}",
                    "customer_id": customer.customer_id,
                    "subscription_id": f"SUB-{customer.customer_id[4:]}-{sub_index:02d}",
                    "invoice_date": month.isoformat(),
                    "period_start": month.isoformat(),
                    "period_end": add_months(month, periods).isoformat(),
                    "billing_period": customer.billing_period,
                    "amount": amount,
                    "status": status,
                    "paid_date": paid_date,
                    "payment_method": weighted_choice(rng, [("Credit card", 0.62), ("ACH / bank transfer", 0.24), ("Invoice / wire", 0.14)]),
                    "attempts": attempts,
                })
                if status == "failed":
                    churn_after, involuntary = month, True

            if month == LAST_MONTH:
                break

            if churn_after == month:
                pass  # already churning from a failed payment
            else:
                hazard = SEGMENT_MONTHLY_CHURN[customer.segment]
                hazard *= 1.9 * math.exp(-tenure / 9.0) + 0.65
                hazard *= math.exp(3.8 * (0.62 - health))
                if utilization < 0.20:
                    hazard *= 1.7
                hazard *= CHURN_SEASONALITY[add_months(month, 1).month]
                if customer.billing_period == "annual":
                    hazard *= 2.6 if (contract_month + 1) % 12 == 0 else 0.06
                if rng.random() < clamp(hazard, 0.0, 0.6):
                    churn_after, involuntary = month, False

            next_month = add_months(month, 1)
            if churn_after == month:
                reason = "Payment failure" if involuntary else weighted_choice(rng, VOLUNTARY_CHURN_REASONS)
                subscriptions.append({
                    "subscription_id": f"SUB-{customer.customer_id[4:]}-{sub_index:02d}",
                    "customer_id": customer.customer_id,
                    "plan_id": PLAN_BY_TIER[tier]["plan_id"],
                    "billing_period": customer.billing_period,
                    "seats": seats,
                    "discount_pct": discount,
                    "start_date": sub_start.isoformat(),
                    "end_date": next_month.isoformat(),
                    "end_reason": "churn",
                    "churn_type": "involuntary" if involuntary else "voluntary",
                    "churn_reason": reason,
                })
                active = False
                churn_after = None
                if not involuntary and rng.random() < 0.09:
                    candidate = add_months(next_month, rng.randint(2, 9))
                    reactivate_on = candidate if candidate <= LAST_MONTH else None
                involuntary = False
                continue

            expansion_odds = SEGMENT_EXPANSION[customer.segment] * (0.5 + health)
            if (contract_month + 1) % 12 == 0:
                expansion_odds *= 1.8
            contraction_odds = 0.030 * (1.7 - health)

            roll = rng.random()
            new_seats, new_tier = seats, tier
            if roll < expansion_odds:
                new_seats = max(seats + 1, int(round(seats * rng.uniform(1.06, 1.45))))
                if new_seats > PLAN_BY_TIER[tier]["max_seats"] and tier < 4:
                    new_tier = tier + 1
                    new_seats = max(new_seats, PLAN_BY_TIER[new_tier]["min_seats"])
            elif roll < expansion_odds + contraction_odds:
                new_seats = max(1, int(round(seats * rng.uniform(0.55, 0.92))))
                if new_seats < PLAN_BY_TIER[tier]["min_seats"] and tier > 1:
                    new_tier = tier - 1
                new_seats = max(new_seats, PLAN_BY_TIER[new_tier]["min_seats"])

            if (new_seats, new_tier) != (seats, tier):
                subscriptions.append({
                    "subscription_id": f"SUB-{customer.customer_id[4:]}-{sub_index:02d}",
                    "customer_id": customer.customer_id,
                    "plan_id": PLAN_BY_TIER[tier]["plan_id"],
                    "billing_period": customer.billing_period,
                    "seats": seats,
                    "discount_pct": discount,
                    "start_date": sub_start.isoformat(),
                    "end_date": next_month.isoformat(),
                    "end_reason": "plan_change",
                    "churn_type": "",
                    "churn_reason": "",
                })
                sub_index += 1
                sub_start = next_month
                seats, tier = new_seats, new_tier

        if active:
            subscriptions.append({
                "subscription_id": f"SUB-{customer.customer_id[4:]}-{sub_index:02d}",
                "customer_id": customer.customer_id,
                "plan_id": PLAN_BY_TIER[tier]["plan_id"],
                "billing_period": customer.billing_period,
                "seats": seats,
                "discount_pct": discount,
                "start_date": sub_start.isoformat(),
                "end_date": "",
                "end_reason": "",
                "churn_type": "",
                "churn_reason": "",
            })

    return subscriptions, usage, invoices


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {path.name:<28} {len(rows):>7,} rows")


def main() -> None:
    rng = random.Random(SEED)
    customers = build_customers(rng)
    subscriptions, usage, invoices = simulate(rng, customers)

    print(f"Writing raw extracts to {RAW_DIR}")
    write_csv(RAW_DIR / "plans.csv", PLANS,
              ["plan_id", "plan_name", "plan_tier", "list_price_per_seat_month", "min_seats", "max_seats"])
    write_csv(RAW_DIR / "customers.csv", [{
        "customer_id": c.customer_id,
        "company_name": c.company_name,
        "segment": c.segment,
        "industry": c.industry,
        "region": c.region,
        "country": c.country,
        "acquisition_channel": c.acquisition_channel,
        "sales_rep": c.sales_rep,
        "signup_date": c.signup_month.isoformat(),
    } for c in customers],
        ["customer_id", "company_name", "segment", "industry", "region", "country",
         "acquisition_channel", "sales_rep", "signup_date"])
    write_csv(RAW_DIR / "subscriptions.csv", sorted(subscriptions, key=lambda r: (r["customer_id"], r["start_date"])),
              ["subscription_id", "customer_id", "plan_id", "billing_period", "seats", "discount_pct",
               "start_date", "end_date", "end_reason", "churn_type", "churn_reason"])
    write_csv(RAW_DIR / "invoices.csv", invoices,
              ["invoice_id", "customer_id", "subscription_id", "invoice_date", "period_start", "period_end",
               "billing_period", "amount", "status", "paid_date", "payment_method", "attempts"])
    write_csv(RAW_DIR / "product_usage_monthly.csv", usage,
              ["customer_id", "month", "licensed_seats", "active_users", "sessions",
               "feature_adoption_score", "support_tickets", "csat_score"])


if __name__ == "__main__":
    main()
