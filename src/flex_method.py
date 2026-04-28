from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linprog


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


DEFAULT_RECIPIENT_WINDOW_START_HOUR = 22.0
DEFAULT_RECIPIENT_WINDOW_END_HOUR = 6.0
CONSERVATIVE_FLEX_BUDGET_HOURS = 2.5
EXPLORATORY_FLEX_BUDGET_HOURS = 4.0
PEAK_TOL = 1e-6

FLEX_SCENARIOS: tuple[FlexScenario, ...] = (
    FlexScenario(
        key="10",
        name="Conservative Flex 10%",
        flex_share=0.10,
        max_peak_hours=CONSERVATIVE_FLEX_BUDGET_HOURS,
        recipient_window_start_hour=DEFAULT_RECIPIENT_WINDOW_START_HOUR,
        recipient_window_end_hour=DEFAULT_RECIPIENT_WINDOW_END_HOUR,
        framing="10% load reduction co-optimized across up to 2.5 peak-equivalent hours per day",
    ),
    FlexScenario(
        key="25",
        name="Exploratory Flex 25%",
        flex_share=0.25,
        max_peak_hours=EXPLORATORY_FLEX_BUDGET_HOURS,
        recipient_window_start_hour=DEFAULT_RECIPIENT_WINDOW_START_HOUR,
        recipient_window_end_hour=DEFAULT_RECIPIENT_WINDOW_END_HOUR,
        framing="25% load reduction co-optimized across up to 4.0 peak-equivalent hours per day",
        exploratory=True,
    ),
)


def _recovery_slot_upper_bound(
    rec_idx: int,
    scenario: FlexScenario,
    base_load: np.ndarray,
    load_total: np.ndarray,
) -> float:
    # Recovery headroom scales directly with the flex magnitude. A scenario that can
    # reduce more deeply is also assumed to be able to absorb a proportionally larger
    # overnight recovery pulse in the same slot.
    recovery_upper = min((1.0 + scenario.flex_share) * base_load[rec_idx], 1.0)
    return max(0.0, recovery_upper - load_total[rec_idx])


def _hour_of_day(timestamp: pd.Timestamp) -> float:
    return timestamp.hour + timestamp.minute / 60.0


def _is_early_recovery_period(timestamp: pd.Timestamp, scenario: FlexScenario) -> bool:
    hour = _hour_of_day(timestamp)
    if scenario.recipient_window_end_hour <= scenario.recipient_window_start_hour:
        return hour < scenario.recipient_window_end_hour
    return False


def is_event_eligible(timestamp: pd.Timestamp, scenario: FlexScenario) -> bool:
    # Restrict source reductions to a narrower daytime peak window so the event starts
    # earlier than the late-afternoon-only case but does not smear across the full day.
    if _is_early_recovery_period(timestamp, scenario):
        return False
    hour = _hour_of_day(timestamp)
    return 11.0 <= hour < 19.0


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


def _recipient_candidates_for_day(
    work: pd.DataFrame,
    source_date: pd.Timestamp,
    scenario: FlexScenario,
) -> list[int]:
    start, end = _recipient_window_bounds(source_date, scenario)
    mask = (work["timestamp"] >= start) & (work["timestamp"] < end)
    return [int(i) for i in work.index[mask]]


def _source_candidates_for_day(
    work: pd.DataFrame,
    day_idx: np.ndarray,
    available_shift: np.ndarray,
    scenario: FlexScenario,
) -> list[int]:
    return [
        int(i)
        for i in day_idx
        if available_shift[i] > 1e-12 and is_event_eligible(pd.Timestamp(work.loc[i, "timestamp"]), scenario)
    ]


