# data

written by the [daily workflow](../.github/workflows/daily.yml) at 00:17 utc.

- `daily.csv`: one row per day, the 24 hours ending at the run. columns: `date_utc`, `blocks`,
  `first_block`, `last_block`, `min_gwei`, `p25_gwei`, `median_gwei`, `p75_gwei`, `p90_gwei`, `max_gwei`,
  `cheapest_hour_utc`, `priciest_hour_utc`, `gas_used_ratio_mean`, `blob_median_gwei`.
- `last-7d.svg`: the chart from `python -m gasweek --hours 168 --svg`, rebuilt every day.

the rows are as good as `eth_feeHistory` on a public node, which is to say: base fees are exact,
timestamps are interpolated inside each 1024-block page (see `gasweek/fees.py`).
