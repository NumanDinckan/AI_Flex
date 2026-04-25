from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FlexScenario:
    key: str
    name: str
    flex_share: float
    max_peak_hours: float
    recipient_window_start_hour: float
    recipient_window_end_hour: float
    framing: str
    exploratory: bool = False


FLEX_EVENT_START_HOUR = 14.0
FLEX_EVENT_END_HOUR = 22.0
DEFAULT_RECIPIENT_WINDOW_START_HOUR = 22.0
DEFAULT_RECIPIENT_WINDOW_END_HOUR = 2.0

FLEX_SCENARIOS: tuple[FlexScenario, ...] = (
    FlexScenario(
        key="10",
        name="Conservative Flex 10%",
        flex_share=0.10,
        max_peak_hours=3.0,
        recipient_window_start_hour=DEFAULT_RECIPIENT_WINDOW_START_HOUR,
        recipient_window_end_hour=DEFAULT_RECIPIENT_WINDOW_END_HOUR,
        framing="10% load reduction for up to 3 consecutive peak hours",
    ),
    FlexScenario(
        key="25",
        name="Exploratory Flex 25%",
        flex_share=0.25,
        max_peak_hours=3.0,
        recipient_window_start_hour=DEFAULT_RECIPIENT_WINDOW_START_HOUR,
        recipient_window_end_hour=DEFAULT_RECIPIENT_WINDOW_END_HOUR,
        framing="25% load reduction for up to 3 consecutive peak hours",
        exploratory=True,
    ),
)


def is_event_eligible(timestamp: pd.Timestamp) -> bool:
    hour = timestamp.hour + timestamp.minute / 60.0
    return timestamp.weekday() < 5 and FLEX_EVENT_START_HOUR <= hour < FLEX_EVENT_END_HOUR


def _recipient_window_label(scenario: FlexScenario) -> str:
    start = int(scenario.recipient_window_start_hour)
    end = int(scenario.recipient_window_end_hour)
    return f"{start:02d}:00-{end:02d}:00"


def _recipient_window_bounds(date: pd.Timestamp, scenario: FlexScenario) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(date) + pd.Timedelta(hours=scenario.recipient_window_start_hour)
    end = pd.Timestamp(date) + pd.Timedelta(hours=scenario.recipient_window_end_hour)
    if scenario.recipient_window_end_hour <= scenario.recipient_window_start_hour:
        end += pd.Timedelta(days=1)
    return start, end


def _select_peak_block(
    work: pd.DataFrame,
    day_idx: np.ndarray,
    available_shift: np.ndarray,
    base_load: np.ndarray,
    dt_hours: float,
    scenario: FlexScenario,
) -> np.ndarray:
    event_idx = [
        int(i)
        for i in day_idx
        if is_event_eligible(pd.Timestamp(work.loc[i, "timestamp"]))
    ]
    if not event_idx:
        return np.asarray([], dtype=int)

    max_steps = max(1, int(round(scenario.max_peak_hours / dt_hours)))
    expected_delta = pd.Timedelta(hours=dt_hours)
    best_block: list[int] = []
    best_score = (-np.inf, -np.inf)

    for start_pos in range(len(event_idx)):
        block = [event_idx[start_pos]]
        for next_pos in range(start_pos + 1, len(event_idx)):
            if len(block) >= max_steps:
                break
            prev_ts = pd.Timestamp(work.loc[block[-1], "timestamp"])
            next_idx = event_idx[next_pos]
            next_ts = pd.Timestamp(work.loc[next_idx, "timestamp"])
            if next_ts - prev_ts != expected_delta:
                break
            block.append(next_idx)

        shifted_score = float(available_shift[block].sum())
        load_score = float(base_load[block].sum())
        if (shifted_score, load_score) > best_score:
            best_score = (shifted_score, load_score)
            best_block = block

    selected = [i for i in best_block if available_shift[i] > 1e-12]
    return np.asarray(selected, dtype=int)


def _recipient_candidates_for_day(
    work: pd.DataFrame,
    source_date: pd.Timestamp,
    scenario: FlexScenario,
) -> list[int]:
    start, end = _recipient_window_bounds(source_date, scenario)
    mask = (work["timestamp"] >= start) & (work["timestamp"] < end)
    return [int(i) for i in work.index[mask]]


