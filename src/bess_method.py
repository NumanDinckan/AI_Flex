from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_bess_day(
    base_load: np.ndarray,
    med_base: np.ndarray,
    halfhour_index: np.ndarray,
    battery_power: float,
    battery_energy: float,
    response_factor: float = 0.25,
    round_trip_eff: float = 0.90,
    step_h: float = 0.5,
) -> dict[str, np.ndarray | float | list[int]]:
    load = base_load.copy().astype(float)
    n = load.size

    soc = np.zeros(n, dtype=float)
    charge_p = np.zeros(n, dtype=float)
    discharge_p = np.zeros(n, dtype=float)

    if battery_power <= 0 or battery_energy <= 0 or n == 0:
        return {
            "load": load,
            "soc": soc,
            "total_charge": 0.0,
            "total_discharge": 0.0,
            "cycles": 0.0,
            "max_soc": 0.0,
            "mean_soc": 0.0,
            "discharge_threshold": 0.0,
            "charge_threshold": 0.0,
            "dynamic_peak_region": [],
            "dynamic_valley_region": [],
            "response_factor": float(response_factor),
        }

    day_median = float(np.median(load))
    day_std = float(np.std(load, ddof=0))
    discharge_th = day_median + 0.15 * day_std
    charge_th = day_median - 0.15 * day_std

    k = max(1, int(np.ceil(0.20 * n)))
    hh = halfhour_index.astype(int)

    order = np.argsort(hh)
    hh_sorted = hh[order]
    load_sorted = load[order]

    def choose_connected_region(values: np.ndarray, hh_idx: np.ndarray, width: int, pick_peak: bool) -> np.ndarray:
        best: np.ndarray | None = None
        best_score = -np.inf if pick_peak else np.inf

        if values.size >= width:
            for start in range(0, values.size - width + 1):
                block_hh = hh_idx[start : start + width]
                if not np.all(np.diff(block_hh) == 1):
                    continue
                block_vals = values[start : start + width]
                score = float(block_vals.sum())
                if (pick_peak and score > best_score) or ((not pick_peak) and score < best_score):
                    best_score = score
                    best = block_hh

        if best is not None:
            return np.asarray(best, dtype=int)

        if pick_peak:
            pick_idx = np.argsort(values)[-width:]
        else:
            pick_idx = np.argsort(values)[:width]
        return np.sort(hh_idx[pick_idx].astype(int))

    peak_region_hh = choose_connected_region(load_sorted, hh_sorted, k, pick_peak=True)
    valley_region_hh = choose_connected_region(load_sorted, hh_sorted, k, pick_peak=False)

    peak_region_set = set(int(v) for v in peak_region_hh.tolist())
    valley_region_set = set(int(v) for v in valley_region_hh.tolist())

    current_soc = 0.5 * battery_energy

    for i in range(n):
        l = float(load[i])
        hh_val = int(halfhour_index[i])
        _ = med_base[i]

        is_peak_region = hh_val in peak_region_set
        is_valley_region = hh_val in valley_region_set

        if is_peak_region and current_soc > 0.1 * battery_energy and l >= discharge_th:
            available_energy_step = max(current_soc - 0.1 * battery_energy, 0.0) * 0.9
            max_discharge_power_step = available_energy_step / step_h
            dynamic_excess = max(0.0, l - discharge_th)
            p = min(battery_power, max_discharge_power_step, response_factor * dynamic_excess)
            if p > 0:
                current_soc -= p * step_h / round_trip_eff
                l -= p
                discharge_p[i] = p

        elif is_valley_region and current_soc < 0.9 * battery_energy and l <= charge_th:
            available_capacity_step = max(0.9 * battery_energy - current_soc, 0.0) * 0.9
            max_charge_power_step = available_capacity_step / step_h
            dynamic_gap = max(0.0, charge_th - l)
            p = min(battery_power, max_charge_power_step, response_factor * dynamic_gap)
            if p > 0:
                current_soc += p * step_h * round_trip_eff
                l += p
                charge_p[i] = p

        current_soc = min(max(current_soc, 0.0), battery_energy)
        load[i] = min(max(l, 0.0), 1.0)
        soc[i] = current_soc

    total_charge = float(np.sum(charge_p) * step_h)
    total_discharge = float(np.sum(discharge_p) * step_h)
    cycles = float((total_charge + total_discharge) / (2.0 * battery_energy)) if battery_energy > 0 else 0.0

    return {
        "load": load,
        "soc": soc,
        "total_charge": total_charge,
        "total_discharge": total_discharge,
        "cycles": cycles,
        "max_soc": float(np.max(soc)),
        "mean_soc": float(np.mean(soc)),
        "discharge_threshold": float(discharge_th),
        "charge_threshold": float(charge_th),
        "dynamic_peak_region": peak_region_hh.tolist(),
        "dynamic_valley_region": valley_region_hh.tolist(),
        "response_factor": float(response_factor),
    }


