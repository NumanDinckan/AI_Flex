# RQ3 Method Notes

This note documents the current RQ3 implementation in this repository after the recent BESS-method update. It is meant to explain what the code currently does, how to interpret the outputs, and which papers informed the current method choice.

## Purpose of RQ3

RQ3 asks a narrower follow-on question after RQ2:

- once flexible load has already been shifted,
- how much additional peak reduction can a co-located battery provide,
- and what does that dispatch look like over a short operational horizon?

In the current code, RQ3 is not a battery-sizing study and not a full tariff optimisation. It is a peak-shaving dispatch study built on top of the RQ2 flexed load.

## Pipeline position

The processing order in the code is:

1. Load and aggregate the filtered half-hour utilisation series.
2. Compute baseline features and the characteristic day.
3. Apply the RQ2 flexibility model.
4. Apply the RQ3 battery model to the flexed load.
5. Export the RQ3 plots and summary.

Relevant code:

- `src/intermediate_report_exports.py`
- `src/flex_method.py`
- `src/bess_method.py`
- `src/rq3_figure2.py`

## Input to RQ3

RQ3 does not run on the raw load directly. It runs on the RQ2 output columns:

- `load_flex_10`
- `load_flex_25`

That means the battery is evaluated as an additional peak-management layer after flexibility, not as a substitute for flexibility.

## Battery scenarios

The current code evaluates four scenarios:

- `10%_flex + 4h-Battery`
- `10%_flex + 8h-Battery`
- `25%_flex + 4h-Battery`
- `25%_flex + 8h-Battery`

The battery power is set as:

- `battery_power = 0.25 * annual_peak_utilisation`

The battery energy is then:

- `4h battery_energy = battery_power * 4`
- `8h battery_energy = battery_power * 8`

So the duration changes the usable stored energy, but the power rating is held constant across the `4h` and `8h` cases.

## Current dispatch method

The current dispatch in `src/bess_method.py` is a two-day, finite-horizon peak-shaving controller.

### Operational horizon

- horizon length: `48h`
- resolution: half-hourly
- controller type: receding horizon

Each dispatch step uses the current day plus the next day as the short planning horizon. This is a practical compromise:

- it is longer than the older single-day heuristic,
- it captures overnight recharge opportunities,
- and it remains lightweight enough to solve repeatedly over a full year.

### Objective structure

The current implementation is an LP-based peak-cap controller using `scipy.optimize.linprog`.

It solves the horizon in three lexicographic stages:

1. minimize the horizon grid-import peak cap
2. minimize terminal state-of-charge deviation
3. minimize battery throughput

This is intentionally peak-oriented. It is not yet a full electricity-bill minimisation model with explicit UK price input.

### Core constraints

The controller enforces:

- battery charge/discharge power limits
- state-of-charge bounds
- round-trip efficiency
- non-export to the grid
- intertemporal energy balance
- a carried historical peak state

The historical-peak state matters because the code is trying to mimic demand-charge style peak management rather than simply flattening each day independently.

### State-of-charge assumptions

The code uses:

- minimum SoC fraction: `10%`
- maximum SoC fraction: `90%`
- round-trip efficiency: `90%`
- starting SoC for each annual scenario: `50%` of battery energy

The dispatch also carries forward the realised end-of-day SoC from one day to the next within the annual simulation.

## What changed relative to the earlier heuristic

The earlier RQ3 logic in this repo was a day-isolated heuristic with:

- dynamic charge/discharge thresholds,
- selected peak and valley bands,
- and no short-horizon optimisation layer.

The current method is more defensible because it:

- optimises a short operational horizon instead of choosing ad hoc peak/valley bands,
- carries SoC between days,
- explicitly respects a grid-import cap,
- and tracks the previously observed peak when deciding how aggressively to discharge.

## Current outputs

RQ3 currently writes:

- `figure2_flex_bess_10_intermediate.png`
- `figure2_flex_bess_25_intermediate.png`
- `bess_summary_intermediate.csv`

### Figures

The current figures are two-day views:

- first panel: original load, flex-only load, and flex-plus-BESS load
- second panel: battery net power
- third panel: battery state of charge

The plotted window is:

- characteristic day
- plus the following day

This was changed intentionally so the reader can see both peak shaving and overnight recharge behaviour.

### Summary CSV

The summary includes:

- annual peak load after BESS
- two-day-window peak load
- peak reduction versus original load
- peak reduction versus the matching flex-only case
- annual charge/discharge energy
- total equivalent cycles
- target grid power statistics
- SoC statistics over the plotted two-day window

## What the current method is not

The current RQ3 code is still not:

- a full UK electricity-price optimisation
- a stochastic dispatch model
- a degradation-cost optimisation
- a full-year co-optimisation of flexibility and storage in one single model

So for the final report, it should be described as:

- a short-horizon, peak-oriented operational dispatch model
- informed by industry-style behind-the-meter peak-shaving formulations
- but still simplified relative to a full tariff co-optimisation framework

## Method references

The following papers and reports are the main references for how to describe the current method.

### Data-center flexibility literature

- Colangelo, P. et al. (2025), *Turning AI Data Centers into Grid-Interactive Assets: Results from a Field Demonstration in Phoenix, Arizona*.
  Link: `https://arxiv.org/abs/2507.00909`
- Colangelo, P. et al. (2026), *AI data centres as grid-interactive assets*, *Nature Energy*.
  Link: `https://doi.org/10.1038/s41560-025-01927-1`

These are useful mainly for the operational interpretation of flexible data-center load. They support statements such as a `25%` reduction for `3` hours during a grid event, but they do not match the exact current implementation in this repository one-for-one.

### Behind-the-meter battery dispatch and peak shaving

- DiOrio, N. (2017), *An Overview of the Automated Dispatch Controller Algorithms in the System Advisor Model (SAM)*, NREL.
  Link: `https://www.nrel.gov/docs/fy18osti/68614.pdf`
- Mirletz, B. T. and Guittet, D. L. (2021), *Heuristic Dispatch Based on Price Signals for Behind-the-Meter PV-Battery Systems in the System Advisor Model*, NREL / IEEE PVSC.
  Link: `https://www.nrel.gov/docs/fy21osti/80258.pdf`
- Neubauer, J. and Simpson, M. (2015), *Deployment of Behind-The-Meter Energy Storage for Demand Charge Reduction*, NREL / OSTI.
  Link: `https://doi.org/10.2172/1168774`
- Rehman, M. M., Kimball, J. W. and Bo, R. (2023), *Multi-layered Energy Management Framework for Extreme Fast Charging Stations Considering Demand Charges, Battery Degradation, and Forecast Uncertainties*.
  Link: `https://www.osti.gov/servlets/purl/1973122`

## Recommended wording for the report

If you want a defensible short description in the final report, the current code supports wording like this:

“RQ3 models a co-located battery as a behind-the-meter peak-shaving asset operating on the flex-adjusted data-center load. The dispatch is solved over a 48-hour receding horizon at half-hour resolution, subject to power, energy, state-of-charge, and efficiency constraints, with the objective of minimizing residual grid-import peaks while preserving operational feasibility.”