def apply_shiftable_flex_for_scenario(
    year_df: pd.DataFrame,
    dt_hours: float,
    scenario: FlexScenario,
) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    if dt_hours <= 0:
        raise ValueError("dt_hours must be positive.")

    work = year_df.sort_values("timestamp").reset_index()
    base_load = work["utilisation"].to_numpy(dtype=float)
    original_annual_peak = float(np.max(base_load)) if base_load.size else 0.0
    reference_col = "mean_day_base" if "mean_day_base" in work.columns else "med_base"
    reference_load = work[reference_col].to_numpy(dtype=float)

    load_total = base_load.copy()
    load_inflex = (1.0 - scenario.flex_share) * base_load
    load_flex_orig = scenario.flex_share * base_load
    load_flex_shifted = load_flex_orig.copy()
    shift_down = np.zeros(len(work), dtype=float)
    shift_up = np.zeros(len(work), dtype=float)
    event_selected = np.zeros(len(work), dtype=float)

    available_shift = np.maximum(0.0, load_flex_orig)
    max_peak_steps = max(1, int(round(scenario.max_peak_hours / dt_hours)))
    recipient_window = _recipient_window_label(scenario)
    daily_rows: list[dict[str, object]] = []

    for date, day_frame in work.groupby(work["timestamp"].dt.floor("D"), sort=True):
        day_idx = day_frame.index.to_numpy(dtype=int)
        event_candidates = [
            i
            for i in day_idx
            if is_event_eligible(pd.Timestamp(work.loc[i, "timestamp"]))
        ]
        selected = _select_peak_block(
            work=work,
            day_idx=day_idx,
            available_shift=available_shift,
            base_load=base_load,
            dt_hours=dt_hours,
            scenario=scenario,
        )
        shiftable_target = float(available_shift[selected].sum()) if selected.size else 0.0
        realized = 0.0
        delay_weighted_sum = 0.0
        saturated_recovery_slots: set[int] = set()
        no_recovery_slots = 0

        recipient_candidates = _recipient_candidates_for_day(
            work=work,
            source_date=pd.Timestamp(date),
            scenario=scenario,
        )

        for peak_idx in selected:
            amount = float(available_shift[peak_idx])
            remaining = amount
            if remaining <= 1e-12:
                continue

            recovery_candidates = []
            for rec_idx in recipient_candidates:
                if rec_idx == peak_idx:
                    continue
                recovery_candidates.append(rec_idx)

            recovery_candidates.sort(key=lambda i: (base_load[i], abs(i - peak_idx), i))
            peak_realized = 0.0
            for rec_idx in recovery_candidates:
                if remaining <= 1e-12:
                    break
                median_gap_allowance = max(0.0, reference_load[peak_idx] - reference_load[rec_idx])
                recovery_upper = min(
                    base_load[rec_idx] + median_gap_allowance,
                    (1.0 + scenario.flex_share) * base_load[rec_idx],
                    original_annual_peak,
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
                rec_ts = pd.Timestamp(work.loc[rec_idx, "timestamp"])
                peak_ts = pd.Timestamp(work.loc[peak_idx, "timestamp"])
                delay_weighted_sum += delta * ((rec_ts - peak_ts).total_seconds() / 3600.0)
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
                "max_peak_hours": float(scenario.max_peak_hours),
                "max_peak_steps": int(max_peak_steps),
                "recipient_window": recipient_window,
                "recipient_window_start_hour": float(scenario.recipient_window_start_hour),
                "recipient_window_end_hour": float(scenario.recipient_window_end_hour),
                "reference_baseline": reference_col,
                "event_candidate_steps": int(len(event_candidates)),
                "selected_peak_steps": int(len(selected)),
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

    reference_col = "mean_day_base" if "mean_day_base" in out.columns else "med_base"
    out["surplus"] = np.maximum(0.0, out["utilisation"] - out[reference_col])
    out["undersupply"] = np.maximum(0.0, out[reference_col] - out["utilisation"])

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

            if not daily_stats.empty:
                day_metric_map = daily_stats.set_index("date")
                out.loc[row_index, f"shiftable_{suffix}_target"] = out.loc[row_index, "date"].map(day_metric_map["shiftable_target"])
                out.loc[row_index, f"shiftable_{suffix}_realized"] = out.loc[row_index, "date"].map(day_metric_map["shiftable_realized"])
                out.loc[row_index, f"shiftable_{suffix}_unmet"] = out.loc[row_index, "date"].map(day_metric_map["shiftable_unmet"])
                flex_daily_stats_parts.append(daily_stats)

    rolling_window_steps = max(1, int(round(3.0 / dt_hours)))
    out["down_10_3h"] = (
        out.groupby(["year", "date"])["reduce_frac_10"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["down_25_3h"] = (
        out.groupby(["year", "date"])["reduce_frac_25"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["up_10_3h"] = (
        out.groupby(["year", "date"])["valley_shiftable_10"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )
    out["up_25_3h"] = (
        out.groupby(["year", "date"])["valley_shiftable_25"].rolling(window=rolling_window_steps, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
    )

    flex_daily_stats = pd.concat(flex_daily_stats_parts, ignore_index=True) if flex_daily_stats_parts else pd.DataFrame()
    return out, flex_daily_stats
