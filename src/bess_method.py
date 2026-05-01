from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog


SOC_MIN_FRACTION = 0.10
SOC_MAX_FRACTION = 0.90
ROUND_TRIP_EFFICIENCY = 0.90
BESS_HORIZON_DAYS = 2
HORIZON_DAYS_BY_DURATION: dict[str, int] = {
    "4h": 2,
    "8h": 3,
}


@dataclass(frozen=True)
class BessScenario:
    scenario: str
    battery_duration: str
    duration_hours: float
    battery_power_fraction: float
    soc_min_fraction: float
    soc_max_fraction: float
    terminal_soc_fraction: float | None
    flex_col: str
    load_col: str
    soc_col: str
    charge_col: str
    discharge_col: str
    net_power_col: str


BESS_SCENARIOS: tuple[BessScenario, ...] = (
    BessScenario(
        scenario="10%_flex + 4h-Battery",
        battery_duration="4h",
        duration_hours=4.0,
        battery_power_fraction=0.10,
        soc_min_fraction=SOC_MIN_FRACTION,
        soc_max_fraction=SOC_MAX_FRACTION,
        terminal_soc_fraction=None,
        flex_col="load_flex_10",
        load_col="load_10_flex_4h_batt",
        soc_col="soc_10_flex_4h_batt",
        charge_col="charge_10_flex_4h_batt",
        discharge_col="discharge_10_flex_4h_batt",
        net_power_col="net_batt_10_flex_4h_batt",
    ),
    BessScenario(
        scenario="10%_flex + 8h-Battery",
        battery_duration="8h",
        duration_hours=8.0,
        battery_power_fraction=0.05,
        soc_min_fraction=SOC_MIN_FRACTION,
        soc_max_fraction=SOC_MAX_FRACTION,
        terminal_soc_fraction=0.50,
        flex_col="load_flex_10",
        load_col="load_10_flex_8h_batt",
        soc_col="soc_10_flex_8h_batt",
        charge_col="charge_10_flex_8h_batt",
        discharge_col="discharge_10_flex_8h_batt",
        net_power_col="net_batt_10_flex_8h_batt",
    ),
    BessScenario(
        scenario="25%_flex + 4h-Battery",
        battery_duration="4h",
        duration_hours=4.0,
        battery_power_fraction=0.25,
        soc_min_fraction=0.05,
        soc_max_fraction=0.95,
        terminal_soc_fraction=0.35,
        flex_col="load_flex_25",
        load_col="load_25_flex_4h_batt",
        soc_col="soc_25_flex_4h_batt",
        charge_col="charge_25_flex_4h_batt",
        discharge_col="discharge_25_flex_4h_batt",
        net_power_col="net_batt_25_flex_4h_batt",
    ),
    BessScenario(
        scenario="25%_flex + 8h-Battery",
        battery_duration="8h",
        duration_hours=8.0,
        battery_power_fraction=0.125,
        soc_min_fraction=0.05,
        soc_max_fraction=0.95,
        terminal_soc_fraction=0.50,
        flex_col="load_flex_25",
        load_col="load_25_flex_8h_batt",
        soc_col="soc_25_flex_8h_batt",
        charge_col="charge_25_flex_8h_batt",
        discharge_col="discharge_25_flex_8h_batt",
        net_power_col="net_batt_25_flex_8h_batt",
    ),
)


def get_bess_horizon_days(scenario: BessScenario) -> int:
    return HORIZON_DAYS_BY_DURATION.get(scenario.battery_duration, BESS_HORIZON_DAYS)


def _clip_soc(
    value: float,
    battery_energy: float,
    soc_min_fraction: float = SOC_MIN_FRACTION,
    soc_max_fraction: float = SOC_MAX_FRACTION,
) -> float:
    soc_min = soc_min_fraction * battery_energy
    soc_max = soc_max_fraction * battery_energy
    return float(np.clip(value, soc_min, soc_max))


