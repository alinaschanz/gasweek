"""pull eth_feeHistory in 1024-block pages and give every block a timestamp.

eth_feeHistory has no timestamps, so one block header per page is fetched and the
blocks in between are interpolated. post-merge blocks are 12 s apart except for
missed slots, so the error inside a page stays well under a minute.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .rpc import Rpc

PAGE = 1024  # the largest block count most public nodes accept per eth_feeHistory call
BLOCKS_PER_HOUR = 300  # 3600 s / 12 s slots


@dataclass(frozen=True)
class BlockFee:
    number: int
    timestamp: int  # unix seconds, interpolated
    base_fee_gwei: float
    gas_used_ratio: float
    blob_fee_gwei: float | None = None
    tips_gwei: tuple[float, float, float] | None = None  # p10, p50, p90 of the priority fees paid in the block


def plan_pages(latest: int, blocks: int, page: int = PAGE) -> list[tuple[int, int]]:
    """(newest_block, count) pairs, newest first, covering `blocks` blocks ending at `latest`."""
    pages = []
    newest, remaining = latest, blocks
    while remaining > 0:
        count = min(page, remaining, newest + 1)
        pages.append((newest, count))
        newest -= count
        remaining -= count
        if newest < 0:
            break
    return pages


def interpolate(anchors: dict[int, int], number: int) -> int:
    """linear interpolation between the two anchor blocks around `number`."""
    if number in anchors:
        return anchors[number]
    below = [b for b in anchors if b < number]
    above = [b for b in anchors if b > number]
    if below and above:
        b1, b2 = max(below), min(above)
        return round(anchors[b1] + (number - b1) * (anchors[b2] - anchors[b1]) / (b2 - b1))
    if below:  # extrapolate at 12 s (only for the few blocks past the last anchor)
        b1 = max(below)
        return anchors[b1] + 12 * (number - b1)
    b2 = min(above)
    return anchors[b2] - 12 * (b2 - number)


TIP_PERCENTILES = (10, 50, 90)


def parse_page(result: dict) -> list[dict]:
    """rows for one eth_feeHistory answer (the last baseFeePerGas entry is the *next* block, dropped)."""
    oldest = int(result["oldestBlock"], 16)
    base = [int(x, 16) for x in result["baseFeePerGas"]]
    used = [float(x) for x in result.get("gasUsedRatio") or []]
    blob = result.get("baseFeePerBlobGas")
    blob_fees = [int(x, 16) for x in blob] if blob else None
    reward = result.get("reward") or []
    rows = []
    for i in range(len(used)):
        tips = None
        if i < len(reward) and reward[i] and len(reward[i]) >= 3:
            tips = tuple(int(x, 16) / 1e9 for x in reward[i][:3])
        rows.append({
            "number": oldest + i,
            "base_fee_gwei": base[i] / 1e9,
            "gas_used_ratio": used[i],
            "blob_fee_gwei": (blob_fees[i] / 1e9) if blob_fees and i < len(blob_fees) else None,
            "tips_gwei": tips,
        })
    return rows


def fetch(rpc: Rpc, blocks: int, latest: int | None = None, workers: int = 4, tips: bool = False) -> list[BlockFee]:
    """with tips=True the node also returns the p10/p50/p90 priority fees paid in every block (a heavier answer)."""
    latest = rpc.block_number() if latest is None else latest
    pages = plan_pages(latest, blocks)
    percentiles = list(TIP_PERCENTILES) if tips else []
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for result in pool.map(lambda page: rpc.call("eth_feeHistory", [hex(page[1]), hex(page[0]), percentiles]), pages):
            rows.extend(parse_page(result))
    rows.sort(key=lambda r: r["number"])
    if not rows:
        return []
    anchor_blocks = sorted({rows[0]["number"], rows[-1]["number"], *(newest - count + 1 for newest, count in pages)})
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        stamps = list(pool.map(rpc.block_timestamp, anchor_blocks))
    anchors = dict(zip(anchor_blocks, stamps, strict=True))
    return [
        BlockFee(
            number=r["number"], timestamp=interpolate(anchors, r["number"]), base_fee_gwei=r["base_fee_gwei"],
            gas_used_ratio=r["gas_used_ratio"], blob_fee_gwei=r["blob_fee_gwei"], tips_gwei=r.get("tips_gwei"),
        )
        for r in rows
    ]
