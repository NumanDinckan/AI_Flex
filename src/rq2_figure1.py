from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EVENT_START_HOUR = 11.0
EVENT_END_HOUR = 19.0


def apply_zoomed_ylim(ax: plt.Axes, *series: pd.Series) -> None:
    vals = np.concatenate([np.asarray(s, dtype=float) for s in series])
    y_min = float(vals.min())
    y_max = float(vals.max())
    span = max(y_max - y_min, 1e-6)
    pad = 0.22 * span

    lower = max(0.0, y_min - pad)
    upper = min(1.0, y_max + pad)

    if upper - lower < 0.03:
        mid = 0.5 * (upper + lower)
        lower = max(0.0, mid - 0.015)
        upper = min(1.0, mid + 0.015)

    ax.set_ylim(lower, upper)


def apply_granular_x_axis(ax: plt.Axes) -> None:
    ax.set_xlim(0, 47)
    ax.set_xticks(np.arange(0, 48, 4))
    ax.set_xticks(np.arange(0, 48, 1), minor=True)
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
    ax.grid(True, which="major", alpha=0.28)
    ax.grid(True, which="minor", alpha=0.12)


def apply_timestamp_x_axis(ax: plt.Axes, timestamps: pd.Series) -> None:
    x = np.arange(len(timestamps))
    tick_idx = np.arange(0, len(timestamps), 4)
    labels = pd.to_datetime(timestamps.iloc[tick_idx]).dt.strftime("%m-%d %H:%M")
    ax.set_xlim(0, len(timestamps) - 1)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xticks(np.arange(0, len(timestamps), 1), minor=True)
    ax.grid(True, which="major", alpha=0.28)
    ax.grid(True, which="minor", alpha=0.10)


def apply_horizon_hour_axis(ax: plt.Axes, horizon_hours: pd.Series | np.ndarray) -> None:
    hours = np.asarray(horizon_hours, dtype=float)
    if hours.size == 0:
        return
    max_hour = float(hours.max())
    major_step = 4 if max_hour <= 24 else 6
    display_max = float(np.ceil(max_hour / major_step) * major_step)
    if max_hour > 24 and display_max < 48:
        display_max = 48.0
    major_ticks = np.arange(0, display_max + 0.01, major_step)
    ax.set_xlim(float(hours.min()), display_max)
    ax.set_xticks(major_ticks)
    ax.set_xticklabels([f"{int(h):02d}:00" for h in major_ticks])
    ax.set_xticks(np.arange(0, display_max + 0.01, 1), minor=True)
    ax.grid(True, which="major", alpha=0.28)
    ax.grid(True, which="minor", alpha=0.10)


def apply_delta_ylim(ax: plt.Axes, *series: pd.Series) -> None:
    vals = np.concatenate([np.asarray(s, dtype=float) for s in series])
    abs_max = float(np.max(np.abs(vals))) if vals.size else 0.0
    lim = max(0.002, abs_max * 1.2)
    ax.set_ylim(-lim, lim)


def add_price_axis(
    ax: plt.Axes,
    x: np.ndarray,
    df: pd.DataFrame,
    label: str = "UK electricity price",
) -> plt.Axes | None:
    if "uk_price" not in df.columns:
        return None
    price = pd.to_numeric(df["uk_price"], errors="coerce")
    if price.notna().sum() == 0:
        return None

    price_ax = ax.twinx()
    price_ax.plot(
        x,
        price.to_numpy(dtype=float),
        label=label,
        linewidth=1.7,
        linestyle=":",
        color="#6f42c1",
        alpha=0.88,
        zorder=0,
    )
    price_ax.set_ylabel("price (EUR/MWh)", color="#6f42c1")
    price_ax.tick_params(axis="y", colors="#6f42c1")
    price_ax.grid(False)
    return price_ax


def merge_legends(ax: plt.Axes, extra_axes: list[plt.Axes | None] | None = None, **legend_kwargs: object) -> None:
    handles, labels = ax.get_legend_handles_labels()
    for extra_ax in extra_axes or []:
        if extra_ax is None:
            continue
        extra_handles, extra_labels = extra_ax.get_legend_handles_labels()
        handles.extend(extra_handles)
        labels.extend(extra_labels)
    ax.legend(handles, labels, **legend_kwargs)


