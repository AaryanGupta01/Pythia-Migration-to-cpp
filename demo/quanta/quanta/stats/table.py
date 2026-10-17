"""Synthetic tabular data and column summaries (the CSV round trip of the `stats` command)."""
from __future__ import annotations

from typing import Dict, List

from quanta.io.csvio import Table
from quanta.util.rng import Lcg

REGIONS = ["north", "south", "east", "west", "centre"]


def make_sales_table(rng: Lcg, rows: int) -> Table:
    """Orders with a region, quantity, unit price and noisy revenue."""
    data: List[List[object]] = []
    for order in range(rows):
        region = rng.choice(REGIONS)
        quantity = 1 + rng.next_int(40)
        price = round(5.0 + 45.0 * rng.next_float(), 2)
        revenue = quantity * price * (1.0 + 0.05 * rng.gauss())
        data.append([order, region, quantity, price, revenue])
    return Table(["order", "region", "quantity", "price", "revenue"], data)


def revenue_by_region(table: Table) -> Dict[str, float]:
    """Total revenue per region, in region-name order."""
    totals: Dict[str, float] = {}
    regions = table.column("region")
    revenue = table.float_column("revenue")
    for region, value in zip(regions, revenue):
        totals[str(region)] = totals.get(str(region), 0.0) + value
    return {k: totals[k] for k in sorted(totals)}


def normalise_column(values: List[float]) -> List[float]:
    """Z-scores of a column (population standard deviation)."""
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5 or 1.0
    return [(v - mean) / sd for v in values]
