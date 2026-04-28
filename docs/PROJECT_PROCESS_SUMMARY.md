# Project Process Summary

This document summarizes what was done in the project and how the final outputs were produced. It is written for use in the final report and presentation.

## 1. Project Aim

The project studies whether publicly available data-centre utilisation profiles reveal useful flexibility potential, and whether operational flexibility plus a co-located battery can reduce residual peaks.

The three research questions are:

- RQ1: What do publicly available data-centre load profiles reveal about variability, peak concentration, and potential flexibility?
- RQ2: How does operational load shifting affect the annual load profile under fixed flexibility definitions?
- RQ3: How much additional peak reduction can a co-located BESS provide after flexibility?

The results are expressed in utilisation ratios, not MW. This is important because the public dataset does not give site-level installed power capacity.

## 2. Input Data

Two input datasets are used:

- Data-centre demand profiles: `data/raw/ukpn-data-centre-demand-profiles.csv`
- UK electricity prices: `data/raw/United Kingdom.csv`

The demand data provides half-hourly utilisation ratios for anonymised data centres. The price file provides a timestamped UK electricity price signal used for plotting, price-aware BESS dispatch, and the scenario comparison cost proxy.

The analysis focuses on year `2025`.

## 3. Data Preparation

The pipeline is run through:

```bash
python src/intermediate_report_exports.py --rq all --year 2025 --output-dir .
```

The processing steps are:

1. Load the raw data-centre CSV.
2. Filter to valid utilisation rows above the minimum threshold.
3. Filter to `High Voltage Import` unless another voltage level is specified.
4. Aggregate valid centre rows into one half-hour utilisation time series.
5. Add timestamp features such as year, date, month, weekday, and half-hour index.
6. Attach UK electricity prices to matching timestamps when the price file is available.
7. Build annual baseline profiles and run the RQ1, RQ2, and RQ3 methods.

The committed report outputs were generated with `--output-dir .`, so the outputs appear directly in `rq1/`, `rq2/`, and `rq3/`.

## 4. Baseline Construction

The model constructs several baseline columns:

- `mean_day_base`: mean utilisation by year and half-hour of day.
- `med_base`: median utilisation by weekday and half-hour.
- `med_base_sensitivity`: median utilisation by month, weekday, and half-hour.

The figures mainly use annual mean-day and annual mean 48-hour views for readability. The calculations themselves are based on the full-year half-hour series.

## 5. RQ1 Process

RQ1 is the empirical evidence step. It does not apply flexibility. It asks what the public profiles reveal before any intervention.

RQ1 outputs:

- `rq1/figure0_intro_annual_mean_day_all_centres.png`
- `rq1/figure0_intro_annual_mean_day_all_centres_left.png`
- `rq1/figure0_1_rq1_center_load_jumps_2025.png`
- `rq1/rq1_profile_answer_summary_2025.csv`
- `rq1/rq1_peak_shaving_opportunity_2025.csv`
- `rq1/rq1_center_variability_metrics_2025.csv`
- `rq1/rq1_center_variability_bucket_summary_2025.csv`

RQ1 looks at:

- one-hour load jumps
- annual load-duration curve
- timing of top-load intervals
- peak-shaving opportunity at percentile caps such as p95 and p90

Main interpretation:

Public data-centre utilisation profiles are not completely flat. They show short-run variation and a concentrated upper tail. The top `10%` of half-hour intervals account for about half of above-mean load. This motivates targeted flexibility scenarios in RQ2.

## 6. RQ2 Process

RQ2 turns the flexibility opportunity into explicit operational scenarios.

The current `main` branch uses a fixed recovery window:

- `10%` Flex: up to `10%` load reduction for at most `3` consecutive peak hours.
- `25%` Flex: up to `25%` load reduction for at most `3` consecutive peak hours.
- Recovery window: `22:00-02:00`.
- Event search window: weekday `14:00-22:00`.

The model selects the highest consecutive peak block within the event window, reduces the flexible share there, and then recovers the shifted load in the fixed overnight recipient window where feasible.

The implementation also prevents recovery from creating a new load spike above the original annual peak.

RQ2 outputs:

- `rq2/figure1_flex_intermediate.png`
- `rq2/figure1_flex_intermediate_annual_shift_components.png`
- `rq2/figure1_flex_intermediate_annual_48h_shift_window.png`
- `rq2/figure1_flex_intermediate_peak_event_day_10_25.png`
- `rq2/flexibility_summary_intermediate.csv`

