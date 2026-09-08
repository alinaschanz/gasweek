"""percentiles and hour-of-day / day-of-week bins. pure functions, no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .fees import BlockFee

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def percentile(values: list[float], p: float) -> float:
    """linear interpolation between order statistics; p in 0..100."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def median(values: list[float]) -> float:
    return percentile(values, 50)


def local_time(timestamp: int, tz_hours: float = 0.0) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=tz_hours)))


def by_hour(rows: list[BlockFee], tz_hours: float = 0.0) -> dict[int, list[float]]:
    bins: dict[int, list[float]] = {h: [] for h in range(24)}
    for r in rows:
        bins[local_time(r.timestamp, tz_hours).hour].append(r.base_fee_gwei)
    return bins


def by_weekday(rows: list[BlockFee], tz_hours: float = 0.0) -> dict[int, list[float]]:
    bins: dict[int, list[float]] = {d: [] for d in range(7)}
    for r in rows:
        bins[local_time(r.timestamp, tz_hours).weekday()].append(r.base_fee_gwei)
    return bins


def bucket(rows: list[BlockFee], seconds: int) -> list[tuple[int, list[float]]]:
    """(bucket_start_timestamp, base fees) for fixed-width time buckets, oldest first."""
    if not rows:
        return []
    start = rows[0].timestamp - rows[0].timestamp % seconds
    out: dict[int, list[float]] = {}
    for r in rows:
        key = start + ((r.timestamp - start) // seconds) * seconds
        out.setdefault(key, []).append(r.base_fee_gwei)
    return sorted(out.items())


def summarize(rows: list[BlockFee], tz_hours: float = 0.0) -> dict:
    fees = [r.base_fee_gwei for r in rows]
    hours = {h: median(v) for h, v in by_hour(rows, tz_hours).items() if v}
    days = {d: median(v) for d, v in by_weekday(rows, tz_hours).items() if v}
    blobs = [r.blob_fee_gwei for r in rows if r.blob_fee_gwei is not None]
    cheapest = min(hours, key=hours.get) if hours else None
    priciest = max(hours, key=hours.get) if hours else None
    return {
        "blocks": len(rows),
        "first_block": rows[0].number,
        "last_block": rows[-1].number,
        "from_ts": rows[0].timestamp,
        "to_ts": rows[-1].timestamp,
        "min": min(fees),
        "p25": percentile(fees, 25),
        "median": median(fees),
        "p75": percentile(fees, 75),
        "p90": percentile(fees, 90),
        "max": max(fees),
        "gas_used_ratio_mean": sum(r.gas_used_ratio for r in rows) / len(rows),
        "blob_median": median(blobs) if blobs else None,
        "hours": hours,
        "weekdays": days,
        "cheapest_hour": cheapest,
        "priciest_hour": priciest,
    }


def gwei(v: float | None) -> str:
    if v is None:
        return "n/a"
    if v >= 100:
        return f"{v:,.0f}"
    if v >= 10:
        return f"{v:.1f}"
    if v >= 1:
        return f"{v:.2f}"
    return f"{v:.3f}"


def bar(value: float, top: float, width: int = 24) -> str:
    n = 0 if top <= 0 else round(width * value / top)
    return "#" * max(n, 1 if value > 0 else 0)
