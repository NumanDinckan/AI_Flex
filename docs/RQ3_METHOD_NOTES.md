# RQ3 Method Notes

This note documents the current RQ3 BESS implementation.

## Purpose
RQ3 evaluates whether a co-located battery can reduce residual peaks after the RQ2 operational flexibility step.

RQ3 now plots an annual mean 48-hour horizon instead of exact calendar days. The dispatch itself still runs over the full year before that 48-hour profile is averaged for reporting.

## Pipeline Position
Processing order:

1. Load and aggregate the filtered half-hour utilisation series.
2. Compute full-year baselines, including `mean_day_base`.
3. Apply RQ2 operational flexibility.
4. Apply BESS dispatch to the flex-adjusted full-year load.
5. Export annual mean 48-hour figures and annual peak summaries.

## Battery Scenarios
The code evaluates four BESS cases:

- `10%_flex + 4h-Battery`
- `10%_flex + 8h-Battery`
- `25%_flex + 4h-Battery`
- `25%_flex + 8h-Battery`

Battery power is set as:

- `battery_power = 0.25 * annual_peak_utilisation`

Battery energy is:

- `4h battery_energy = battery_power * 4`
- `8h battery_energy = battery_power * 8`

The `4h` and `8h` labels refer to battery energy duration, not the RQ2 flexibility duration.

## Dispatch Objective
The BESS controller is a 48-hour receding-horizon LP with carried state of charge and historical peak state.

Without a price file, the controller is peak-first:

1. minimize residual grid-import peak
2. minimize terminal state-of-charge deviation
3. minimize battery throughput

With `--price-input`, the third stage becomes price-aware:

1. minimize residual grid-import peak
2. minimize terminal state-of-charge deviation
3. minimize price-weighted grid import within the peak cap, with a small throughput tiebreaker

This is a combined peak-shaving plus price-aware dispatch, not a full tariff or degradation co-optimization.

## Peak Definitions
The summary CSV uses these report terms:

- `original_peak_load`: peak before flex and BESS
- `residual_peak_after_flex`: peak after RQ2 flexibility
- `residual_peak_after_flex_and_bess`: peak after both flexibility and BESS

It also reports:

- `annual_peak_reduction_vs_original_percent`
- `annual_peak_reduction_vs_matching_flex_only_percent`
- `mean_horizon_peak_reduction_vs_original_percent`
- `mean_horizon_peak_reduction_vs_matching_flex_only_percent`
- annual charge/discharge energy
- total equivalent cycles
- mean-horizon SoC statistics
- `price_signal_used`
- `total_grid_cost_proxy_year` when a price CSV is supplied

## Outputs
RQ3 writes:

- `outputs/rq3/figure2_flex_bess_10_intermediate.png`
- `outputs/rq3/figure2_flex_bess_25_intermediate.png`
- `outputs/rq3/bess_summary_intermediate.csv`

The figures show annual mean 48-hour profiles:

- original load
- flex-only load
- flex plus 4h BESS
- flex plus 8h BESS
- battery net power
- battery state of charge

## Report Wording
Recommended wording:

“RQ3 models a co-located battery as a behind-the-meter asset operating on the flex-adjusted data-centre load. The dispatch is solved over a 48-hour receding horizon at half-hour resolution. It minimizes residual peaks first and, when UK price data is supplied, uses price as a secondary dispatch criterion within the peak cap.”

## References
- Colangelo, P. et al. (2025), *Turning AI Data Centers into Grid-Interactive Assets: Results from a Field Demonstration in Phoenix, Arizona*. `https://arxiv.org/abs/2507.00909`
- Colangelo, P. et al. (2026), *AI data centres as grid-interactive assets*, *Nature Energy*. `https://doi.org/10.1038/s41560-025-01927-1`
- DiOrio, N. (2017), *An Overview of the Automated Dispatch Controller Algorithms in the System Advisor Model (SAM)*. `https://www.nrel.gov/docs/fy18osti/68614.pdf`
- Mirletz, B. T. and Guittet, D. L. (2021), *Heuristic Dispatch Based on Price Signals for Behind-the-Meter PV-Battery Systems in the System Advisor Model*. `https://www.nrel.gov/docs/fy21osti/80258.pdf`
- Neubauer, J. and Simpson, M. (2015), *Deployment of Behind-The-Meter Energy Storage for Demand Charge Reduction*. `https://doi.org/10.2172/1168774`
