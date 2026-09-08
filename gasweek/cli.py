"""command line entry point: python -m gasweek [--hours 168] [--tz +2] [--svg fees.svg]"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

from . import __version__
from .fees import BLOCKS_PER_HOUR, fetch
from .rpc import Rpc, RpcError, RpcUnavailable
from .stats import WEEKDAYS, bar, by_hour, gwei, percentile, summarize
from .svg import render

SUMMARY_FIELDS = (
    "date_utc", "blocks", "first_block", "last_block", "min_gwei", "p25_gwei", "median_gwei", "p75_gwei", "p90_gwei",
    "max_gwei", "cheapest_hour_utc", "priciest_hour_utc", "gas_used_ratio_mean", "blob_median_gwei",
)


def parse_tz(text: str) -> float:
    text = text.strip().lower()
    if text in ("utc", "z", "0"):
        return 0.0
    if ":" in text:
        sign = -1 if text.startswith("-") else 1
        hh, mm = text.lstrip("+-").split(":")
        return sign * (int(hh) + int(mm) / 60)
    return float(text)


def report(summary: dict, tz_hours: float, hours_bins: dict[int, list[float]]) -> str:
    tz = "utc" if not tz_hours else f"utc{tz_hours:+g}"
    frm = datetime.fromtimestamp(summary["from_ts"], tz=timezone.utc)
    to = datetime.fromtimestamp(summary["to_ts"], tz=timezone.utc)
    lines = [
        f"ethereum base fee, {summary['blocks']:,} blocks ({summary['first_block']:,} to {summary['last_block']:,}), "
        f"{frm:%Y-%m-%d %H:%M} to {to:%Y-%m-%d %H:%M} utc",
        f"overall  min {gwei(summary['min'])}  p25 {gwei(summary['p25'])}  median {gwei(summary['median'])}  "
        f"p75 {gwei(summary['p75'])}  p90 {gwei(summary['p90'])}  max {gwei(summary['max'])} gwei"
        + (f"  |  blob median {gwei(summary['blob_median'])} gwei" if summary["blob_median"] is not None else ""),
        f"blocks were {summary['gas_used_ratio_mean'] * 100:.0f}% full on average",
        "",
        f"hour ({tz})  median     p25     p75",
    ]
    hours = summary["hours"]
    top = max(hours.values()) if hours else 1
    for h in range(24):
        v = hours_bins.get(h) or []
        if not v:
            continue
        lines.append(f"{h:02d}:00      {gwei(hours[h]):>7} {gwei(percentile(v, 25)):>7} {gwei(percentile(v, 75)):>7}  {bar(hours[h], top)}")
    if summary["cheapest_hour"] is not None:
        c, p = summary["cheapest_hour"], summary["priciest_hour"]
        ratio = hours[p] / hours[c] if hours[c] else float("inf")
        lines += [
            "",
            f"cheapest hour  {c:02d}:00-{(c + 1) % 24:02d}:00 {tz}  median {gwei(hours[c])} gwei",
            f"priciest hour  {p:02d}:00-{(p + 1) % 24:02d}:00 {tz}  median {gwei(hours[p])} gwei  ({ratio:.1f}x)",
        ]
    days = summary["weekdays"]
    if len(days) > 1:
        lines += ["", "weekday  median"]
        for d in range(7):
            if d in days:
                lines.append(f"{WEEKDAYS[d]}      {gwei(days[d]):>7}  {bar(days[d], max(days.values()))}")
    return "\n".join(lines)


def append_summary(path: str, summary: dict) -> None:
    row = {
        "date_utc": datetime.fromtimestamp(summary["to_ts"], tz=timezone.utc).strftime("%Y-%m-%d"),
        "blocks": summary["blocks"], "first_block": summary["first_block"], "last_block": summary["last_block"],
        "min_gwei": f"{summary['min']:.6g}", "p25_gwei": f"{summary['p25']:.6g}", "median_gwei": f"{summary['median']:.6g}",
        "p75_gwei": f"{summary['p75']:.6g}", "p90_gwei": f"{summary['p90']:.6g}", "max_gwei": f"{summary['max']:.6g}",
        "cheapest_hour_utc": summary["cheapest_hour"], "priciest_hour_utc": summary["priciest_hour"],
        "gas_used_ratio_mean": f"{summary['gas_used_ratio_mean']:.4f}",
        "blob_median_gwei": "" if summary["blob_median"] is None else f"{summary['blob_median']:.6g}",
    }
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gasweek", description="when is ethereum cheapest? base fee by hour of day, last week.")
    ap.add_argument("--hours", type=float, default=168, help="window length in hours (default 168 = 7 days)")
    ap.add_argument("--tz", default="0", help="hour offset for the hour-of-day table, e.g. +2 for berlin in summer (default utc)")
    ap.add_argument("--svg", metavar="PATH", help="write a chart (fee over time + hour-of-day bars)")
    ap.add_argument("--csv", metavar="PATH", help="write every block: number, timestamp, base fee, gas used ratio, blob fee")
    ap.add_argument("--json", action="store_true", help="print the summary as json instead of the table")
    ap.add_argument("--summary-append", metavar="PATH", help="append one summary row to a csv (used by the daily workflow)")
    ap.add_argument("--rpc", action="append", metavar="URL", help="json-rpc endpoint (repeatable, tried in order)")
    ap.add_argument("--quiet", action="store_true", help="no table on stdout")
    ap.add_argument("--version", action="version", version=f"gasweek {__version__}")
    args = ap.parse_args(argv)

    try:
        tz_hours = parse_tz(args.tz)
    except ValueError:
        print(f"error: cannot parse --tz {args.tz!r}", file=sys.stderr)
        return 2
    blocks = max(1, int(args.hours * BLOCKS_PER_HOUR))
    try:
        rows = fetch(Rpc(args.rpc) if args.rpc else Rpc(), blocks)
    except (RpcError, RpcUnavailable) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("error: empty fee history", file=sys.stderr)
        return 2
    summary = summarize(rows, tz_hours)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["block", "timestamp", "base_fee_gwei", "gas_used_ratio", "blob_fee_gwei"])
            for r in rows:
                w.writerow([r.number, r.timestamp, f"{r.base_fee_gwei:.9g}", f"{r.gas_used_ratio:.4f}",
                            "" if r.blob_fee_gwei is None else f"{r.blob_fee_gwei:.9g}"])
    if args.svg:
        with open(args.svg, "w", encoding="utf-8") as f:
            f.write(render(rows, tz_hours))
    if args.summary_append:
        append_summary(args.summary_append, summary)
    if args.quiet:
        return 0
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(report(summary, tz_hours, by_hour(rows, tz_hours)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