def add_peak_valley_shading(
    ax: plt.Axes,
    x: np.ndarray,
    original: pd.Series,
    shifted: pd.Series,
    reduction_label: str,
    up_label: str,
    event_mask: np.ndarray | None = None,
) -> None:
    if event_mask is None:
        hour = np.asarray(x, dtype=float) / 2.0
        active_event_mask = (hour >= EVENT_START_HOUR) & (hour < EVENT_END_HOUR)
    else:
        active_event_mask = np.asarray(event_mask, dtype=bool)

    valley_mask = ~active_event_mask
    reduced = shifted < original
    increased = shifted > original

    ax.fill_between(
        x,
        original,
        shifted,
        where=(active_event_mask & reduced),
        color="#8fd19e",
        alpha=0.22,
        label=reduction_label,
    )
    ax.fill_between(
        x,
        original,
        shifted,
        where=(valley_mask & increased),
        color="#f4b7b2",
        alpha=0.18,
        label=up_label,
    )


def build_annual_mean_horizon(
    year_df: pd.DataFrame,
    dt_hours: float,
    horizon_hours: float = 48.0,
) -> pd.DataFrame:
    steps = int(round(horizon_hours / dt_hours))
    day_steps = int(round(24.0 / dt_hours))
    numeric_cols = [
        col
        for col in year_df.columns
        if pd.api.types.is_numeric_dtype(year_df[col])
        and col not in {"year", "month", "weekday", "halfhour_index"}
    ]

    windows: list[pd.DataFrame] = []
    for date in sorted(pd.to_datetime(year_df["date"].dropna().unique())):
        start = pd.Timestamp(date)
        end = start + pd.Timedelta(hours=horizon_hours)
        window = year_df[(year_df["timestamp"] >= start) & (year_df["timestamp"] < end)].copy()
        if window.empty:
            continue
        elapsed_hours = (window["timestamp"] - start).dt.total_seconds() / 3600.0
        window["horizon_index"] = np.rint(elapsed_hours / dt_hours).astype(int)
        window = window[(window["horizon_index"] >= 0) & (window["horizon_index"] < steps)]
        if window["horizon_index"].nunique() == steps:
            windows.append(window[["horizon_index", *numeric_cols]])

    if not windows:
        raise ValueError("No complete annual 48-hour windows could be built for RQ2.")

    profile = (
        pd.concat(windows, ignore_index=True)
        .groupby("horizon_index", observed=True)[numeric_cols]
        .mean()
        .reindex(range(steps))
        .interpolate(limit_direction="both")
        .reset_index()
    )
    profile["horizon_hour"] = profile["horizon_index"] * dt_hours
    profile["halfhour_index"] = profile["horizon_index"] % day_steps
    profile["profile_basis"] = f"annual_mean_{int(horizon_hours)}h_shift_window"
    return profile