def _build_day_pair_problem(
    work: pd.DataFrame,
    source_idx: list[int],
    recipient_idx: list[int],
    scenario: FlexScenario,
    base_load: np.ndarray,
    reference_load: np.ndarray,
    load_total: np.ndarray,
    original_annual_peak: float,
    dt_hours: float,
) -> tuple[list[tuple[int, int]], np.ndarray, np.ndarray, dict[int, list[int]], dict[int, list[int]], float]:
    day_peak = float(np.max(base_load[source_idx])) if source_idx else 0.0
    budget = float(scenario.flex_share * day_peak * scenario.max_peak_hours / dt_hours) if dt_hours > 0 else 0.0

    pairs: list[tuple[int, int]] = []
    delay_hours: list[float] = []
    source_priority: list[float] = []
    pairs_by_source: dict[int, list[int]] = {idx: [] for idx in source_idx}
    pairs_by_recipient: dict[int, list[int]] = {idx: [] for idx in recipient_idx}

    peak_ref = max(day_peak, 1e-9)
    price_series = pd.to_numeric(work["uk_price"], errors="coerce") if "uk_price" in work.columns else None
    max_price = float(np.nanmax(price_series.to_numpy(dtype=float))) if price_series is not None else 1.0
    if not np.isfinite(max_price):
        max_price = 1.0
    max_price = max(max_price, 1e-9)

    for src_idx in source_idx:
        src_ts = pd.Timestamp(work.loc[src_idx, "timestamp"])
        surplus = max(0.0, base_load[src_idx] - reference_load[src_idx])
        if scenario.exploratory and price_series is not None:
            # The exploratory 25% case is price-responsive: it prioritizes higher-price
            # source intervals while still favoring load that sits above the reference profile.
            src_price = float(price_series.loc[src_idx])
            if np.isfinite(src_price):
                price_norm = src_price / max_price
                priority = 1.0 + price_norm + (surplus / peak_ref)
            else:
                priority = 1.0 + (base_load[src_idx] / peak_ref) + (surplus / peak_ref)
        else:
            # The conservative 10% case remains load-magnitude driven.
            priority = 1.0 + (base_load[src_idx] / peak_ref) + (surplus / peak_ref)
        for rec_idx in recipient_idx:
            rec_ts = pd.Timestamp(work.loc[rec_idx, "timestamp"])
            if rec_ts <= src_ts:
                continue
            pair_pos = len(pairs)
            pairs.append((src_idx, rec_idx))
            delay_hours.append((rec_ts - src_ts).total_seconds() / 3600.0)
            source_priority.append(priority)
            pairs_by_source[src_idx].append(pair_pos)
            pairs_by_recipient[rec_idx].append(pair_pos)

    return (
        pairs,
        np.asarray(delay_hours, dtype=float),
        np.asarray(source_priority, dtype=float),
        pairs_by_source,
        pairs_by_recipient,
        budget,
    )