def simulate_peak_cap_dispatch(
    load: np.ndarray,
    target_power: float,
    battery_power: float,
    battery_energy: float,
    initial_soc: float,
    terminal_soc_target: float,
    step_h: float,
    soc_min_fraction: float = SOC_MIN_FRACTION,
    soc_max_fraction: float = SOC_MAX_FRACTION,
    round_trip_eff: float = ROUND_TRIP_EFFICIENCY,
) -> dict[str, np.ndarray | float | bool]:
    base_load = np.asarray(load, dtype=float)
    n = base_load.size

    grid_load = base_load.copy()
    soc_trace = np.zeros(n, dtype=float)
    charge_power = np.zeros(n, dtype=float)
    discharge_power = np.zeros(n, dtype=float)

    if n == 0 or battery_power <= 0 or battery_energy <= 0 or step_h <= 0:
        return {
            "grid_load": grid_load,
            "soc": soc_trace,
            "charge_power": charge_power,
            "discharge_power": discharge_power,
            "net_battery_power": discharge_power - charge_power,
            "total_charge": 0.0,
            "total_discharge": 0.0,
            "cycles": 0.0,
            "final_soc": 0.0,
            "min_soc": 0.0,
            "max_soc": 0.0,
            "target_power": float(target_power),
            "feasible": bool(np.max(base_load) <= target_power + 1e-10),
        }

    eta = float(np.sqrt(round_trip_eff))
    soc_min = soc_min_fraction * battery_energy
    soc_max = soc_max_fraction * battery_energy
    soc = _clip_soc(initial_soc, battery_energy, soc_min_fraction=soc_min_fraction, soc_max_fraction=soc_max_fraction)
    terminal_target = _clip_soc(
        terminal_soc_target,
        battery_energy,
        soc_min_fraction=soc_min_fraction,
        soc_max_fraction=soc_max_fraction,
    )

    for i, base in enumerate(base_load):
        discharge_needed = max(base - target_power, 0.0)
        max_discharge = min(battery_power, max(0.0, (soc - soc_min) * eta / step_h))
        discharge = min(discharge_needed, max_discharge)

        charge = 0.0
        if base < target_power:
            charge_room = target_power - base
            max_charge = min(battery_power, max(0.0, (soc_max - soc) / (eta * step_h)))
            charge = min(charge_room, max_charge)

        soc += charge * step_h * eta
        soc -= discharge * step_h / eta
        soc = float(np.clip(soc, soc_min, soc_max))

        charge_power[i] = charge
        discharge_power[i] = discharge
        grid_load[i] = base + charge - discharge
        soc_trace[i] = soc

    total_charge = float(charge_power.sum() * step_h)
    total_discharge = float(discharge_power.sum() * step_h)
    cycles = float((total_charge + total_discharge) / (2.0 * battery_energy)) if battery_energy > 0 else 0.0
    feasible = bool(grid_load.max() <= target_power + 1e-6 and soc_trace[-1] >= terminal_target - 1e-6)

    return {
        "grid_load": grid_load,
        "soc": soc_trace,
        "charge_power": charge_power,
        "discharge_power": discharge_power,
        "net_battery_power": discharge_power - charge_power,
        "total_charge": total_charge,
        "total_discharge": total_discharge,
        "cycles": cycles,
        "final_soc": float(soc_trace[-1]),
        "min_soc": float(soc_trace.min()),
        "max_soc": float(soc_trace.max()),
        "target_power": float(target_power),
        "feasible": feasible,
    }


