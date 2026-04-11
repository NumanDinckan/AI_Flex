from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from rq1_figure0 import run_rq1
from rq2_figure1 import run_rq2
from rq3_figure2 import run_rq3


REQUIRED_COLUMNS = [
    "cleansed_voltage_level",
    "anonymised_data_centre_name",
    "dc_type",
    "utc_timestamp",
    "hh_utilisation_ratio",
]


@dataclass
class CoreAnalysisResults:
    battery_daily_stats: pd.DataFrame
    flex_daily_stats: pd.DataFrame
    timeseries: pd.DataFrame
    characteristic_days: dict[int, pd.Timestamp]


@dataclass
class ReportContext:
    year: int
    min_utilisation: float
    dt_hours: float
    output_dir: Path
    characteristic_day: pd.Timestamp
    day_df: pd.DataFrame
    year_df: pd.DataFrame
    centres_year_df: pd.DataFrame | None
    flex_daily_stats: pd.DataFrame
    battery_daily_stats: pd.DataFrame


@dataclass(frozen=True)
class FlexScenario:
    key: str
    name: str
    flex_share: float
    recovery_window_hours: float
    framing: str
    exploratory: bool = False


FLEX_EVENT_START_HOUR = 14.0
FLEX_EVENT_END_HOUR = 22.0

FLEX_SCENARIOS: tuple[FlexScenario, ...] = (
    FlexScenario(
        key="10",
        name="Conservative Flex 10%",
        flex_share=0.10,
        recovery_window_hours=6.0,
        framing="Conservative peer-reviewed case",
    ),
    FlexScenario(
        key="25",
        name="Exploratory Flex 25%",
        flex_share=0.25,
        recovery_window_hours=12.0,
        framing="Exploratory upper-bound case",
        exploratory=True,
    ),
)


def add_common_report_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--input", type=str, default="data/raw/ukpn-data-centre-demand-profiles.csv")
    parser.add_argument("--output-dir", type=str, default=".")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dt-hours", type=float, default=0.5)
    parser.add_argument("--dc-type", type=str, default="")
    parser.add_argument("--voltage-level", type=str, default="High Voltage Import")
    parser.add_argument("--centres", type=str, default="")
    parser.add_argument(
        "--min-utilisation",
        type=float,
        default=0.1,
        help="Keep only rows with hh_utilisation_ratio strictly greater than this threshold.",
    )
    parser.add_argument("--chunksize", type=int, default=750_000)
    return parser


def detect_delimiter(csv_path: Path) -> str:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
    return ";" if first_line.count(";") > first_line.count(",") else ","


def parse_centre_list(raw: str) -> set[str] | None:
    if not raw:
        return None
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return values or None


