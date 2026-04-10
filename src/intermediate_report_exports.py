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
    timeseries: pd.DataFrame
    characteristic_days: dict[int, pd.Timestamp]


@dataclass
class ReportContext:
    year: int
    min_utilisation: float
    output_dir: Path
    characteristic_day: pd.Timestamp
    day_df: pd.DataFrame
    centres_year_df: pd.DataFrame | None
    battery_daily_stats: pd.DataFrame


def add_common_report_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--input", type=str, default="data/raw/ukpn-data-centre-demand-profiles.csv")
    parser.add_argument("--output-dir", type=str, default=".")
    parser.add_argument("--year", type=int, default=2025)
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


def distribute_to_valley_equal_with_capacity(
    base_load: np.ndarray,
    valley_idx: np.ndarray,
    total_energy: float,
) -> np.ndarray:
    addition = np.zeros_like(base_load, dtype=float)
    if total_energy <= 0 or valley_idx.size == 0:
        return addition

    remaining = float(total_energy)
    active = valley_idx.copy()

    while remaining > 1e-12 and active.size > 0:
        cap = 1.0 - (base_load[active] + addition[active])
        cap = np.maximum(cap, 0.0)
        active = active[cap > 1e-12]
        if active.size == 0:
            break

        cap = 1.0 - (base_load[active] + addition[active])
        cap = np.maximum(cap, 0.0)
        equal_share = remaining / float(active.size)
        delta = np.minimum(cap, equal_share)
        addition[active] += delta
        remaining -= float(delta.sum())

    return addition


def add_flex(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values(["year", "date", "halfhour_index", "timestamp"]).reset_index(drop=True)

    out["surplus"] = np.maximum(0.0, out["utilisation"] - out["med_base"])
    out["undersupply"] = np.maximum(0.0, out["med_base"] - out["utilisation"])

    for col in [
        "reduce_frac_10",
        "reduce_frac_25",
        "valley_shiftable_10",
        "valley_shiftable_25",
        "shift_down_10",
        "shift_down_25",
        "shift_up_10",
        "shift_up_25",
        "shiftable_10_target",
        "shiftable_25_target",
        "shiftable_10_realized",
        "shiftable_25_realized",
        "shiftable_10_unmet",
        "shiftable_25_unmet",
        "total_surplus_peak",
        "load_flex_10",
        "load_flex_25",
    ]:
        out[col] = 0.0

    for _, g in out.groupby(["year", "date"], sort=True):
        idx = g.index.to_numpy()
        hh = g["halfhour_index"].to_numpy(dtype=int)
        util = g["utilisation"].to_numpy(dtype=float)
        med = g["med_base"].to_numpy(dtype=float)
        surplus = np.maximum(0.0, util - med)

        peak_mask = (hh >= 16) & (hh <= 36)
        valley_mask = ~peak_mask

        peak_idx = np.where(peak_mask)[0]
        valley_idx = np.where(valley_mask)[0]

        total_surplus_peak = float(surplus[peak_idx].sum()) if peak_idx.size else 0.0
        shiftable_10 = 0.10 * total_surplus_peak
        shiftable_25 = 0.25 * total_surplus_peak

        reduce_10 = np.zeros_like(util)
        reduce_25 = np.zeros_like(util)

        if total_surplus_peak > 0 and peak_idx.size > 0:
            peak_weights = surplus[peak_idx] / total_surplus_peak
            reduce_10[peak_idx] = peak_weights * shiftable_10
            reduce_25[peak_idx] = peak_weights * shiftable_25

        base_after_reduce_10 = util - reduce_10
        base_after_reduce_25 = util - reduce_25

        valley_add_10 = distribute_to_valley_equal_with_capacity(
            base_load=base_after_reduce_10,
            valley_idx=valley_idx,
            total_energy=shiftable_10,
        )
        valley_add_25 = distribute_to_valley_equal_with_capacity(
            base_load=base_after_reduce_25,
            valley_idx=valley_idx,
            total_energy=shiftable_25,
        )

        flex_10 = np.clip(base_after_reduce_10 + valley_add_10, 0.0, 1.0)
        flex_25 = np.clip(base_after_reduce_25 + valley_add_25, 0.0, 1.0)

        realized_10 = float(valley_add_10.sum())
        realized_25 = float(valley_add_25.sum())

        out.loc[idx, "reduce_frac_10"] = reduce_10
        out.loc[idx, "reduce_frac_25"] = reduce_25
        out.loc[idx, "valley_shiftable_10"] = valley_add_10
        out.loc[idx, "valley_shiftable_25"] = valley_add_25
        out.loc[idx, "shift_down_10"] = reduce_10
        out.loc[idx, "shift_down_25"] = reduce_25
        out.loc[idx, "shift_up_10"] = valley_add_10
        out.loc[idx, "shift_up_25"] = valley_add_25
        out.loc[idx, "shiftable_10_target"] = shiftable_10
        out.loc[idx, "shiftable_25_target"] = shiftable_25
        out.loc[idx, "shiftable_10_realized"] = realized_10
        out.loc[idx, "shiftable_25_realized"] = realized_25
        out.loc[idx, "shiftable_10_unmet"] = max(0.0, shiftable_10 - realized_10)
        out.loc[idx, "shiftable_25_unmet"] = max(0.0, shiftable_25 - realized_25)
        out.loc[idx, "total_surplus_peak"] = total_surplus_peak
        out.loc[idx, "load_flex_10"] = flex_10
        out.loc[idx, "load_flex_25"] = flex_25

    out["down_10_4h"] = (
        out.groupby(["year", "date"])["reduce_frac_10"].rolling(window=8, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["down_25_4h"] = (
        out.groupby(["year", "date"])["reduce_frac_25"].rolling(window=8, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["up_10_4h"] = (
        out.groupby(["year", "date"])["valley_shiftable_10"].rolling(window=8, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["up_25_4h"] = (
        out.groupby(["year", "date"])["valley_shiftable_25"].rolling(window=8, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )

    return out


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


def run_core_analysis(df: pd.DataFrame) -> CoreAnalysisResults:
    ts = prepare_features(df)
    ts = add_baselines(ts)
    ts = add_flex(ts)
    ts, battery_daily_stats = simulate_bess(ts)
    characteristic_days = find_characteristic_days(ts)

    return CoreAnalysisResults(
        battery_daily_stats=battery_daily_stats,
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

    results = run_core_analysis(df)

    if args.year not in results.characteristic_days:
        available = sorted(results.characteristic_days.keys())
        raise ValueError(f"Requested year {args.year} not available. Available years: {available}")

    characteristic_day = results.characteristic_days[args.year]

    day_df = results.timeseries[
        (results.timeseries["year"] == args.year) & (results.timeseries["date"] == characteristic_day)
    ].sort_values("halfhour_index")

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
        output_dir=output_dir,
        characteristic_day=characteristic_day,
        day_df=day_df,
        centres_year_df=centres_year_df,
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
    for path in saved_files:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