def find_optimal_peak_target(
    load: np.ndarray,
    battery_power: float,
    battery_energy: float,
    initial_soc: float,
    terminal_soc_target: float,
    step_h: float,
    soc_min_fraction: float = SOC_MIN_FRACTION,
    soc_max_fraction: float = SOC_MAX_FRACTION,
    round_trip_eff: float = ROUND_TRIP_EFFICIENCY,
    tol: float = 1e-4,
) -> dict[str, np.ndarray | float | bool]:
    base_load = np.asarray(load, dtype=float)
    if base_load.size == 0:
        return simulate_peak_cap_dispatch(
            load=base_load,
            target_power=0.0,
            battery_power=battery_power,
            battery_energy=battery_energy,
            initial_soc=initial_soc,
            terminal_soc_target=terminal_soc_target,
            step_h=step_h,
            soc_min_fraction=soc_min_fraction,
            soc_max_fraction=soc_max_fraction,
            round_trip_eff=round_trip_eff,
        )

    lower = max(float(base_load.mean()), float(base_load.max() - battery_power), 0.0)
    upper = float(base_load.max())

    best = simulate_peak_cap_dispatch(
        load=base_load,
        target_power=upper,
        battery_power=battery_power,
        battery_energy=battery_energy,
        initial_soc=initial_soc,
        terminal_soc_target=terminal_soc_target,
        step_h=step_h,
        soc_min_fraction=soc_min_fraction,
        soc_max_fraction=soc_max_fraction,
        round_trip_eff=round_trip_eff,
    )

    for _ in range(50):
        if upper - lower <= tol:
            break
        mid = 0.5 * (lower + upper)
        candidate = simulate_peak_cap_dispatch(
            load=base_load,
            target_power=mid,
            battery_power=battery_power,
            battery_energy=battery_energy,
            initial_soc=initial_soc,
            terminal_soc_target=terminal_soc_target,
            step_h=step_h,
            soc_min_fraction=soc_min_fraction,
            soc_max_fraction=soc_max_fraction,
            round_trip_eff=round_trip_eff,
        )
        if bool(candidate["feasible"]):
            upper = mid
            best = candidate
        else:
            lower = mid

    return best


