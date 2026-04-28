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

Battery power is scenario-specific:

- `10%` BESS cases use `battery_power = 0.10 * annual_peak_utilisation`
- `25%` BESS cases use `battery_power = 0.25 * annual_peak_utilisation`

Battery energy is:

- `4h battery_energy = battery_power * 4`
- `8h battery_energy = battery_power * 8`

The `4h` and `8h` labels refer to battery energy duration. They are separate from the RQ2 daily flexibility budgets of `2.5` and `4.0` peak-equivalent hours.

The `25%` BESS cases are also allowed a more aggressive operating envelope than the `10%` cases:

- `10%` cases use a `10%-90%` usable SoC band and keep the terminal target at the carried current SoC
- `25%` cases use a `5%-95%` usable SoC band and target a lower terminal reserve of `35%` of battery energy

This setup is intentional: the exploratory `25%` flex case is meant to test whether deeper operational flexibility can be paired with a stronger behind-the-meter storage response.

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

- Original annual peak: `0.3684`.
- Residual annual peak after RQ2 flexibility: `0.3616` in both the `10%` and `25%` flex cases on this branch.
- Residual annual peak after BESS ranges from about `0.3454` to `0.3397` across the four BESS cases.
- Annual peak reduction versus original ranges from about `6.25%` to `7.78%`.
- `price_signal_used = True`, because the UK price CSV was available.

The strongest case on this branch is `25% Flex + 8h BESS` at `0.3397`, equivalent to about `7.78%` annual peak reduction versus original. The `25%` BESS cases now outperform the matching `10%` cases not only because of longer energy duration, but also because they are allowed a larger battery power fraction and a looser SoC reserve policy.

## Inherited RQ2 Limitations

RQ3 inherits the structure of the RQ2 flex-adjusted load that it dispatches on top of. On this branch, the RQ2 step uses the narrower `11:00-19:00` source window and fixed `22:00-06:00` recovery window. Two important limitations remain:

- overnight recovery is still constrained to the fixed `22:00-06:00` window
- recovery is deterministic and does not model endogenous queue or rebound dynamics

In other words, RQ3 does not remove the remaining RQ2 simplifications. It evaluates BESS on top of them.

## Figure 2 Outputs

Report-ready files:

- `rq3/figure2_flex_bess_10_intermediate.png`
- `rq3/figure2_flex_bess_25_intermediate.png`
- `rq3/bess_summary_intermediate.csv`
- `rq3/scenario_comparison_table_2025.csv`

The figures show annual mean 48-hour profiles for:

- original load
- flex-only load
- flex plus 4h BESS
- flex plus 8h BESS
- battery net power
- battery state of charge
- UK electricity price on the right-hand axis when available

## Scenario Comparison Table

`rq3/scenario_comparison_table_2025.csv` is the compact table for final-report and presentation use. It intentionally stays at six columns:

- `scenario`
- `flex_case`
- `bess_duration`
- `residual_peak_utilisation`
- `annual_peak_reduction_vs_original_percent`
- `price_weighted_cost_reduction_vs_original_percent`

These columns are defensible because data-centre demand-response studies commonly evaluate peak avoidance and electricity-cost savings, while behind-the-meter storage studies commonly evaluate peak-demand reduction. The table also includes the residual peak so the percentage reduction is anchored to the remaining utilisation level.

The cost metric is a price-weighted import proxy:

`sum(load * UK electricity price * dt_hours)`

Because the project uses utilisation ratios rather than MW, this is not an absolute electricity bill. It excludes demand charges, standing charges, taxes, network tariffs, degradation, and investment cost. Use it only for relative comparison across scenarios under the same annual price series.

A report-ready Markdown copy is available in `docs/SCENARIO_COMPARISON_TABLE.md`.

## Final Report Wording

Use:

> RQ3 models a co-located BESS as a behind-the-meter asset operating on the RQ2 flex-adjusted data-centre load. Dispatch is solved over a 48-hour receding horizon at half-hour resolution. The objective minimizes residual peaks first and uses UK electricity price as a secondary dispatch signal when price data is available.

Also use:

> The battery is not sized identically across all scenarios. The `10%` BESS cases use battery power equal to `10%` of the annual peak utilisation, while the `25%` BESS cases use `25%`. The exploratory `25%` cases also operate with a wider usable SoC band (`5%-95%`) and a lower terminal reserve target (`35%` of battery energy), allowing them to respond more aggressively to peak events.

For the result:

> In the 2025 utilisation profile generated on this branch, RQ2 flexibility alone delivers only a modest peak change, but adding BESS reduces the annual peak from `0.3684` to between about `0.3454` and `0.3397`, equivalent to about `6.25%` to `7.78%` peak reduction depending on the scenario. The best case is `25% Flex + 8h BESS`.

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
- McFadden, W. et al. (2016), *Saving on Data Center Energy Bills with EDEALS: Electricity Demand-response Easy Adjusted Load Shifting*. `https://www.usenix.org/conference/cooldc16/workshop-program/presentation/mcfadden`
- Neubauer, J. and Simpson, M. (2015), *Deployment of Behind-The-Meter Energy Storage for Demand Charge Reduction*. `https://doi.org/10.2172/1168774`
- Zhang, X. A. and Zavala, V. M. (2021), *Remunerating Space-Time, Load-Shifting Flexibility from Data Centers in Electricity Markets*. `https://arxiv.org/abs/2105.11416`
- Norris, T. H., Profeta, T., Patiño-Echeverri, D., and Cowie-Haskell, A. (2025), *Rethinking Load Growth: Assessing the Potential for Integration of Large Flexible Loads in US Power Systems*. `https://nicholasinstitute.duke.edu/publications/rethinking-load-growth`
- IEA (2025), *Energy and AI*. `https://www.iea.org/reports/energy-and-ai`
- Wang, Y., Guo, Q., and Chen, M. (2025), *Providing load flexibility by reshaping power profiles of large language model workloads*. `https://doi.org/10.1016/j.adapen.2025.100232`
- Chen, X., Wang, X., Colacelli, A., Lee, M., and Xie, L. (2025), *Electricity Demand and Grid Impacts of AI Data Centers: Challenges and Prospects*. `https://doi.org/10.48550/arXiv.2509.07218`

## Caveats

- Results are in utilisation ratios, not MW.
- Battery sizing and SoC policy are fixed by scenario, not optimized economically.
- The model does not include degradation cost, full tariff structure, standing charges, or investment cost.
- The mean 48-hour figure is a reporting view; annual peak metrics remain the primary result.
