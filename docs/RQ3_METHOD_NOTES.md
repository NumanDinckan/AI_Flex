# RQ3 Method Notes

## Research Question

How much additional peak reduction can a co-located battery energy storage system provide after the RQ2 flexibility step?

RQ3 evaluates BESS as an operational peak-shaving asset applied after load flexibility. It does not size an investment portfolio and it does not run a full electricity-bill optimization.

## Data Basis

The BESS dispatch is run over the full-year half-hour series. Figure 2 then reports an annual mean 48-hour horizon, which is an averaged visualization rather than two exact calendar days.

The committed RQ3 outputs are in `rq3/`. If the runner is executed without `--output-dir .`, equivalent outputs are written under `outputs/rq3/`.

## Pipeline Position

Processing order:

1. Load and aggregate the filtered half-hour utilisation series.
2. Compute the full-year baselines.
3. Apply RQ2 operational flexibility.
4. Dispatch BESS on the flex-adjusted full-year load.
5. Export annual peak summaries and annual mean 48-hour figures.

## Battery Scenarios

The model evaluates four cases:

- `10% Flex + 4h BESS`
- `10% Flex + 8h BESS`
- `25% Flex + 4h BESS`
- `25% Flex + 8h BESS`

Battery power is set as:

`battery_power = 0.25 * annual_peak_utilisation`

Battery energy is:

- `4h battery_energy = battery_power * 4`
- `8h battery_energy = battery_power * 8`

The `4h` and `8h` labels refer to battery energy duration. They are separate from the RQ2 maximum flexibility duration of 3 peak hours.

## Dispatch Objective

The BESS controller is a 48-hour receding-horizon linear program with carried state of charge and historical peak state.

Without a price file, the controller is peak-first:

1. minimize residual grid-import peak
2. minimize terminal state-of-charge deviation
3. minimize battery throughput

With the UK price CSV, the third stage becomes price-aware:

1. minimize residual grid-import peak
2. minimize terminal state-of-charge deviation
3. minimize price-weighted grid import within the peak cap, with a small throughput tie-breaker

Peak shaving remains the primary objective. Price affects dispatch timing only after the feasible peak cap has been established.

## Peak Definitions

Use these terms consistently:

- `original_peak_load`: annual peak before flexibility and BESS.
- `residual_peak_after_flex`: annual peak after RQ2 flexibility.
- `residual_peak_after_flex_and_bess`: annual peak after both RQ2 flexibility and RQ3 BESS.

The annual peak fields are the main quantitative result fields. The mean-horizon fields describe the averaged 48-hour visualization and should not replace annual peak metrics in the report.

## Current 2025 Results

From `rq3/bess_summary_intermediate.csv`:

- Original annual peak: `0.5643`.
- Residual annual peak after RQ2 flexibility: `0.5643`.
- Residual annual peak after BESS: about `0.4239`.
- Annual peak reduction versus original: about `24.89%` for all four BESS cases.
- `price_signal_used = True`, because the UK price CSV was available.

The `4h` and `8h` BESS cases produce very similar annual peak reductions in the current summary. The main difference is in annual charge/discharge energy, equivalent cycles, and price-aware dispatch behavior.

## Figure 2 Outputs

Report-ready files:

- `rq3/figure2_flex_bess_10_intermediate.png`
- `rq3/figure2_flex_bess_25_intermediate.png`
- `rq3/bess_summary_intermediate.csv`

The figures show annual mean 48-hour profiles for:

- original load
- flex-only load
- flex plus 4h BESS
- flex plus 8h BESS
- battery net power
- battery state of charge
- UK electricity price on the right-hand axis when available

## Final Report Wording

Use:

> RQ3 models a co-located BESS as a behind-the-meter asset operating on the RQ2 flex-adjusted data-centre load. Dispatch is solved over a 48-hour receding horizon at half-hour resolution. The objective minimizes residual peaks first and uses UK electricity price as a secondary dispatch signal when price data is available.

For the result:

> In the 2025 utilisation profile, RQ2 flexibility alone does not reduce the absolute annual peak, but adding BESS reduces the residual annual peak from `0.5643` to about `0.4239`, a reduction of about `24.9%`.

## Presentation Use

Recommended slide:

1. Show Figure 2 for the `10%` and `25%` flexibility cases.
2. State that BESS is evaluated after the RQ2 flexibility rule.
3. Report the annual peak reduction, not only the visual mean-horizon result.
4. Explain that the price signal shapes dispatch after peak reduction, not as a full bill optimization.

## References

- Colangelo, P. et al. (2025), *Turning AI Data Centers into Grid-Interactive Assets: Results from a Field Demonstration in Phoenix, Arizona*. `https://arxiv.org/abs/2507.00909`
- Colangelo, P. et al. (2026), *AI data centres as grid-interactive assets*, *Nature Energy*. `https://doi.org/10.1038/s41560-025-01927-1`
- DiOrio, N. (2017), *An Overview of the Automated Dispatch Controller Algorithms in the System Advisor Model (SAM)*. `https://www.nrel.gov/docs/fy18osti/68614.pdf`
- Mirletz, B. T. and Guittet, D. L. (2021), *Heuristic Dispatch Based on Price Signals for Behind-the-Meter PV-Battery Systems in the System Advisor Model*. `https://www.nrel.gov/docs/fy21osti/80258.pdf`
- Neubauer, J. and Simpson, M. (2015), *Deployment of Behind-The-Meter Energy Storage for Demand Charge Reduction*. `https://doi.org/10.2172/1168774`

## Caveats

- Results are in utilisation ratios, not MW.
- Battery sizing is fixed by scenario, not optimized economically.
- The model does not include degradation cost, full tariff structure, standing charges, or investment cost.
- The mean 48-hour figure is a reporting view; annual peak metrics remain the primary result.