def solve_peak_cap_dispatch_lp(
    load: np.ndarray,
    battery_power: float,
    battery_energy: float,
    initial_soc: float,
    terminal_soc_target: float,
    historical_peak: float,
    step_h: float,
    price: np.ndarray | None = None,
    soc_min_fraction: float = SOC_MIN_FRACTION,
    soc_max_fraction: float = SOC_MAX_FRACTION,
    round_trip_eff: float = ROUND_TRIP_EFFICIENCY,
    peak_tol: float = 1e-5,
    slack_tol: float = 1e-6,
) -> dict[str, np.ndarray | float | bool]:
    base_load = np.asarray(load, dtype=float)
    n = base_load.size
    price_signal: np.ndarray | None = None
    if price is not None:
        candidate_price = np.asarray(price, dtype=float)
        if candidate_price.size == n and not np.isnan(candidate_price).all():
            fill_value = float(np.nanmedian(candidate_price))
            candidate_price = np.where(np.isnan(candidate_price), fill_value, candidate_price)
            price_range = float(candidate_price.max() - candidate_price.min())
            if price_range > 1e-12:
                price_signal = (candidate_price - float(candidate_price.min())) / price_range
            else:
                price_signal = np.zeros(n, dtype=float)

    if n == 0 or battery_power <= 0 or battery_energy <= 0 or step_h <= 0:
        return simulate_peak_cap_dispatch(
            load=base_load,
            target_power=float(historical_peak),
            battery_power=battery_power,
            battery_energy=battery_energy,
            initial_soc=initial_soc,
            terminal_soc_target=terminal_soc_target,
            step_h=step_h,
            soc_min_fraction=soc_min_fraction,
            soc_max_fraction=soc_max_fraction,
            round_trip_eff=round_trip_eff,
        )

    eta = float(np.sqrt(round_trip_eff))
    soc_min = soc_min_fraction * battery_energy
    soc_max = soc_max_fraction * battery_energy
    initial_soc = _clip_soc(
        initial_soc,
        battery_energy,
        soc_min_fraction=soc_min_fraction,
        soc_max_fraction=soc_max_fraction,
    )
    terminal_soc_target = _clip_soc(
        terminal_soc_target,
        battery_energy,
        soc_min_fraction=soc_min_fraction,
        soc_max_fraction=soc_max_fraction,
    )

    idx_m = 0
    idx_c = 1
    idx_d = idx_c + n
    idx_e = idx_d + n
    idx_sp = idx_e + n
    idx_sm = idx_sp + 1
    var_count = idx_sm + 1

    def charge_idx(t: int) -> int:
        return idx_c + t

    def discharge_idx(t: int) -> int:
        return idx_d + t

    def energy_idx(t: int) -> int:
        return idx_e + t

    peak_upper_bound = max(float(base_load.max()), float(historical_peak), 0.0)
    bounds: list[tuple[float | None, float | None]] = [(max(float(historical_peak), 0.0), peak_upper_bound)]
    bounds.extend([(0.0, float(battery_power))] * n)
    bounds.extend([(0.0, float(battery_power))] * n)
    bounds.extend([(float(soc_min), float(soc_max))] * n)
    bounds.extend([(0.0, None), (0.0, None)])

    a_ub_rows: list[np.ndarray] = []
    b_ub_rows: list[float] = []

    for t, load_t in enumerate(base_load):
        peak_row = np.zeros(var_count, dtype=float)
        peak_row[idx_m] = -1.0
        peak_row[charge_idx(t)] = 1.0
        peak_row[discharge_idx(t)] = -1.0
        a_ub_rows.append(peak_row)
        b_ub_rows.append(-float(load_t))

        no_export_row = np.zeros(var_count, dtype=float)
        no_export_row[charge_idx(t)] = -1.0
        no_export_row[discharge_idx(t)] = 1.0
        a_ub_rows.append(no_export_row)
        b_ub_rows.append(float(load_t))

    a_eq_rows: list[np.ndarray] = []
    b_eq_rows: list[float] = []

    for t in range(n):
        dyn_row = np.zeros(var_count, dtype=float)
        dyn_row[charge_idx(t)] = -eta * step_h
        dyn_row[discharge_idx(t)] = step_h / eta
        dyn_row[energy_idx(t)] = 1.0
        if t > 0:
            dyn_row[energy_idx(t - 1)] = -1.0
            rhs = 0.0
        else:
            rhs = float(initial_soc)
        a_eq_rows.append(dyn_row)
        b_eq_rows.append(rhs)

    terminal_row = np.zeros(var_count, dtype=float)
    terminal_row[energy_idx(n - 1)] = 1.0
    terminal_row[idx_sp] = -1.0
    terminal_row[idx_sm] = 1.0
    a_eq_rows.append(terminal_row)
    b_eq_rows.append(float(terminal_soc_target))

    a_ub = np.vstack(a_ub_rows) if a_ub_rows else None
    b_ub = np.asarray(b_ub_rows, dtype=float) if b_ub_rows else None
    a_eq = np.vstack(a_eq_rows)
    b_eq = np.asarray(b_eq_rows, dtype=float)

    def solve_lp(
        objective: np.ndarray,
        extra_a_ub: list[np.ndarray] | None = None,
        extra_b_ub: list[float] | None = None,
    ):
        if extra_a_ub:
            full_a_ub = np.vstack([a_ub, *extra_a_ub]) if a_ub is not None else np.vstack(extra_a_ub)
            full_b_ub = np.concatenate([b_ub, np.asarray(extra_b_ub, dtype=float)]) if b_ub is not None else np.asarray(extra_b_ub, dtype=float)
        else:
            full_a_ub = a_ub
            full_b_ub = b_ub
        return linprog(
            c=objective,
            A_ub=full_a_ub,
            b_ub=full_b_ub,
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )

    stage1_obj = np.zeros(var_count, dtype=float)
    stage1_obj[idx_m] = 1.0
    stage1 = solve_lp(stage1_obj)
    if not stage1.success:
        raise RuntimeError(stage1.message)
    m_star = float(stage1.x[idx_m])

    cap_row = np.zeros(var_count, dtype=float)
    cap_row[idx_m] = 1.0
    stage2_obj = np.zeros(var_count, dtype=float)
    stage2_obj[idx_sp] = 1.0
    stage2_obj[idx_sm] = 1.0
    stage2 = solve_lp(stage2_obj, extra_a_ub=[cap_row], extra_b_ub=[m_star + peak_tol])
    if not stage2.success:
        raise RuntimeError(stage2.message)
    slack_star = float(stage2.x[idx_sp] + stage2.x[idx_sm])

    slack_row = np.zeros(var_count, dtype=float)
    slack_row[idx_sp] = 1.0
    slack_row[idx_sm] = 1.0
    stage3_obj = np.zeros(var_count, dtype=float)
    if price_signal is not None:
        throughput_tiebreaker = 1e-6 * step_h
        stage3_obj[idx_c:idx_d] = price_signal * step_h + throughput_tiebreaker
        stage3_obj[idx_d:idx_e] = -price_signal * step_h + throughput_tiebreaker
    else:
        stage3_obj[idx_c:idx_d] = step_h
        stage3_obj[idx_d:idx_e] = step_h
    stage3 = solve_lp(
        stage3_obj,
        extra_a_ub=[cap_row, slack_row],
        extra_b_ub=[m_star + peak_tol, slack_star + slack_tol],
    )
    if not stage3.success:
        raise RuntimeError(stage3.message)

    solution = stage3.x
    charge_power = solution[idx_c:idx_d]
    discharge_power = solution[idx_d:idx_e]
    soc_trace = solution[idx_e:idx_sp]
    grid_load = base_load + charge_power - discharge_power
    total_charge = float(charge_power.sum() * step_h)
    total_discharge = float(discharge_power.sum() * step_h)
    cycles = float((total_charge + total_discharge) / (2.0 * battery_energy)) if battery_energy > 0 else 0.0

    return {
        "grid_load": grid_load,
        "soc": soc_trace,
        "charge_power": charge_power,
        "discharge_power": discharge_power,
        "net_battery_power": discharge_power - charge_power,
        "total_charge": total_charge,
        "total_discharge": total_discharge,
        "cycles": cycles,
        "final_soc": float(soc_trace[-1]),
        "min_soc": float(soc_trace.min()),
        "max_soc": float(soc_trace.max()),
        "target_power": m_star,
        "terminal_slack": slack_star,
        "price_signal_used": price_signal is not None,
        "feasible": True,
    }