def _solve_daily_shift_lp(
    work: pd.DataFrame,
    source_idx: list[int],
    recipient_idx: list[int],
    available_shift: np.ndarray,
    base_load: np.ndarray,
    reference_load: np.ndarray,
    load_total: np.ndarray,
    original_annual_peak: float,
    dt_hours: float,
    scenario: FlexScenario,
) -> tuple[np.ndarray, np.ndarray, float, float, float]:
    outgoing = np.zeros(len(load_total), dtype=float)
    incoming = np.zeros(len(load_total), dtype=float)

    if not source_idx or not recipient_idx:
        return outgoing, incoming, 0.0, 0.0, 0.0

    (
        pairs,
        delay_hours,
        source_priority,
        pairs_by_source,
        pairs_by_recipient,
        budget,
    ) = _build_day_pair_problem(
        work=work,
        source_idx=source_idx,
        recipient_idx=recipient_idx,
        scenario=scenario,
        base_load=base_load,
        reference_load=reference_load,
        load_total=load_total,
        original_annual_peak=original_annual_peak,
        dt_hours=dt_hours,
    )

    if not pairs or budget <= 1e-12:
        return outgoing, incoming, budget, 0.0, 0.0

    n_pairs = len(pairs)
    var_count = 1 + n_pairs
    idx_m = 0
    peak_upper = float(max(np.max(base_load[source_idx]), np.max(load_total[recipient_idx]), 0.0))

    bounds: list[tuple[float | None, float | None]] = [(0.0, peak_upper)]
    bounds.extend([(0.0, None)] * n_pairs)

    a_ub_rows: list[np.ndarray] = []
    b_ub_rows: list[float] = []

    for src_idx in source_idx:
        row = np.zeros(var_count, dtype=float)
        for pair_pos in pairs_by_source.get(src_idx, []):
            row[1 + pair_pos] = 1.0
        a_ub_rows.append(row)
        b_ub_rows.append(float(available_shift[src_idx]))

    recipient_capacity = {}
    for rec_idx in recipient_idx:
        recipient_capacity[rec_idx] = _recovery_slot_upper_bound(
            rec_idx=rec_idx,
            scenario=scenario,
            base_load=base_load,
            load_total=load_total,
        )
        row = np.zeros(var_count, dtype=float)
        for pair_pos in pairs_by_recipient.get(rec_idx, []):
            row[1 + pair_pos] = 1.0
        a_ub_rows.append(row)
        b_ub_rows.append(float(recipient_capacity[rec_idx]))

    budget_row = np.zeros(var_count, dtype=float)
    budget_row[1:] = 1.0
    a_ub_rows.append(budget_row)
    b_ub_rows.append(float(budget))

    affected_idx = sorted(set(source_idx) | set(recipient_idx))
    for slot_idx in affected_idx:
        row = np.zeros(var_count, dtype=float)
        row[idx_m] = -1.0
        for pair_pos, (src_idx, rec_idx) in enumerate(pairs):
            if rec_idx == slot_idx:
                row[1 + pair_pos] += 1.0
            if src_idx == slot_idx:
                row[1 + pair_pos] -= 1.0
        a_ub_rows.append(row)
        b_ub_rows.append(-float(load_total[slot_idx]))

    a_ub = np.vstack(a_ub_rows)
    b_ub = np.asarray(b_ub_rows, dtype=float)

    peak_stage = linprog(
        c=np.r_[1.0, np.zeros(n_pairs, dtype=float)],
        A_ub=a_ub,
        b_ub=b_ub,
        bounds=bounds,
        method="highs",
    )
    if not peak_stage.success:
        return outgoing, incoming, budget, 0.0, 0.0

    peak_cap = float(peak_stage.x[idx_m])
    peak_limit_row = np.zeros(var_count, dtype=float)
    peak_limit_row[idx_m] = 1.0
    a_ub_stage2 = np.vstack([a_ub, peak_limit_row])
    b_ub_stage2 = np.r_[b_ub, peak_cap + PEAK_TOL]

    delay_penalty = delay_hours / max(24.0, float(np.max(delay_hours)) if delay_hours.size else 24.0)
    c_stage2 = np.r_[0.0, -(source_priority) + 0.01 * delay_penalty]
    allocation_stage = linprog(
        c=c_stage2,
        A_ub=a_ub_stage2,
        b_ub=b_ub_stage2,
        bounds=bounds,
        method="highs",
    )
    if not allocation_stage.success:
        return outgoing, incoming, budget, peak_cap, 0.0

    pair_values = allocation_stage.x[1:]
    delay_weighted_sum = 0.0
    for pair_pos, value in enumerate(pair_values):
        if value <= 1e-12:
            continue
        src_idx, rec_idx = pairs[pair_pos]
        outgoing[src_idx] += float(value)
        incoming[rec_idx] += float(value)
        delay_weighted_sum += float(value) * float(delay_hours[pair_pos])

    return outgoing, incoming, budget, peak_cap, delay_weighted_sum


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
        source_candidates = _source_candidates_for_day(
            work=work,
            day_idx=day_idx,
            available_shift=available_shift,
            scenario=scenario,
        )
        recipient_candidates = _recipient_candidates_for_day(
            work=work,
            source_date=pd.Timestamp(date),
            scenario=scenario,
        )
        outgoing, incoming, shiftable_target, optimized_peak, delay_weighted_sum = _solve_daily_shift_lp(
            work=work,
            source_idx=source_candidates,
            recipient_idx=recipient_candidates,
            available_shift=available_shift,
            base_load=base_load,
            reference_load=reference_load,
            load_total=load_total,
            original_annual_peak=original_annual_peak,
            dt_hours=dt_hours,
            scenario=scenario,
        )

        active_sources = [idx for idx in source_candidates if outgoing[idx] > 1e-12]
        if active_sources:
            event_selected[active_sources] = 1.0

        load_total -= outgoing
        load_total += incoming
        load_flex_shifted -= outgoing
        load_flex_shifted += incoming
        shift_down += outgoing
        shift_up += incoming

        realized = float(outgoing.sum())
        unmet = max(0.0, shiftable_target - realized)
        saturated_recovery_slots = {
            int(rec_idx)
            for rec_idx in recipient_candidates
            if incoming[rec_idx] > 1e-12 and load_total[rec_idx] >= original_annual_peak - 1e-10
        }

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
                "event_candidate_steps": int(len(source_candidates)),
                "selected_peak_steps": int(len(active_sources)),
                "active_shift_steps": int(np.sum(outgoing[day_idx] > 1e-12)),
                "shiftable_target": float(shiftable_target),
                "shiftable_realized": float(realized),
                "shiftable_unmet": float(unmet),
                "shifted_energy_utilisation_hours": float(realized * dt_hours),
                "feasible_day": bool(unmet <= 1e-10),
                "recovery_saturation_slots": int(len(saturated_recovery_slots)),
                "average_deferment_hours": float(delay_weighted_sum / realized) if realized > 1e-12 else 0.0,
                "used_eligible_flex_percent": float(realized / shiftable_target * 100.0) if shiftable_target > 1e-12 else 0.0,
                "fully_recovered_percent": float(realized / shiftable_target * 100.0) if shiftable_target > 1e-12 else 0.0,
                "no_recovery_slots": 0,
                "active_event_day": bool(len(active_sources) > 0),
                "selection_method": "daily_peak_lp_multi_interval",
                "optimized_day_peak_after_flex": float(optimized_peak),
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
