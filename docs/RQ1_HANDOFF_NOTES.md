# RQ1 Handoff Notes (for Team)

## Scope
This note explains:
- what each RQ1 graph means,
- which data and filters were used,
- how the RQ1 CSV outputs are computed and interpreted.

## Run Configuration Used
Command:

```bash
python src/intermediate_report_exports.py --rq rq1 --year 2025
```

Default filters from the runner:
- `--year 2025`
- `--voltage-level "High Voltage Import"`
- `--dc-type ""` (no DC-type filtering)
- `--centres ""` (all centres included)
- `--min-utilisation 0.1` (strictly greater than 0.1)
- `--chunksize 750000`

Important:
- `min-utilisation` removes very low-load rows before analysis.
- Centre-level and aggregate calculations both use the same filters.

## Data Source and Unit
Input file:
- `data/raw/ukpn-data-centre-demand-profiles.csv`

Relevant columns used:
- `anonymised_data_centre_name`
- `utc_timestamp`
- `hh_utilisation_ratio`
- plus filter columns (`dc_type`, `cleansed_voltage_level`)

Time granularity:
- half-hourly (`hh`), so 48 points/day.

## Core Preprocessing Logic
1. Filter rows by voltage/DC type/centre/min-utilisation.
2. Build aggregate half-hour timeseries by averaging utilisation across matched rows per timestamp.
3. Build the annual mean-day profile for 2025 from all filtered centre-level rows.
4. For RQ1 centre analysis, load centre-level rows for the whole year.

## Figure Outputs and Meaning

## 1) `figure0_intro_annual_mean_day_all_centres.png`
This is the main combined RQ1 dashboard (2x2 panels):

Panel A: Annual mean-day vs weekday/weekend patterns
- Annual mean-day profile (2025) vs weekday mean vs weekend mean.
- Includes weekday p10-p90 band.
- Purpose: shows the 08:00-18:00 style structure is not a one-day artifact.

Panel B: Cross-centre variability by hour
- Boxplot by hour based on annual centre-level hourly averages.
- Purpose: shows dispersion across centres for each hour.

Panel C: One-hour load jump distribution by hour
- Boxplot of `|delta_1h|` by hour over all centres and all days.
- `delta_1h` compares each centre against the value exactly one timestamp hour earlier.
- Purpose: identifies time windows with stronger ramp/jump behavior.

Panel D: Top 20 centres by one-hour jump count
- Bar chart of centres with most jumps.
- Bar colors indicate variability bucket (`low`, `medium`, `high`) from CV ranking.
- Purpose: quickly identify centres with highest jump frequency.

## 2) `figure0_1_rq1_center_load_jumps_2025.png`
This is centre-focused detail for load jumps (non-aggregated view):

Panel A: Centre x Hour heatmap
- Value = mean `|delta_1h|` for each (centre, hour).
- Centres sorted by `jump_count_1h` descending.
- Purpose: visual fingerprint of which centres jump most and when.

Panel B: Top 10 centre jump profiles
- Line plot of hourly mean `|delta_1h|` for top jump centres.
- Purpose: compare centre-specific jump shapes over the day.

## CSV Outputs and Column Definitions

## 1) `rq1_center_variability_metrics_2025.csv`
One row per data centre.

Columns:
- `centre`: centre identifier
- `n_timesteps`: number of half-hour rows after filters
- `mean_utilisation`: annual mean utilisation
- `std_utilisation`: annual std dev
- `peak_utilisation`: annual max utilisation
- `peak_to_average_ratio`: `peak / mean`
- `coefficient_of_variation`: `std / mean`
- `mean_abs_delta_1h`: annual mean of `|delta_1h|`
- `jump_threshold_p90_abs_delta_1h`: centre-specific p90 of `|delta_1h|`
- `jump_count_1h`: count of rows where `|delta_1h| >= p90 threshold`
- `jump_share_1h`: `jump_count_1h / number_of_valid_deltas`
- `variability_bucket`: low/medium/high bucket from CV percentile grouping

Interpretation note:
- Since threshold is centre-specific p90, `jump_share_1h` tends to be around 10% by construction.
- Use `jump_count_1h`, `mean_abs_delta_1h`, and `coefficient_of_variation` together for ranking.

## 2) `rq1_center_variability_bucket_summary_2025.csv`
Aggregated summary by bucket (`low`, `medium`, `high`).

Columns:
- `variability_bucket`
- `n_centres`
- `mean_cv`
- `mean_jump_share_1h`
- `mean_peak_to_average`

Purpose:
- Compare groups of centres by operational variability intensity.

## Recommended One-Liner for Team
RQ1 now evaluates annual center-level dynamics (not single-day medians), quantifies one-hour load jumps per centre, and groups centres by variability to identify which centres and hours drive operational volatility in 2025.