def load_aggregated_timeseries(
    csv_path: Path,
    dc_type: str | None,
    voltage_level: str | None,
    centres: set[str] | None,
    min_utilisation: float,
    chunksize: int,
) -> pd.DataFrame:
    delimiter = detect_delimiter(csv_path)

    sum_by_ts = pd.Series(dtype="float64")
    count_by_ts = pd.Series(dtype="float64")

    reader = pd.read_csv(
        csv_path,
        usecols=REQUIRED_COLUMNS,
        delimiter=delimiter,
        encoding="utf-8-sig",
        chunksize=chunksize,
        dtype={
            "cleansed_voltage_level": "string",
            "anonymised_data_centre_name": "string",
            "dc_type": "string",
            "utc_timestamp": "string",
            "hh_utilisation_ratio": "float64",
        },
    )

    for chunk in reader:
        if dc_type:
            chunk = chunk[chunk["dc_type"] == dc_type]
        if voltage_level:
            chunk = chunk[chunk["cleansed_voltage_level"] == voltage_level]
        if centres:
            chunk = chunk[chunk["anonymised_data_centre_name"].isin(centres)]
        if chunk.empty:
            continue

        chunk["utc_timestamp"] = pd.to_datetime(chunk["utc_timestamp"], errors="coerce")
        chunk["hh_utilisation_ratio"] = pd.to_numeric(chunk["hh_utilisation_ratio"], errors="coerce")
        chunk = chunk.dropna(subset=["utc_timestamp", "hh_utilisation_ratio"])
        chunk = chunk[chunk["hh_utilisation_ratio"] > min_utilisation]
        if chunk.empty:
            continue

        grouped = chunk.groupby("utc_timestamp", sort=False)["hh_utilisation_ratio"].agg(["sum", "count"])
        sum_by_ts = sum_by_ts.add(grouped["sum"], fill_value=0.0)
        count_by_ts = count_by_ts.add(grouped["count"], fill_value=0.0)

    if count_by_ts.empty:
        raise ValueError("No valid rows found after filtering.")

    utilisation = (sum_by_ts / count_by_ts).sort_index()
    return utilisation.rename("utilisation").rename_axis("timestamp").reset_index()


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("timestamp").copy()
    out["date"] = out["timestamp"].dt.floor("D")
    out["year"] = out["timestamp"].dt.year.astype(int)
    out["month"] = out["timestamp"].dt.month.astype(int)
    out["weekday"] = out["timestamp"].dt.weekday.astype(int)
    out["halfhour_index"] = (out["timestamp"].dt.hour * 2 + (out["timestamp"].dt.minute // 30)).astype(int)
    return out


def add_baselines(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    med_base = (
        out.groupby(["year", "weekday", "halfhour_index"], observed=True)["utilisation"]
        .median()
        .rename("med_base")
    )
    out = out.join(med_base, on=["year", "weekday", "halfhour_index"])

    med_base_sens = (
        out.groupby(["year", "month", "weekday", "halfhour_index"], observed=True)["utilisation"]
        .median()
        .rename("med_base_sensitivity")
    )
    out = out.join(med_base_sens, on=["year", "month", "weekday", "halfhour_index"])

    return out


def is_event_eligible(timestamp: pd.Timestamp) -> bool:
    hour = timestamp.hour + timestamp.minute / 60.0
    return timestamp.weekday() < 5 and FLEX_EVENT_START_HOUR <= hour < FLEX_EVENT_END_HOUR


def apply_shiftable_flex_for_scenario(
    year_df: pd.DataFrame,
    dt_hours: float,
    scenario: FlexScenario,
) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    if dt_hours <= 0:
        raise ValueError("dt_hours must be positive.")

    work = year_df.sort_values("timestamp").reset_index()
    base_load = work["utilisation"].to_numpy(dtype=float)
    med_base = work["med_base"].to_numpy(dtype=float)
    n = len(work)

    load_total = base_load.copy()
    load_inflex = (1.0 - scenario.flex_share) * base_load
    load_flex_orig = scenario.flex_share * base_load
    load_flex_shifted = load_flex_orig.copy()
    shift_down = np.zeros(n, dtype=float)
    shift_up = np.zeros(n, dtype=float)
    event_selected = np.zeros(n, dtype=float)

    recovery_steps = max(1, int(round(scenario.recovery_window_hours / dt_hours)))
    daily_rows: list[dict[str, object]] = []

    for date, day_frame in work.groupby(work["timestamp"].dt.floor("D"), sort=True):
        day_idx = day_frame.index.to_numpy(dtype=int)
        event_candidates = [
            i
            for i in day_idx
            if is_event_eligible(pd.Timestamp(work.loc[i, "timestamp"])) and base_load[i] > med_base[i] + 1e-12
        ]
        available_shift = np.maximum(0.0, np.minimum(load_flex_orig, base_load - med_base))
        selected = np.asarray(
            sorted(
                event_candidates,
                key=lambda i: (base_load[i] - med_base[i], base_load[i], i),
                reverse=True,
            ),
            dtype=int,
        )
        shiftable_target = float(available_shift[selected].sum()) if selected.size else 0.0
        realized = 0.0
        delay_weighted_sum = 0.0
        saturated_recovery_slots: set[int] = set()
        no_recovery_slots = 0

        for peak_idx in selected:
            amount = float(available_shift[peak_idx])
            remaining = amount
            if remaining <= 1e-12:
                continue

            recovery_candidates = []
            for rec_idx in day_idx:
                if rec_idx == peak_idx:
                    continue
                rec_ts = pd.Timestamp(work.loc[rec_idx, "timestamp"])
                if is_event_eligible(rec_ts):
                    continue
                if abs(rec_idx - peak_idx) > recovery_steps:
                    continue
                recovery_candidates.append(rec_idx)

            recovery_candidates.sort(
                key=lambda i: (
                    base_load[i],
                    abs(i - peak_idx),
                    i,
                )
            )
            peak_realized = 0.0
            for rec_idx in recovery_candidates:
                if remaining <= 1e-12:
                    break
                median_gap_allowance = max(0.0, med_base[peak_idx] - med_base[rec_idx])
                recovery_upper = min(
                    base_load[rec_idx] + median_gap_allowance,
                    (1.0 + scenario.flex_share) * base_load[rec_idx],
                    1.0,
                )
                capacity = max(0.0, recovery_upper - load_total[rec_idx])
                if capacity <= 1e-12:
                    continue

                delta = min(remaining, capacity)
                load_total[peak_idx] -= delta
                load_total[rec_idx] += delta
                load_flex_shifted[peak_idx] -= delta
                load_flex_shifted[rec_idx] += delta
                shift_down[peak_idx] += delta
                shift_up[rec_idx] += delta
                remaining -= delta
                peak_realized += delta
                realized += delta
                delay_weighted_sum += delta * ((rec_idx - peak_idx) * dt_hours)
                if load_total[rec_idx] >= recovery_upper - 1e-10:
                    saturated_recovery_slots.add(int(rec_idx))

            if peak_realized <= 1e-12:
                no_recovery_slots += 1

        if selected.size:
            active_selected = selected[shift_down[selected] > 1e-12]
            event_selected[active_selected] = 1.0

        unmet = max(0.0, shiftable_target - realized)
        daily_rows.append(
            {
                "year": int(day_frame["year"].iloc[0]),
                "date": pd.Timestamp(date),
                "scenario_key": scenario.key,
                "scenario_name": scenario.name,
                "framing": scenario.framing,
                "exploratory": scenario.exploratory,
                "flex_share": float(scenario.flex_share),
                "recovery_window_hours": float(scenario.recovery_window_hours),
                "event_candidate_steps": int(len(selected)),
                "active_shift_steps": int(np.sum(shift_down[day_idx] > 1e-12)),
                "shiftable_target": float(shiftable_target),
                "shiftable_realized": float(realized),
                "shiftable_unmet": float(unmet),
                "shifted_energy_utilisation_hours": float(realized * dt_hours),
                "feasible_day": bool(unmet <= 1e-10),
                "recovery_saturation_slots": int(len(saturated_recovery_slots)),
                "average_deferment_hours": float(delay_weighted_sum / realized) if realized > 1e-12 else 0.0,
                "used_eligible_flex_percent": float(realized / shiftable_target * 100.0) if shiftable_target > 1e-12 else 0.0,
                "fully_recovered_percent": float(realized / shiftable_target * 100.0) if shiftable_target > 1e-12 else 0.0,
                "no_recovery_slots": int(no_recovery_slots),
                "active_event_day": bool(len(selected) > 0),
            }
        )

    return (
        {
            "load_total": np.clip(load_total, 0.0, 1.0),
            "load_inflex": load_inflex,
            "load_flex_orig": load_flex_orig,
            "load_flex_shifted": load_flex_shifted,
            "shift_down": shift_down,
            "shift_up": shift_up,
            "event_selected": event_selected,
            "row_index": work["index"].to_numpy(dtype=int),
        },
        pd.DataFrame(daily_rows),
    )


def add_flex(df: pd.DataFrame, dt_hours: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy().sort_values(["year", "date", "halfhour_index", "timestamp"]).reset_index(drop=True)

    out["surplus"] = np.maximum(0.0, out["utilisation"] - out["med_base"])
    out["undersupply"] = np.maximum(0.0, out["med_base"] - out["utilisation"])

    for suffix in ["10", "25"]:
        for col in [
            f"load_inflex_{suffix}",
            f"load_flex_orig_{suffix}",
            f"load_flex_shifted_{suffix}",
            f"reduce_frac_{suffix}",
            f"valley_shiftable_{suffix}",
            f"shift_down_{suffix}",
            f"shift_up_{suffix}",
            f"shiftable_{suffix}_target",
            f"shiftable_{suffix}_realized",
            f"shiftable_{suffix}_unmet",
            f"load_flex_{suffix}",
            f"event_selected_{suffix}",
        ]:
            out[col] = 0.0

    flex_daily_stats_parts: list[pd.DataFrame] = []

    for _, year_df in out.groupby("year", sort=True):
        for scenario in FLEX_SCENARIOS:
            scenario_out, daily_stats = apply_shiftable_flex_for_scenario(year_df, dt_hours=dt_hours, scenario=scenario)
            row_index = scenario_out["row_index"]
            suffix = scenario.key
            out.loc[row_index, f"load_inflex_{suffix}"] = scenario_out["load_inflex"]
            out.loc[row_index, f"load_flex_orig_{suffix}"] = scenario_out["load_flex_orig"]
            out.loc[row_index, f"load_flex_shifted_{suffix}"] = scenario_out["load_flex_shifted"]
            out.loc[row_index, f"reduce_frac_{suffix}"] = scenario_out["shift_down"]
            out.loc[row_index, f"valley_shiftable_{suffix}"] = scenario_out["shift_up"]
            out.loc[row_index, f"shift_down_{suffix}"] = scenario_out["shift_down"]
            out.loc[row_index, f"shift_up_{suffix}"] = scenario_out["shift_up"]
            out.loc[row_index, f"load_flex_{suffix}"] = scenario_out["load_total"]
            out.loc[row_index, f"event_selected_{suffix}"] = scenario_out["event_selected"]

            day_metric_map = daily_stats.set_index("date") if not daily_stats.empty else pd.DataFrame()
            if not daily_stats.empty:
                out.loc[row_index, f"shiftable_{suffix}_target"] = out.loc[row_index, "date"].map(day_metric_map["shiftable_target"])
                out.loc[row_index, f"shiftable_{suffix}_realized"] = out.loc[row_index, "date"].map(day_metric_map["shiftable_realized"])
                out.loc[row_index, f"shiftable_{suffix}_unmet"] = out.loc[row_index, "date"].map(day_metric_map["shiftable_unmet"])
                flex_daily_stats_parts.append(daily_stats)

    rolling_window_steps = max(1, int(round(4.0 / dt_hours)))
    out["down_10_4h"] = (
        out.groupby(["year", "date"])["reduce_frac_10"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["down_25_4h"] = (
        out.groupby(["year", "date"])["reduce_frac_25"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["up_10_4h"] = (
        out.groupby(["year", "date"])["valley_shiftable_10"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["up_25_4h"] = (
        out.groupby(["year", "date"])["valley_shiftable_25"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )

    flex_daily_stats = pd.concat(flex_daily_stats_parts, ignore_index=True) if flex_daily_stats_parts else pd.DataFrame()
    return out, flex_daily_stats


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
            p = min(
                battery_power,
                max_discharge_power_step,
                response_factor * dynamic_excess,
            )
            if p > 0:
                current_soc -= p * step_h / round_trip_eff
                l -= p
                discharge_p[i] = p

        elif is_valley_region and current_soc < 0.9 * battery_energy and l <= charge_th:
            available_capacity_step = max(0.9 * battery_energy - current_soc, 0.0) * 0.9
            max_charge_power_step = available_capacity_step / step_h
            dynamic_gap = max(0.0, charge_th - l)
            p = min(
                battery_power,
                max_charge_power_step,
                response_factor * dynamic_gap,
            )
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


def find_characteristic_days(df: pd.DataFrame) -> dict[int, pd.Timestamp]:
    daily_peaks = (
        df.groupby(["year", "date"], as_index=False)["utilisation"].max().rename(columns={"utilisation": "day_peak"})
    )

    characteristic: dict[int, pd.Timestamp] = {}
    for year, g in daily_peaks.groupby("year", sort=True):
        idx = g["day_peak"].idxmax()
        characteristic[int(year)] = pd.Timestamp(g.loc[idx, "date"])

    return characteristic


def run_core_analysis(df: pd.DataFrame, dt_hours: float) -> CoreAnalysisResults:
    ts = prepare_features(df)
    ts = add_baselines(ts)
    ts, flex_daily_stats = add_flex(ts, dt_hours=dt_hours)
    ts, battery_daily_stats = simulate_bess(ts)
    characteristic_days = find_characteristic_days(ts)

    return CoreAnalysisResults(
        battery_daily_stats=battery_daily_stats,
        flex_daily_stats=flex_daily_stats,
        timeseries=ts,
        characteristic_days=characteristic_days,
    )


def load_centre_year_timeseries(
    csv_path: Path,
    year: int,
    target_date: pd.Timestamp | None,
    dc_type: str | None,
    voltage_level: str | None,
    min_utilisation: float,
    chunksize: int,
) -> pd.DataFrame:
    delimiter = detect_delimiter(csv_path)
    parts: list[pd.DataFrame] = []

    reader = pd.read_csv(
        csv_path,
        usecols=REQUIRED_COLUMNS,
        delimiter=delimiter,
        encoding="utf-8-sig",
        chunksize=chunksize,
        dtype={
            "cleansed_voltage_level": "string",
            "anonymised_data_centre_name": "string",
            "dc_type": "string",
            "utc_timestamp": "string",
            "hh_utilisation_ratio": "float64",
        },
    )

    for chunk in reader:
        if dc_type:
            chunk = chunk[chunk["dc_type"] == dc_type]
        if voltage_level:
            chunk = chunk[chunk["cleansed_voltage_level"] == voltage_level]
        if chunk.empty:
            continue

        chunk["timestamp"] = pd.to_datetime(chunk["utc_timestamp"], errors="coerce")
        chunk["utilisation"] = pd.to_numeric(chunk["hh_utilisation_ratio"], errors="coerce")
        chunk = chunk.dropna(subset=["timestamp", "utilisation", "anonymised_data_centre_name"])
        chunk = chunk[chunk["utilisation"] > min_utilisation]
        if chunk.empty:
            continue

        chunk = chunk[chunk["timestamp"].dt.year == year]
        if chunk.empty:
            continue
        if target_date is not None:
            chunk = chunk[chunk["timestamp"].dt.floor("D") == pd.Timestamp(target_date)]
            if chunk.empty:
                continue

        out = chunk.loc[:, ["timestamp", "anonymised_data_centre_name", "utilisation"]].copy()
        out = out.rename(columns={"anonymised_data_centre_name": "centre"})
        out["halfhour_index"] = (out["timestamp"].dt.hour * 2 + (out["timestamp"].dt.minute // 30)).astype(int)
        parts.append(out)

    if not parts:
        raise ValueError(f"No centre-level rows found for year {year} after filtering.")

    return pd.concat(parts, ignore_index=True)


def build_context(args: argparse.Namespace, include_rq1_data: bool) -> ReportContext:
    if args.dt_hours <= 0:
        raise ValueError("--dt-hours must be positive.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_csv = Path(args.input)
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = load_aggregated_timeseries(
        csv_path=input_csv,
        dc_type=args.dc_type.strip() if args.dc_type else None,
        voltage_level=args.voltage_level.strip() if args.voltage_level else None,
        centres=parse_centre_list(args.centres),
        min_utilisation=args.min_utilisation,
        chunksize=args.chunksize,
    )

    results = run_core_analysis(df, dt_hours=args.dt_hours)

    if args.year not in results.characteristic_days:
        available = sorted(results.characteristic_days.keys())
        raise ValueError(f"Requested year {args.year} not available. Available years: {available}")

    characteristic_day = results.characteristic_days[args.year]

    day_df = results.timeseries[
        (results.timeseries["year"] == args.year) & (results.timeseries["date"] == characteristic_day)
    ].sort_values("halfhour_index")
    year_df = results.timeseries[results.timeseries["year"] == args.year].sort_values("timestamp").copy()
    flex_daily_stats = results.flex_daily_stats[results.flex_daily_stats["year"] == args.year].copy()

    if day_df.empty:
        raise ValueError(f"No characteristic-day data found for year {args.year}.")

    centres_year_df: pd.DataFrame | None = None
    if include_rq1_data:
        centres_year_df = load_centre_year_timeseries(
            csv_path=input_csv,
            year=args.year,
            target_date=None,
            dc_type=args.dc_type.strip() if args.dc_type else None,
            voltage_level=args.voltage_level.strip() if args.voltage_level else None,
            min_utilisation=args.min_utilisation,
            chunksize=args.chunksize,
        )

    return ReportContext(
        year=args.year,
        min_utilisation=args.min_utilisation,
        dt_hours=args.dt_hours,
        output_dir=output_dir,
        characteristic_day=characteristic_day,
        day_df=day_df,
        year_df=year_df,
        centres_year_df=centres_year_df,
        flex_daily_stats=flex_daily_stats,
        battery_daily_stats=results.battery_daily_stats,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run intermediate report outputs for RQ1/RQ2/RQ3.")
    add_common_report_args(parser)
    parser.add_argument(
        "--rq",
        choices=["all", "rq1", "rq2", "rq3"],
        default="all",
        help="Select which research-question output set to generate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_rq1_data = args.rq in {"all", "rq1"}
    context = build_context(args, include_rq1_data=include_rq1_data)

    saved_files: list[str] = []

    if args.rq in {"all", "rq1"}:
        if context.centres_year_df is None:
            raise ValueError("RQ1 selected but centre-level year data is unavailable.")
        rq1_files = run_rq1(
            centres_year_df=context.centres_year_df,
            year=context.year,
            characteristic_day=context.characteristic_day,
            output_dir=context.output_dir,
        )
        saved_files.extend([str(p.resolve()) for p in rq1_files])

    if args.rq in {"all", "rq2"}:
        fig, table = run_rq2(
            day_df=context.day_df,
            year_df=context.year_df,
            flex_daily_stats=context.flex_daily_stats,
            year=context.year,
            output_dir=context.output_dir,
        )
        saved_files.extend([str(fig.resolve()), str(table.resolve())])

    if args.rq in {"all", "rq3"}:
        fig10, fig25, table = run_rq3(
            day_df=context.day_df,
            battery_daily_stats=context.battery_daily_stats,
            year=context.year,
            output_dir=context.output_dir,
        )
        saved_files.extend([str(fig10.resolve()), str(fig25.resolve()), str(table.resolve())])

    print(f"RQ selection: {args.rq}")
    print(f"Year selected: {context.year}")
    print(f"Characteristic day: {context.characteristic_day.date()}")
    print(f"Min utilisation filter: > {context.min_utilisation}")
    print(f"dt_hours: {context.dt_hours}")
    for path in saved_files:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
