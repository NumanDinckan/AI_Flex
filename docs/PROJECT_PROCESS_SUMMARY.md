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

The current `main` branch uses scenario-specific recovery windows:

- `10%` Flex: `10%` load reduction co-optimized across up to `2.5` peak-equivalent hours per day.
- `25%` Flex: `25%` load reduction co-optimized across up to `4.0` peak-equivalent hours per day.
- Recovery window, `10%`: `22:00-06:00`.
- Recovery window, `25%`: `20:00-08:00`.
- Source window: `11:00-19:00`.

The model co-optimizes source reductions and recipient recovery in a daily linear program, then recovers shifted load in the scenario-specific off-peak recipient window where feasible.

The flex selector is intentionally load-driven. UK price data is not used to choose flexible source intervals; price responsiveness is reserved for the BESS dispatch stage and the scenario comparison cost proxy.

The implementation minimizes a shared daily peak variable across source and recovery slots so the rebound does not simply replace the daytime peak inside the daily LP.

RQ2 outputs:

- `rq2/figure1_flex_intermediate.png`
- `rq2/figure1_flex_intermediate_annual_shift_components.png`
- `rq2/figure1_flex_intermediate_annual_48h_shift_window.png`
- `rq2/figure1_flex_intermediate_peak_event_day_10_25.png`
- `rq2/flexibility_summary_intermediate.csv`

Current 2025 result:

- Original annual peak: `0.3684`
- Residual annual peak after `10%` flex: `0.3616`
- Residual annual peak after `25%` flex: `0.3616`
- Shifted energy, `10%` case: about `16.96` utilisation-hours
- Shifted energy, `25%` case: about `27.95` utilisation-hours

Main interpretation:

RQ2 shifts load and gives a modest annual peak reduction, but both flex-only scenarios still land at the same residual annual peak. The widened `25%` recovery corridor realizes more shifted energy, yet recovery diagnostics still show high unmet budget across the year. Therefore, RQ2 is best presented as the operational load-shifting step that prepares the input for RQ3.

## 7. RQ3 Process

RQ3 applies a co-located battery energy storage system after RQ2 flexibility.

The BESS cases are:

- `10% Flex + 4h BESS`
- `10% Flex + 8h BESS`
- `25% Flex + 4h BESS`
- `25% Flex + 8h BESS`

Battery sizing uses the original annual utilisation peak as the reference:

```text
battery_power = battery_power_fraction * original_annual_peak
battery_energy = battery_power * duration_hours
```

The scenario sizing is:

| Scenario | Power fraction | Duration | Energy relative to original peak |
| --- | ---: | ---: | ---: |
| `10% Flex + 4h BESS` | `0.10` | `4h` | `0.40 * original_peak` |
| `10% Flex + 8h BESS` | `0.05` | `8h` | `0.40 * original_peak` |
| `25% Flex + 4h BESS` | `0.25` | `4h` | `1.00 * original_peak` |
| `25% Flex + 8h BESS` | `0.125` | `8h` | `1.00 * original_peak` |

Within each flex case, the `8h` BESS is energy-matched to the paired `4h` case and uses half the power rating. This makes the `8h` case a lower-C-rate sustained-delivery asset rather than a same-power doubled-energy upgrade.

The BESS dispatch is a duration-specific receding-horizon linear program:

- `4h` batteries use a `48h` horizon.
- `8h` batteries use a `72h` horizon.

It is peak-first:

1. minimize residual grid-import peak
2. minimize terminal state-of-charge deviation
3. use price-weighted dispatch as a secondary objective when UK prices are available

RQ3 outputs:

- `rq3/figure2_flex_bess_10_intermediate.png`
- `rq3/figure2_flex_bess_25_intermediate.png`
- `rq3/bess_summary_intermediate.csv`
- `rq3/scenario_comparison_table_2025.csv`

Current 2025 result:

- Original annual peak: `0.3684`
- Residual annual peak after RQ2 flexibility: `0.3616`
- Residual annual peak after BESS: `0.3454` to `0.3404`
- Annual peak reduction after BESS: `6.24%` to `7.60%`

Main interpretation:

BESS provides the main annual peak reduction result. The strongest annual-peak result is `25% Flex + 8h BESS`, with residual peak `0.3404` and `7.6045%` peak reduction versus original. The strongest price-weighted cost proxy result is `25% Flex + 4h BESS`, with `0.9013%` reduction. This split is consistent with the sizing design: the lower-power `8h` case can sustain delivery, while the higher-power `4h` case has more leverage for price-timed charge and discharge inside the peak-first cap.

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

That branch replaces fixed recovery windows with dynamic recovery within a `24` hour horizon using low-load and low-price recipient slots.

The current `main` branch, however, uses scenario-specific fixed recovery windows.

## 11. Final Storyline

The project should be presented as a three-step analysis:

1. RQ1 shows that public data-centre load profiles contain variability, peak concentration, and measurable flexibility potential.
2. RQ2 applies explicit flexibility rules to test operational load shifting.
3. RQ3 applies BESS after flexibility and shows the main annual peak reduction.

The central final message is:

> Public data-centre utilisation profiles show concentrated peak periods. Operational flexibility can shift some load and modestly reduce the annual peak, but recovery constraints remain binding. Adding BESS after flexibility reduces the residual annual peak by about `7.60%` in the strongest case, while the price-weighted cost proxy improves most in the `25% Flex + 4h BESS` case.
