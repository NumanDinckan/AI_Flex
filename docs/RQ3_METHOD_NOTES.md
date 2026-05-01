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

## Battery Scenario Design

The model evaluates four cases:

- `10% Flex + 4h BESS`
- `10% Flex + 8h BESS`
- `25% Flex + 4h BESS`
- `25% Flex + 8h BESS`

The annual peak of the original utilisation profile is the sizing reference:

```text
annual_peak = max(utilisation)
battery_power = battery_power_fraction * annual_peak
battery_energy = battery_power * duration_hours
```

Scenario sizing:

| Scenario | Power Fraction | Duration | Energy |
| --- | ---: | ---: | ---: |
| `10% Flex + 4h BESS` | `0.10` | `4h` | `0.40 * annual_peak` |
| `10% Flex + 8h BESS` | `0.05` | `8h` | `0.40 * annual_peak` |
| `25% Flex + 4h BESS` | `0.25` | `4h` | `1.00 * annual_peak` |
| `25% Flex + 8h BESS` | `0.125` | `8h` | `1.00 * annual_peak` |

The `4h` and `8h` labels refer to battery energy duration, not to the RQ2 daily flexibility budgets of `2.5` and `4.0` peak-equivalent hours.

Within each flex case, the `8h` BESS is energy-matched to its paired `4h` case and has half the power rating. This is a deliberate lower-C-rate sustained-delivery archetype. It should not be described as a same-power, doubled-energy upgrade. The tradeoff is that the `8h` case has less instantaneous peak-clipping capability but can sustain lower-power discharge for longer.

The usable SoC bands and terminal targets are:

| Scenario Group | SoC Band | Terminal SoC Target |
| --- | ---: | ---: |
| `10%` flex cases | `10%-90%` | `4h`: carried current SoC; `8h`: `50%` |
| `25%` flex cases | `5%-95%` | `4h`: `35%`; `8h`: `50%` |

The `25%` cases remain exploratory because they assume deeper flexible load and a wider usable SoC band. The `8h` cases test a different battery role: sustained delivery and load leveling rather than high-power peak clipping.

## Dispatch Optimization

The BESS controller is a duration-specific receding-horizon linear program with carried state of charge and historical peak state:

- `4h` BESS cases use a `48h` rolling horizon.
- `8h` BESS cases use a `72h` rolling horizon.

The longer `8h` horizon is used to reduce horizon-boundary effects and give the medium-duration battery one additional overnight recovery/charging opportunity in the lookahead. The model executes only the first day of each optimized horizon, carries the final executed SoC forward, and then resolves the next horizon.

For each rolling horizon, dispatch is solved lexicographically:

1. Minimize the residual grid-import peak.
2. Minimize terminal SoC deviation subject to the peak cap from stage 1.
3. Choose a dispatch pattern subject to the peak cap and terminal slack from stages 1-2.

Without a price file, stage 3 minimizes battery throughput. With the UK price CSV, stage 3 minimizes price-weighted grid import within the feasible peak cap, with a small throughput tie-breaker.

The model constraints enforce:

- battery charge and discharge power limits
- SoC minimum and maximum limits
- round-trip efficiency of `90%`
- no grid export
- terminal SoC slack accounting
- historical peak accounting across executed days

Peak shaving remains the primary objective. Price affects dispatch timing only after the feasible peak cap has been established. Therefore, this is not a full tariff, investment, degradation, or electricity-bill optimization.

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
- Residual annual peak after BESS ranges from about `0.3454` to `0.3404` across the four BESS cases.
- Annual peak reduction versus original ranges from about `6.24%` to `7.60%`.
- `price_signal_used = True`, because the UK price CSV was available.

The strongest annual-peak case on this branch is `25% Flex + 8h BESS` at `0.3404`, equivalent to `7.6045%` annual peak reduction versus original. The strongest price-weighted cost proxy result is `25% Flex + 4h BESS` at `0.9013%`. This split is expected: the energy-matched lower-power `8h` cases produce less sharp peak clipping and less price-arbitrage leverage than a same-power 8h battery, but they better represent a sustained-delivery storage archetype.

## Inherited RQ2 Limitations

RQ3 inherits the structure of the RQ2 flex-adjusted load that it dispatches on top of. On this branch, the RQ2 step uses the narrower `11:00-19:00` source window and scenario-specific recovery windows. Two important limitations remain:

- recovery is still constrained to prescribed windows: `22:00-06:00` for `10%` and `20:00-08:00` for `25%`
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

> RQ3 models a co-located BESS as a behind-the-meter asset operating on the RQ2 flex-adjusted data-centre load. Dispatch is solved over a duration-specific receding horizon at half-hour resolution: 48 hours for 4h batteries and 72 hours for 8h batteries. The objective minimizes residual peaks first and uses UK electricity price as a secondary dispatch signal when price data is available.

Also use:

> The battery is not sized identically across all scenarios. Within each flex case, the 8h BESS is energy-matched to the paired 4h BESS but has half the power rating, so it represents a lower-C-rate sustained-delivery asset rather than a same-power energy expansion. The 8h cases also target 50% terminal SoC to preserve inter-day shifting energy.

For the result:

> In the 2025 utilisation profile generated on this branch, RQ2 flexibility alone delivers only a modest peak change, but adding BESS reduces the annual peak from `0.3684` to between about `0.3454` and `0.3404`, equivalent to about `6.24%` to `7.60%` peak reduction depending on the scenario. The best annual-peak case is `25% Flex + 8h BESS`.

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