def plot_figure1(day_df: pd.DataFrame, year: int, out_file: Path) -> None:
    x = day_df["halfhour_index"].to_numpy(dtype=int)
    reference_col = "mean_day_base" if "mean_day_base" in day_df.columns else "med_base"

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(
        x,
        day_df[reference_col],
        label="Annual Mean Baseline",
        linewidth=1.9,
        linestyle="--",
        color="#6c757d",
        alpha=0.85,
        zorder=1,
    )
    ax.plot(x, day_df["load_flex_10"], label="10% Flex", linewidth=1.8, color="#f28e2b", alpha=0.78, zorder=2)
    ax.plot(x, day_df["load_flex_25"], label="25% Flex", linewidth=1.8, color="#59a14f", alpha=0.76, zorder=2)

    add_peak_valley_shading(
        ax=ax,
        x=x,
        original=day_df["utilisation"],
        shifted=day_df["load_flex_25"],
        reduction_label="Event-window reduction",
        up_label="Recovery-window increase",
    )

    ax.plot(x, day_df["utilisation"], label="Baseline Load", linewidth=2.5, color="#173f5f", zorder=4)

    ax.set_title(f"AI Data Center Flexibility: Annual Mean-Day Profile ({year})", fontsize=13, pad=16)
    ax.text(
        0.5,
        1.01,
        "Full-year mean daily profile after co-optimized peak-window reductions and scenario-specific recovery",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#444444",
    )

    ax.set_xlabel("time of day (HH:MM)")
    ax.set_ylabel("utilisation")
    apply_granular_x_axis(ax)
    price_ax = add_price_axis(ax, x, day_df, label="UK electricity price (annual mean)")
    apply_zoomed_ylim(
        ax,
        day_df["utilisation"],
        day_df[reference_col],
        day_df["load_flex_10"],
        day_df["load_flex_25"],
    )

    handles, labels = ax.get_legend_handles_labels()
    order = [
        "Baseline Load",
        "Annual Mean Baseline",
        "10% Flex",
        "25% Flex",
        "Event-window reduction",
        "Recovery-window increase",
    ]
    handle_map = dict(zip(labels, handles))
    ordered_labels = [label for label in order if label in handle_map]
    ordered_handles = [handle_map[label] for label in ordered_labels]
    if price_ax is not None:
        price_handles, price_labels = price_ax.get_legend_handles_labels()
        ordered_handles.extend(price_handles)
        ordered_labels.extend(price_labels)
    ax.legend(ordered_handles, ordered_labels, loc="best", frameon=False)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_annual_shift_components(day_df: pd.DataFrame, year: int, out_file: Path) -> None:
    x = day_df["halfhour_index"].to_numpy(dtype=int)
    scenarios = [
        ("10", "10% Flex", "#f28e2b"),
        ("25", "25% Flex", "#59a14f"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(16, 9), sharex="col")

    for row, (suffix, label, color) in enumerate(scenarios):
        load_ax = axes[row, 0]
        shift_ax = axes[row, 1]
        flex_col = f"load_flex_{suffix}"
        down_col = f"shift_down_{suffix}"
        up_col = f"shift_up_{suffix}"

        load_ax.plot(x, day_df["utilisation"], label="Annual mean baseline", linewidth=2.3, color="#173f5f")
        load_ax.plot(x, day_df[flex_col], label=label, linewidth=2.0, color=color)
        load_ax.fill_between(
            x,
            day_df["utilisation"],
            day_df[flex_col],
            where=day_df[down_col].to_numpy(dtype=float) > 1e-10,
            color="#8fd19e",
            alpha=0.25,
            label="mean reduction",
        )
        load_ax.fill_between(
            x,
            day_df["utilisation"],
            day_df[flex_col],
            where=day_df[up_col].to_numpy(dtype=float) > 1e-10,
            color="#f4b7b2",
            alpha=0.20,
            label="mean recovery",
        )
        load_ax.set_title(f"{label}: annual mean-day load response", fontsize=11, pad=10)
        load_ax.set_ylabel("utilisation")
        apply_zoomed_ylim(load_ax, day_df["utilisation"], day_df[flex_col])
        apply_granular_x_axis(load_ax)
        price_ax = add_price_axis(load_ax, x, day_df, label="UK price")
        merge_legends(load_ax, [price_ax], loc="best", frameon=False, fontsize=8)

        shift_ax.bar(x - 0.16, -day_df[down_col], width=0.32, color="#2ca25f", alpha=0.72, label="reduction")
        shift_ax.bar(x + 0.16, day_df[up_col], width=0.32, color="#de6b6b", alpha=0.62, label="recovery")
        shift_ax.axhline(0.0, color="#333333", linewidth=1.0)
        shift_ax.set_title(f"{label}: mean shifted load by recipient/source hour", fontsize=11, pad=10)
        shift_ax.set_ylabel("mean shifted\nutilisation")
        apply_delta_ylim(shift_ax, day_df[down_col], day_df[up_col])
        apply_granular_x_axis(shift_ax)
        shift_ax.legend(loc="best", frameon=False, fontsize=8)

    axes[1, 0].set_xlabel("time of day (HH:MM)")
    axes[1, 1].set_xlabel("time of day (HH:MM)")
    fig.suptitle(f"RQ2 Flexibility Components: Annual Mean-Day View ({year})", fontsize=14, y=0.995)
    fig.text(
        0.5,
        0.955,
        "Reductions are selected within 11:00-19:00; recovery is 22:00-06:00 for 10% and 20:00-08:00 for 25%.",
        ha="center",
        va="top",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_annual_48h_shift_window(
    year_df: pd.DataFrame,
    year: int,
    dt_hours: float,
    out_file: Path,
) -> None:
    horizon_df = build_annual_mean_horizon(year_df, dt_hours=dt_hours, horizon_hours=48.0)
    x = horizon_df["horizon_hour"].to_numpy(dtype=float)
    scenarios = [
        ("10", "10% Flex", "#f28e2b"),
        ("25", "25% Flex", "#59a14f"),
    ]

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for ax, (suffix, label, color) in zip(axes, scenarios):
        flex_col = f"load_flex_{suffix}"
        down_col = f"shift_down_{suffix}"
        up_col = f"shift_up_{suffix}"

        ax.plot(x, horizon_df["utilisation"], label="Annual mean baseline", linewidth=2.2, color="#173f5f")
        ax.plot(x, horizon_df[flex_col], label=label, linewidth=2.0, color=color)
        ax.fill_between(
            x,
            horizon_df["utilisation"],
            horizon_df[flex_col],
            where=horizon_df[down_col].to_numpy(dtype=float) > 1e-10,
            color="#8fd19e",
            alpha=0.28,
            label="peak reduction",
        )
        ax.fill_between(
            x,
            horizon_df["utilisation"],
            horizon_df[flex_col],
            where=horizon_df[up_col].to_numpy(dtype=float) > 1e-10,
            color="#f4b7b2",
            alpha=0.20,
            label="overnight recovery",
        )
        recovery_spans = [(22, 30), (46, 48)] if suffix == "10" else [(20, 32), (44, 48)]
        for start, end in recovery_spans:
            ax.axvspan(start, end, color="#bdd7e7", alpha=0.12, linewidth=0)
        apply_zoomed_ylim(ax, horizon_df["utilisation"], horizon_df[flex_col])
        ax.set_ylabel("utilisation")
        ax.set_title(label, fontsize=11, pad=8)
        price_ax = add_price_axis(ax, x, horizon_df, label="UK price")
        merge_legends(ax, [price_ax], loc="best", frameon=False, fontsize=8)
        ax.grid(alpha=0.22)

    axes[-1].set_xlabel("hour of annual mean 48-hour profile")
    apply_horizon_hour_axis(axes[-1], x)
    fig.suptitle(f"RQ2 Flexibility: Annual Mean 48-Hour Shift Window ({year})", fontsize=14, y=0.995)
    fig.text(
        0.5,
        0.955,
        "Annual mean 0-48h profile averaged from complete daily 48-hour windows in the selected year; no specific calendar days are shown.",
        ha="center",
        va="top",
        fontsize=10,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def _scenario_definition(scenario_key: str | None) -> str:
    if scenario_key == "10":
        return "10% load reduction co-optimized across up to 2.5 peak-equivalent hours per day; shifted to 22:00-06:00"
    if scenario_key == "25":
        return "25% load reduction co-optimized across up to 4.0 peak-equivalent hours per day; shifted to 20:00-08:00"
    return "no flexibility applied"


def _first_non_null(df: pd.DataFrame, column: str, default: object) -> object:
    if column not in df.columns:
        return default
    values = df[column].dropna()
    if values.empty:
        return default
    return values.iloc[0]


def make_flex_summary(
    mean_day_df: pd.DataFrame,
    year_df: pd.DataFrame,
    flex_daily_stats: pd.DataFrame,
    dt_hours: float,
) -> pd.DataFrame:
    original_peak_year = float(year_df["utilisation"].max())
    original_energy_year = float(year_df["utilisation"].sum() * dt_hours)
    original_energy_mean_day = float(mean_day_df["utilisation"].sum() * dt_hours)

    scenario_defs = [
        ("Original", "utilisation", None),
        ("10% Flex only", "load_flex_10", "10"),
        ("25% Flex only", "load_flex_25", "25"),
    ]

    rows = []
    for scenario, col, scenario_key in scenario_defs:
        mean_day_peak = float(mean_day_df[col].max())
        mean_day_energy = float(mean_day_df[col].sum() * dt_hours)
        annual_energy = float(year_df[col].sum() * dt_hours)
        residual_peak_after_flex = float(year_df[col].max())
        max_increase = float(np.maximum(0.0, mean_day_df[col] - mean_day_df["utilisation"]).max())
        halfhours_above_original = int(
            np.sum((mean_day_df[col] - mean_day_df["utilisation"]).to_numpy(dtype=float) > 1e-10)
        )
        shifted_energy = 0.0
        unmet_energy = 0.0
        active_flex_days = 0
        recipient_window = ""
        max_peak_hours = np.nan
        mean_unmet_shift_budget_percent = np.nan
        max_unmet_shift_budget_percent = np.nan
        high_unmet_recovery_days = 0
        recovery_saturation_days = 0
        mean_recovery_capacity_used_percent = np.nan

        if scenario_key is not None:
            daily_subset = flex_daily_stats[
                (flex_daily_stats["scenario_key"] == scenario_key)
            ]
            shifted_energy = float(daily_subset["shiftable_realized"].sum() * dt_hours) if not daily_subset.empty else 0.0
            unmet_energy = float(daily_subset["shiftable_unmet"].sum() * dt_hours) if not daily_subset.empty else 0.0
            if not daily_subset.empty:
                active_flex_days = int(np.sum(daily_subset["active_event_day"].to_numpy(dtype=bool)))
                recipient_window = str(_first_non_null(daily_subset, "recipient_window", ""))
                max_peak_hours = float(_first_non_null(daily_subset, "max_peak_hours", np.nan))
                if "unmet_shift_budget_percent" in daily_subset:
                    mean_unmet_shift_budget_percent = float(daily_subset["unmet_shift_budget_percent"].mean())
                    max_unmet_shift_budget_percent = float(daily_subset["unmet_shift_budget_percent"].max())
                if "high_unmet_recovery_warning" in daily_subset:
                    high_unmet_recovery_days = int(
                        np.sum(daily_subset["high_unmet_recovery_warning"].to_numpy(dtype=bool))
                    )
                if "recovery_saturation_slots" in daily_subset:
                    recovery_saturation_days = int(
                        np.sum(daily_subset["recovery_saturation_slots"].to_numpy(dtype=float) > 0)
                    )
                if "recovery_capacity_used_percent" in daily_subset:
                    mean_recovery_capacity_used_percent = float(daily_subset["recovery_capacity_used_percent"].mean())

        rows.append(
            {
                "scenario": scenario,
                "profile_basis": "annual_mean_day",
                "operational_definition": _scenario_definition(scenario_key),
                "original_peak_load": original_peak_year,
                "residual_peak_after_flex": residual_peak_after_flex,
                "annual_peak_reduction_vs_original_percent": (
                    (original_peak_year - residual_peak_after_flex) / original_peak_year * 100.0
                    if original_peak_year > 0
                    else 0.0
                ),
                "mean_day_peak_load": mean_day_peak,
                "mean_day_energy_utilisation_hours": mean_day_energy,
                "mean_day_energy_delta_percent": (
                    (mean_day_energy - original_energy_mean_day) / original_energy_mean_day * 100.0
                    if original_energy_mean_day > 0
                    else 0.0
                ),
                "annual_energy_utilisation_hours": annual_energy,
                "annual_energy_delta_percent": (
                    (annual_energy - original_energy_year) / original_energy_year * 100.0
                    if original_energy_year > 0
                    else 0.0
                ),
                "shifted_energy_utilisation_hours_year": shifted_energy,
                "unmet_shift_budget_utilisation_hours_year": unmet_energy,
                "max_increase_vs_original_mean_day": max_increase,
                "halfhours_above_original_mean_day": halfhours_above_original,
                "active_flex_days": active_flex_days,
                "max_peak_hours": max_peak_hours,
                "recipient_window": recipient_window,
                "mean_unmet_shift_budget_percent": mean_unmet_shift_budget_percent,
                "max_unmet_shift_budget_percent": max_unmet_shift_budget_percent,
                "high_unmet_recovery_days": high_unmet_recovery_days,
                "recovery_saturation_days": recovery_saturation_days,
                "mean_recovery_capacity_used_percent": mean_recovery_capacity_used_percent,
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [
        c
        for c in out.columns
        if c not in {"scenario", "profile_basis", "operational_definition", "recipient_window"}
    ]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def run_rq2(
    mean_day_df: pd.DataFrame,
    year_df: pd.DataFrame,
    flex_daily_stats: pd.DataFrame,
    year: int,
    dt_hours: float,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_file = output_dir / "figure1_flex_intermediate.png"
    components_file = output_dir / "figure1_flex_intermediate_annual_shift_components.png"
    horizon_file = output_dir / "figure1_flex_intermediate_annual_48h_shift_window.png"
    summary_file = output_dir / "flexibility_summary_intermediate.csv"

    plot_figure1(mean_day_df, year, figure_file)
    plot_annual_shift_components(mean_day_df, year, components_file)
    plot_annual_48h_shift_window(year_df, year, dt_hours=dt_hours, out_file=horizon_file)
    make_flex_summary(mean_day_df, year_df, flex_daily_stats, dt_hours=dt_hours).to_csv(summary_file, index=False)

    return [figure_file, components_file, horizon_file, summary_file]