def simulate_bess(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy().sort_values(["year", "date", "halfhour_index", "timestamp"]).reset_index(drop=True)

    for col in [
        "load_10_flex_4h_batt",
        "load_10_flex_8h_batt",
        "load_25_flex_4h_batt",
        "load_25_flex_8h_batt",
        "soc_10_flex_4h_batt",
        "soc_10_flex_8h_batt",
        "soc_25_flex_4h_batt",
        "soc_25_flex_8h_batt",
    ]:
        out[col] = np.nan

    battery_rows: list[dict[str, float | int | str | pd.Timestamp]] = []

    for year, gy in out.groupby("year", sort=True):
        year_peak = float(gy["utilisation"].max())
        battery_power = 0.25 * year_peak
        battery_energy_4h = battery_power * 4.0
        battery_energy_8h = battery_power * 8.0
        base_energy = max(battery_power * 4.0, 1e-12)
        response_4h = 0.25 * (battery_energy_4h / base_energy)
        response_8h = 0.25 * (battery_energy_8h / base_energy)

        for day, gd in gy.groupby("date", sort=True):
            idx = gd.index.to_numpy()
            base = gd["med_base"].to_numpy(dtype=float)
            hh = gd["halfhour_index"].to_numpy(dtype=int)

            l10 = gd["load_flex_10"].to_numpy(dtype=float)
            l25 = gd["load_flex_25"].to_numpy(dtype=float)

            s10_4 = simulate_bess_day(l10, base, hh, battery_power, battery_energy_4h, response_factor=response_4h)
            s10_8 = simulate_bess_day(l10, base, hh, battery_power, battery_energy_8h, response_factor=response_8h)
            s25_4 = simulate_bess_day(l25, base, hh, battery_power, battery_energy_4h, response_factor=response_4h)
            s25_8 = simulate_bess_day(l25, base, hh, battery_power, battery_energy_8h, response_factor=response_8h)

            out.loc[idx, "load_10_flex_4h_batt"] = np.asarray(s10_4["load"], dtype=float)
            out.loc[idx, "load_10_flex_8h_batt"] = np.asarray(s10_8["load"], dtype=float)
            out.loc[idx, "load_25_flex_4h_batt"] = np.asarray(s25_4["load"], dtype=float)
            out.loc[idx, "load_25_flex_8h_batt"] = np.asarray(s25_8["load"], dtype=float)

            out.loc[idx, "soc_10_flex_4h_batt"] = np.asarray(s10_4["soc"], dtype=float)
            out.loc[idx, "soc_10_flex_8h_batt"] = np.asarray(s10_8["soc"], dtype=float)
            out.loc[idx, "soc_25_flex_4h_batt"] = np.asarray(s25_4["soc"], dtype=float)
            out.loc[idx, "soc_25_flex_8h_batt"] = np.asarray(s25_8["soc"], dtype=float)

            scenario_rows = [
                ("10%_flex + 4h-Battery", "4h", battery_energy_4h, s10_4),
                ("10%_flex + 8h-Battery", "8h", battery_energy_8h, s10_8),
                ("25%_flex + 4h-Battery", "4h", battery_energy_4h, s25_4),
                ("25%_flex + 8h-Battery", "8h", battery_energy_8h, s25_8),
            ]

            for scenario, duration, energy, res in scenario_rows:
                battery_rows.append(
                    {
                        "year": int(year),
                        "date": day,
                        "scenario": scenario,
                        "battery_duration": duration,
                        "battery_power": battery_power,
                        "battery_energy": energy,
                        "total_charge": float(res["total_charge"]),
                        "total_discharge": float(res["total_discharge"]),
                        "cycles": float(res["cycles"]),
                        "max_soc": float(res["max_soc"]),
                        "mean_soc": float(res["mean_soc"]),
                        "discharge_threshold": float(res["discharge_threshold"]),
                        "charge_threshold": float(res["charge_threshold"]),
                        "dynamic_peak_region": ",".join(str(int(v)) for v in list(res["dynamic_peak_region"])),
                        "dynamic_valley_region": ",".join(str(int(v)) for v in list(res["dynamic_valley_region"])),
                        "response_factor": float(res["response_factor"]),
                    }
                )

    return out, pd.DataFrame(battery_rows)
