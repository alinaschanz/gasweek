# changelog

all notable changes to gasweek. the format follows [keep a changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [semver](https://semver.org/) as far as a command line tool has an api.

## [unreleased]

## [0.1.0] - 2026-09-08

first cut: base fee by hour of day over the last week, table, svg and a daily dataset.

- `eth_feeHistory` in parallel pages with interpolated timestamps
- hour-of-day and weekday tables, percentiles, svg chart, csv and json
- daily workflow writing `data/daily.csv` and `data/last-7d.svg`