def simulate_bess(
    df: pd.DataFrame,
    step_h: float = 0.5,
    price_col: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy().sort_values(["year", "date", "halfhour_index", "timestamp"]).reset_index(drop=True)
    has_price = bool(price_col and price_col in out.columns)

    for scenario in BESS_SCENARIOS:
        for col in [
            scenario.load_col,
            scenario.soc_col,
            scenario.charge_col,
            scenario.discharge_col,
            scenario.net_power_col,
        ]:
            out[col] = np.nan

    battery_rows: list[dict[str, float | int | str | pd.Timestamp]] = []

    for year, gy in out.groupby("year", sort=True):
        year_peak = float(gy["utilisation"].max())

        day_groups = [(pd.Timestamp(date), day_df.index.to_numpy()) for date, day_df in gy.groupby("date", sort=True)]
        index_by_date = {date: idx for date, idx in day_groups}
        dates = [date for date, _ in day_groups]

        for scenario in BESS_SCENARIOS:
            battery_power = scenario.battery_power_fraction * year_peak
            battery_energy = battery_power * scenario.duration_hours
            current_soc = 0.5 * battery_energy
            historical_peak = 0.0
            horizon_days = get_bess_horizon_days(scenario)
            planned_horizon_hours = int(round(horizon_days * 24.0))

            for day_pos, date in enumerate(dates):
                exec_idx = index_by_date[date]
                horizon_dates = dates[day_pos : day_pos + horizon_days]
                horizon_idx = np.concatenate([index_by_date[d] for d in horizon_dates])

                horizon_load = out.loc[horizon_idx, scenario.flex_col].to_numpy(dtype=float)
                horizon_price = out.loc[horizon_idx, price_col].to_numpy(dtype=float) if has_price else None
                controller_method = (
                    f"rolling_{planned_horizon_hours}h_peak_cap_price_lp"
                    if has_price
                    else f"rolling_{planned_horizon_hours}h_peak_cap_lp"
                )
                used_fallback = False
                terminal_slack = 0.0
                historical_peak_before_dispatch = float(historical_peak)
                terminal_soc_target = (
                    scenario.terminal_soc_fraction * battery_energy
                    if scenario.terminal_soc_fraction is not None
                    else current_soc
                )
                try:
                    dispatch = solve_peak_cap_dispatch_lp(
                        load=horizon_load,
                        battery_power=battery_power,
                        battery_energy=battery_energy,
                        initial_soc=current_soc,
                        terminal_soc_target=terminal_soc_target,
                        historical_peak=historical_peak,
                        step_h=step_h,
                        price=horizon_price,
                        soc_min_fraction=scenario.soc_min_fraction,
                        soc_max_fraction=scenario.soc_max_fraction,
                    )
                    terminal_slack = float(dispatch.get("terminal_slack", 0.0))
                except RuntimeError:
                    target_guess = max(float(historical_peak_before_dispatch), float(np.max(horizon_load)))
                    dispatch = simulate_peak_cap_dispatch(
                        load=horizon_load,
                        target_power=target_guess,
                        battery_power=battery_power,
                        battery_energy=battery_energy,
                        initial_soc=current_soc,
                        terminal_soc_target=terminal_soc_target,
                        step_h=step_h,
                        soc_min_fraction=scenario.soc_min_fraction,
                        soc_max_fraction=scenario.soc_max_fraction,
                    )
                    controller_method = (
                        f"rolling_{planned_horizon_hours}h_peak_cap_price_fallback"
                        if has_price
                        else f"rolling_{planned_horizon_hours}h_peak_cap_fallback"
                    )
                    used_fallback = True

                n_exec = len(exec_idx)
                exec_load = np.asarray(dispatch["grid_load"], dtype=float)[:n_exec]
                exec_soc = np.asarray(dispatch["soc"], dtype=float)[:n_exec]
                exec_charge = np.asarray(dispatch["charge_power"], dtype=float)[:n_exec]
                exec_discharge = np.asarray(dispatch["discharge_power"], dtype=float)[:n_exec]
                exec_net_power = np.asarray(dispatch["net_battery_power"], dtype=float)[:n_exec]
                exec_price = np.asarray(horizon_price, dtype=float)[:n_exec] if horizon_price is not None else None

                out.loc[exec_idx, scenario.load_col] = exec_load
                out.loc[exec_idx, scenario.soc_col] = exec_soc
                out.loc[exec_idx, scenario.charge_col] = exec_charge
                out.loc[exec_idx, scenario.discharge_col] = exec_discharge
                out.loc[exec_idx, scenario.net_power_col] = exec_net_power

                total_charge = float(exec_charge.sum() * step_h)
                total_discharge = float(exec_discharge.sum() * step_h)
                energy_cost_proxy = (
                    float(np.sum(exec_load * exec_price * step_h)) if exec_price is not None else np.nan
                )
                peak_pre_bess = float(out.loc[exec_idx, scenario.flex_col].max())
                peak_post_bess = float(exec_load.max()) if exec_load.size else peak_pre_bess
                final_soc = float(exec_soc[-1]) if exec_soc.size else float(current_soc)
                historical_peak = max(historical_peak, peak_post_bess)

                battery_rows.append(
                    {
                        "year": int(year),
                        "date": date,
                        "scenario": scenario.scenario,
                        "battery_duration": scenario.battery_duration,
                        "controller_method": controller_method,
                        "used_fallback": bool(used_fallback),
                        "dispatch_horizon_days": int(len(horizon_dates)),
                        "dispatch_horizon_hours": float(len(horizon_load) * step_h),
                        "battery_power": battery_power,
                        "battery_energy": battery_energy,
                        "historical_peak_before_dispatch": historical_peak_before_dispatch,
                        "initial_soc": float(current_soc),
                        "terminal_soc_target": float(terminal_soc_target),
                        "final_soc": final_soc,
                        "min_soc": float(exec_soc.min()) if exec_soc.size else float(current_soc),
                        "max_soc": float(exec_soc.max()) if exec_soc.size else float(current_soc),
                        "target_grid_power": float(dispatch["target_power"]),
                        "terminal_soc_slack": terminal_slack,
                        "price_signal_used": bool(dispatch.get("price_signal_used", False)),
                        "mean_price": float(np.mean(exec_price)) if exec_price is not None else np.nan,
                        "energy_cost_proxy": energy_cost_proxy,
                        "total_charge": total_charge,
                        "total_discharge": total_discharge,
                        "cycles": float((total_charge + total_discharge) / (2.0 * battery_energy)) if battery_energy > 0 else 0.0,
                        "charge_steps": int(np.sum(exec_charge > 1e-10)),
                        "discharge_steps": int(np.sum(exec_discharge > 1e-10)),
                        "peak_pre_bess": peak_pre_bess,
                        "peak_post_bess": peak_post_bess,
                        "peak_reduction_vs_flex_percent": (
                            (peak_pre_bess - peak_post_bess) / peak_pre_bess * 100.0 if peak_pre_bess > 0 else 0.0
                        ),
                    }
                )

                current_soc = final_soc

    return out, pd.DataFrame(battery_rows)