Current 2025 result:

- Original annual peak: `0.5643`
- Residual annual peak after `10%` flex: `0.5643`
- Residual annual peak after `25%` flex: `0.5643`
- Shifted energy, `10%` case: about `3.75` utilisation-hours
- Shifted energy, `25%` case: about `3.86` utilisation-hours

Main interpretation:

RQ2 shifts load but does not reduce the absolute annual peak in the current dataset. This happens because the absolute annual peak is not sufficiently affected by the selected flex events and because recovery constraints limit how much extra shifting the `25%` case can realise. Therefore, RQ2 is best presented as the operational load-shifting step that prepares the input for RQ3.

## 7. RQ3 Process

RQ3 applies a co-located battery energy storage system after RQ2 flexibility.

The BESS cases are:

- `10% Flex + 4h BESS`
- `10% Flex + 8h BESS`
- `25% Flex + 4h BESS`
- `25% Flex + 8h BESS`

Battery power is set as:

```text
battery_power = 0.25 * original_annual_peak
```

Battery energy is:

```text
4h battery_energy = battery_power * 4
8h battery_energy = battery_power * 8
```

The BESS dispatch is a 48-hour receding-horizon linear program. It is peak-first:

1. minimize residual grid-import peak
2. minimize terminal state-of-charge deviation
3. use price-weighted dispatch as a secondary objective when UK prices are available

RQ3 outputs:

- `rq3/figure2_flex_bess_10_intermediate.png`
- `rq3/figure2_flex_bess_25_intermediate.png`
- `rq3/bess_summary_intermediate.csv`
- `rq3/scenario_comparison_table_2025.csv`

Current 2025 result:

- Original annual peak: `0.5643`
- Residual annual peak after RQ2 flexibility: `0.5643`
- Residual annual peak after BESS: about `0.4239`
- Annual peak reduction after BESS: about `24.9%`

Main interpretation:

BESS provides the main annual peak reduction result. The `4h` and `8h` BESS cases produce very similar peak reductions because both have enough power to reduce the binding peak in this setup. The `8h` case has a larger impact on price-weighted cost because it has more energy capacity to move import away from expensive hours.

## 8. Scenario Comparison Table

The compact scenario comparison table is:

- `rq3/scenario_comparison_table_2025.csv`
- `docs/SCENARIO_COMPARISON_TABLE.md`

The table includes six columns:

- `scenario`
- `flex_case`
- `bess_duration`
- `residual_peak_utilisation`
- `annual_peak_reduction_vs_original_percent`
- `price_weighted_cost_reduction_vs_original_percent`

The peak reduction formula is:

```text
(original_peak - scenario_peak) / original_peak * 100
```

The price-weighted cost proxy is:

```text
sum(load * UK electricity price * dt_hours)
```

The cost reduction formula is:

```text
(original_cost_proxy - scenario_cost_proxy) / original_cost_proxy * 100
```

This is a relative cost proxy, not a real electricity bill. It does not include demand charges, fixed charges, network tariffs, taxes, BESS degradation, or investment cost.

## 9. Method Caveats

Important limitations:

- Utilisation ratios are not MW.
- RQ1 identifies potential; it does not prove contractual flexibility.
- RQ2 is a transparent scenario rule, not a job-level workload scheduler.
- RQ3 is not a full investment, tariff, or degradation model.
- The cost-reduction column is only a price-weighted proxy.
- Annual mean figures are visualization tools; annual peak metrics should be used for quantitative conclusions.

## 10. Sensitivity Variant

A separate branch exists for a no-fixed-recovery-window sensitivity:

```text
experiment/no-fixed-recovery-window
```

That branch replaces the fixed `22:00-02:00` recovery window with dynamic recovery within a `24` hour horizon using low-load and low-price recipient slots.

The current `main` branch, however, uses the fixed `22:00-02:00` recovery window.

## 11. Final Storyline

The project should be presented as a three-step analysis:

1. RQ1 shows that public data-centre load profiles contain variability, peak concentration, and measurable flexibility potential.
2. RQ2 applies explicit flexibility rules to test operational load shifting.
3. RQ3 applies BESS after flexibility and shows the main annual peak reduction.

The central final message is:

> Public data-centre utilisation profiles show concentrated peak periods. Operational flexibility can shift some load, but in the current fixed-window setup it does not reduce the absolute annual peak. Adding BESS after flexibility reduces the residual annual peak by about `24.9%`, while the price-weighted cost proxy also improves, especially for the `8h` BESS cases.
