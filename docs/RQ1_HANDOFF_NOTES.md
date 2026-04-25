# RQ1 Handoff Notes

## Research Question

What do publicly available data centre load profiles reveal about variability, peak concentration, and potential flexibility?

RQ1 should now be answered with three linked ideas:

- Variability: how much the profiles move within short time windows.
- Peak concentration: whether high-load periods are spread evenly or concentrated in a small share of the year.
- Potential flexibility: how much load would need to be shifted to reduce those concentrated peaks.

## Run Configuration

Command:

```bash
python src/intermediate_report_exports.py --rq rq1 --year 2025 --output-dir .
```

Default filters:

- `--year 2025`
- `--voltage-level "High Voltage Import"`
- `--dc-type ""`
- `--centres ""`
- `--min-utilisation 0.1`
- `--chunksize 750000`

The analysis uses `data/raw/ukpn-data-centre-demand-profiles.csv` and the half-hourly `hh_utilisation_ratio` field.

## Main Figure

## `figure0_intro_annual_mean_day_all_centres.png`

Figure 0 is now a direct RQ1 evidence dashboard.

Panel A: Variability
- Shows the one-hour load-jump distribution by hour.
- Uses `|delta_1h|`, where each centre is compared with its own value exactly one hour earlier.
- This is the graph we keep because it directly shows short-run operational volatility.

Panel B: Peak concentration
- Shows the top of the annual load-duration curve.
- The x-axis is the share of highest-load half-hours included.
- The p99, p95, and p90 thresholds show how quickly the curve falls away from the annual peak.
- The figure annotates `peak/mean` and the top-10% share of above-mean load.

Panel C: Peak timing
- Shows which hours of the day contain the annual top-10% load intervals.
- This answers whether peaks are randomly distributed or concentrated in recognizable operating windows.

Panel D: Potential flexibility
- Shows the utilisation-hours above candidate peak caps (`p99`, `p95`, `p90`, `p85`, `p80`).
- Bars show how much load would need to be shifted to cap the profile at each threshold.
- The red line shows the implied reduction from the annual peak.

## Supporting Outputs

## `figure0_1_rq1_center_load_jumps_2025.png`

Centre-level detail for the one-hour jump story:

- Panel A: centre-by-hour heatmap of mean `|delta_1h|`.
- Panel B: hourly jump profiles for the top 10 centres by mean `|delta_1h|`.
- Centres with at least one week of observations are used for stable ranking.

## `rq1_profile_answer_summary_2025.csv`

One-row summary for answering RQ1 in text. Important fields:

- `peak_to_average_ratio`
- `p90_utilisation`, `p95_utilisation`, `p99_utilisation`
- `median_centre_cv`, `p90_centre_cv`
- `mean_centre_mean_abs_delta_1h`
- `top_1pct_share_of_above_mean_energy_percent`
- `top_5pct_share_of_above_mean_energy_percent`
- `top_10pct_share_of_above_mean_energy_percent`

Current 2025 values:

- Peak utilisation is about `1.79x` the annual mean.
- The top `10%` half-hours contain about `50.3%` of above-mean load.
- The top `5%` half-hours contain about `30.6%` of above-mean load.
- The top `1%` half-hours contain about `8.5%` of above-mean load.

## `rq1_peak_shaving_opportunity_2025.csv`

Threshold-by-threshold flexibility proxy. Important fields:

- `cap_percentile`
- `cap_utilisation`
- `hours_above_cap`
- `excess_utilisation_hours_to_shift`
- `peak_reduction_percent_of_peak`

Interpretation:

- Shaving to `p95` affects about `219.5` hours and requires about `5.37` utilisation-hours of shifted load.
- Shaving to `p90` affects about `439.0` hours and requires about `11.95` utilisation-hours of shifted load.
- These are not RQ2 flexibility results. They are RQ1 evidence of where flexibility potential exists before applying a scenario.

## `rq1_center_variability_metrics_2025.csv`

One row per centre. Important fields:

- `n_timesteps`
- `sufficient_coverage`
- `coefficient_of_variation`
- `mean_abs_delta_1h`
- `peak_to_average_ratio`
- `variability_bucket`

Centres need at least `336` half-hour observations, equal to one week, for stable variability bucket assignment. Centres below that remain in the metrics file but are labelled `insufficient coverage`.

## `rq1_center_variability_bucket_summary_2025.csv`

Variability bucket comparison using only centres with sufficient coverage. It shows that high-variability centres have higher CV, larger one-hour movements, and higher peak-to-average ratios than low-variability centres.

## Recommended RQ1 Answer

Publicly available data centre load profiles reveal that average load is relatively stable, but operational variability appears in short one-hour movements and differs meaningfully across centres. Peaks are not just isolated single points: the upper tail of the load-duration curve is concentrated enough that the top 10% of half-hours account for about half of above-mean load. This creates measurable flexibility potential, because reducing the profile to high-percentile caps such as p95 or p90 requires shifting a limited number of utilisation-hours from a clearly identified set of high-load intervals.
