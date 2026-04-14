from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


EVENT_START_HOUR = 14.0
EVENT_END_HOUR = 22.0


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


def apply_two_day_x_axis(ax: plt.Axes, timestamps: pd.Series) -> None:
    x = np.arange(len(timestamps))
    tick_idx = np.arange(0, len(timestamps), 4)
    labels = pd.to_datetime(timestamps.iloc[tick_idx]).dt.strftime("%m-%d %H:%M")
    ax.set_xlim(0, len(timestamps) - 1)
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xticks(np.arange(0, len(timestamps), 1), minor=True)
    ax.grid(True, which="major", alpha=0.28)
    ax.grid(True, which="minor", alpha=0.10)


def apply_delta_ylim(ax: plt.Axes, *series: pd.Series) -> None:
    vals = np.concatenate([np.asarray(s, dtype=float) for s in series])
    abs_max = float(np.max(np.abs(vals))) if vals.size else 0.0
    lim = max(0.002, abs_max * 1.2)
    ax.set_ylim(-lim, lim)


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


def format_index_ranges(indices: list[int]) -> str:
    if not indices:
        return "-"

    values = sorted(set(int(v) for v in indices))
    ranges: list[str] = []
    start = values[0]
    prev = values[0]

    for val in values[1:]:
        if val == prev + 1:
            prev = val
            continue
        ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
        start = val
        prev = val

    ranges.append(f"{start}-{prev}" if start != prev else f"{start}")
    return ",".join(ranges)


def get_event_window_mask(timestamps: pd.Series) -> np.ndarray:
    ts = pd.to_datetime(timestamps)
    hour = ts.dt.hour + ts.dt.minute / 60.0
    return ((ts.dt.weekday < 5) & (hour >= EVENT_START_HOUR) & (hour < EVENT_END_HOUR)).to_numpy(dtype=bool)


def get_two_day_window(year_df: pd.DataFrame, characteristic_day: pd.Timestamp) -> pd.DataFrame:
    start = pd.Timestamp(characteristic_day) - pd.Timedelta(days=1)
    end = pd.Timestamp(characteristic_day) + pd.Timedelta(days=1) - pd.Timedelta(minutes=30)
    out = year_df[(year_df["timestamp"] >= start) & (year_df["timestamp"] <= end)].copy()
    return out.sort_values("timestamp").reset_index(drop=True)


def build_transfer_pairs(window_df: pd.DataFrame, suffix: str) -> list[tuple[int, int, float]]:
    down = window_df[f"shift_down_{suffix}"].to_numpy(dtype=float).copy()
    up = window_df[f"shift_up_{suffix}"].to_numpy(dtype=float).copy()
    transfers: list[tuple[int, int, float]] = []

    down_idx = [int(i) for i in np.where(down > 1e-10)[0]]
    up_idx = [int(i) for i in np.where(up > 1e-10)[0]]

    for src in down_idx:
        remaining = down[src]
        if remaining <= 1e-10:
            continue
        ordered_up = sorted(up_idx, key=lambda dst: (abs(dst - src), dst))
        for dst in ordered_up:
            if remaining <= 1e-10:
                break
            if up[dst] <= 1e-10:
                continue
            amount = min(remaining, up[dst])
            transfers.append((src, dst, float(amount)))
            remaining -= amount
            up[dst] -= amount

    return transfers


def draw_transfer_annotations(
    ax: plt.Axes,
    window_df: pd.DataFrame,
    suffix: str,
    color: str,
) -> None:
    transfers = build_transfer_pairs(window_df, suffix)
    if not transfers:
        return

    ymax = ax.get_ylim()[1]
    for idx, (src, dst, amount) in enumerate(transfers, start=1):
        src_y = float(window_df["utilisation"].iloc[src])
        dst_y = float(window_df["utilisation"].iloc[dst])
        lift = 0.012 + 0.004 * (idx % 3)
        ax.annotate(
            "",
            xy=(dst, dst_y + lift),
            xytext=(src, src_y + lift),
            arrowprops={
                "arrowstyle": "->",
                "color": color,
                "lw": 1.0,
                "alpha": 0.55,
                "shrinkA": 0,
                "shrinkB": 0,
                "connectionstyle": "arc3,rad=0.12",
            },
            zorder=2,
        )
        label_y = min(max(src_y, dst_y) + lift + 0.0015, ymax - 0.002)
        label_x = src + 0.5 * (dst - src)
        ax.text(
            label_x,
            label_y,
            str(idx),
            color=color,
            fontsize=7.5,
            ha="center",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": color, "alpha": 0.78},
            zorder=5,
        )


def build_aggregated_transfers(window_df: pd.DataFrame, suffix: str) -> list[tuple[int, float, float]]:
    transfers = build_transfer_pairs(window_df, suffix)
    if not transfers:
        return []

    grouped: dict[int, list[tuple[int, float]]] = {}
    for src, dst, amount in transfers:
        grouped.setdefault(src, []).append((dst, amount))

    aggregated: list[tuple[int, float, float]] = []
    for src in sorted(grouped):
        total_amount = float(sum(amount for _, amount in grouped[src]))
        if total_amount <= 1e-10:
            continue
        weighted_dst = float(sum(dst * amount for dst, amount in grouped[src]) / total_amount)
        aggregated.append((src, weighted_dst, total_amount))

    return aggregated


def draw_aggregated_transfer_annotations(
    ax: plt.Axes,
    window_df: pd.DataFrame,
    suffix: str,
    color: str,
) -> None:
    transfers = build_aggregated_transfers(window_df, suffix)
    if not transfers:
        return

    ymax = ax.get_ylim()[1]
    timestamps = pd.to_datetime(window_df["timestamp"]).reset_index(drop=True)

    for idx, (src, dst_mean, amount) in enumerate(transfers, start=1):
        src_y = float(window_df["utilisation"].iloc[src])
        dst_y = float(np.interp(dst_mean, np.arange(len(window_df)), window_df["utilisation"].to_numpy(dtype=float)))
        lift = 0.014 + 0.006 * ((idx - 1) % 2)
        ax.annotate(
            "",
            xy=(dst_mean, dst_y + lift),
            xytext=(src, src_y + lift),
            arrowprops={
                "arrowstyle": "->",
                "color": color,
                "lw": 1.8,
                "alpha": 0.78,
                "shrinkA": 0,
                "shrinkB": 0,
                "connectionstyle": "arc3,rad=0.08",
            },
            zorder=4,
        )
        src_label = timestamps.iloc[src].strftime("%H:%M")
        dst_idx = int(round(dst_mean))
        dst_idx = max(0, min(dst_idx, len(timestamps) - 1))
        dst_label = timestamps.iloc[dst_idx].strftime("%H:%M")
        label_x = src + 0.5 * (dst_mean - src)
        label_y = min(max(src_y, dst_y) + lift + 0.002, ymax - 0.002)
        ax.text(
            label_x,
            label_y,
            f"{idx}: {src_label} -> {dst_label}",
            color=color,
            fontsize=8,
            ha="center",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": color, "alpha": 0.86},
            zorder=5,
        )


def plot_figure1(day_df: pd.DataFrame, year: int, out_file: Path) -> None:
    x = day_df["halfhour_index"].to_numpy(dtype=int)

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(
        x,
        day_df["med_base"],
        label="Typical Median Reference",
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
        up_label="Recovery outside event window",
    )

    ax.plot(x, day_df["utilisation"], label="Baseline Load", linewidth=2.5, color="#173f5f", zorder=4)

    ax.set_title(f"AI Data Center Flexibility: 10% Conservative vs 25% Aggressive ({year})", fontsize=13, pad=16)
    ax.text(
        0.5,
        1.01,
        "Characteristic day profile with weekday 14:00-22:00 event-window shifting",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#444444",
    )

    ax.set_xlabel("halfhour_index (0-47)")
    ax.set_ylabel("utilisation")
    apply_granular_x_axis(ax)
    apply_zoomed_ylim(
        ax,
        day_df["utilisation"],
        day_df["med_base"],
        day_df["load_flex_10"],
        day_df["load_flex_25"],
    )

    handles, labels = ax.get_legend_handles_labels()
    order = [
        "Baseline Load",
        "Typical Median Reference",
        "10% Flex",
        "25% Flex",
        "Event-window reduction",
        "Recovery outside event window",
    ]
    handle_map = dict(zip(labels, handles))
    ordered_labels = [label for label in order if label in handle_map]
    ordered_handles = [handle_map[label] for label in ordered_labels]
    ax.legend(ordered_handles, ordered_labels, loc="best", frameon=False)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_two_day_diagnostic(year_df: pd.DataFrame, characteristic_day: pd.Timestamp, year: int, out_file: Path) -> None:
    window_df = get_two_day_window(year_df, characteristic_day)
    if window_df.empty:
        return

    x = np.arange(len(window_df))
    event_mask = get_event_window_mask(window_df["timestamp"])

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    scenario_defs = [
        ("10", "10% Flex", "#f28e2b"),
        ("25", "25% Flex", "#59a14f"),
    ]

    for ax, (suffix, label, color) in zip(axes, scenario_defs):
        scenario_col = f"load_flex_{suffix}"
        shift_down_col = f"shift_down_{suffix}"
        shift_up_col = f"shift_up_{suffix}"

        ax.plot(x, window_df["utilisation"], label="Baseline Load", linewidth=2.3, color="#173f5f", zorder=4)
        ax.plot(x, window_df[scenario_col], label=label, linewidth=1.9, color=color, alpha=0.90, zorder=3)

        ax.fill_between(
            x,
            window_df["utilisation"],
            window_df[scenario_col],
            where=((window_df[shift_down_col].to_numpy(dtype=float) > 1e-10) & event_mask),
            color="#7cc576",
            alpha=0.28,
            label="Reduced in event window",
        )
        ax.fill_between(
            x,
            window_df["utilisation"],
            window_df[scenario_col],
            where=(window_df[shift_up_col].to_numpy(dtype=float) > 1e-10),
            color="#d1495b",
            alpha=0.18,
            label="Recovered in other slots",
        )

        for idx in np.where(event_mask)[0]:
            ax.axvspan(idx - 0.5, idx + 0.5, color="#999999", alpha=0.04, linewidth=0)

        apply_zoomed_ylim(ax, window_df["utilisation"], window_df[scenario_col])
        draw_transfer_annotations(ax, window_df, suffix, color)
        ax.set_ylabel("utilisation")
        ax.set_title(label, fontsize=11, pad=8)
        ax.legend(loc="best", frameon=False, fontsize=8)

    axes[0].text(
        0.5,
        1.08,
        f"Two-day diagnostic around the characteristic day ({year}). Event windows are 14:00-22:00 on weekdays; numbered arrows show which reduced slots are paired with which recovery slots inside the allowed recovery window.",
        transform=axes[0].transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#444444",
    )
    axes[-1].set_xlabel("timestamp")
    apply_two_day_x_axis(axes[-1], window_df["timestamp"].reset_index(drop=True))

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_two_day_aggregated_diagnostic(year_df: pd.DataFrame, characteristic_day: pd.Timestamp, year: int, out_file: Path) -> None:
    window_df = get_two_day_window(year_df, characteristic_day)
    if window_df.empty:
        return

    x = np.arange(len(window_df))
    event_mask = get_event_window_mask(window_df["timestamp"])

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    scenario_defs = [
        ("10", "10% Flex", "#f28e2b"),
        ("25", "25% Flex", "#59a14f"),
    ]

    for ax, (suffix, label, color) in zip(axes, scenario_defs):
        scenario_col = f"load_flex_{suffix}"
        shift_down_col = f"shift_down_{suffix}"
        shift_up_col = f"shift_up_{suffix}"

        ax.plot(x, window_df["utilisation"], label="Baseline Load", linewidth=2.3, color="#173f5f", zorder=4)
        ax.plot(x, window_df[scenario_col], label=label, linewidth=1.9, color=color, alpha=0.90, zorder=3)

        ax.fill_between(
            x,
            window_df["utilisation"],
            window_df[scenario_col],
            where=((window_df[shift_down_col].to_numpy(dtype=float) > 1e-10) & event_mask),
            color="#7cc576",
            alpha=0.28,
            label="Reduced in event window",
        )
        ax.fill_between(
            x,
            window_df["utilisation"],
            window_df[scenario_col],
            where=(window_df[shift_up_col].to_numpy(dtype=float) > 1e-10),
            color="#d1495b",
            alpha=0.18,
            label="Recovered in other slots",
        )

        for idx in np.where(event_mask)[0]:
            ax.axvspan(idx - 0.5, idx + 0.5, color="#999999", alpha=0.04, linewidth=0)

        apply_zoomed_ylim(ax, window_df["utilisation"], window_df[scenario_col])
        draw_aggregated_transfer_annotations(ax, window_df, suffix, color)
        ax.set_ylabel("utilisation")
        ax.set_title(label, fontsize=11, pad=8)
        ax.legend(loc="best", frameon=False, fontsize=8)

    axes[0].text(
        0.5,
        1.08,
        f"Aggregated two-day diagnostic around the characteristic day ({year}). Each arrow aggregates one event-slot reduction to its weighted-average recovery location inside the allowed recovery window.",
        transform=axes[0].transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#444444",
    )
    axes[-1].set_xlabel("timestamp")
    apply_two_day_x_axis(axes[-1], window_df["timestamp"].reset_index(drop=True))

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def make_flex_summary(day_df: pd.DataFrame, flex_daily_stats: pd.DataFrame) -> pd.DataFrame:
    original_peak = float(day_df["utilisation"].max())
    original_energy = float(day_df["utilisation"].sum())
    characteristic_day = pd.Timestamp(day_df["date"].iloc[0])

    scenario_defs = [
        ("Original", "utilisation", None),
        ("10% Flex only", "load_flex_10", "10"),
        ("25% Flex only", "load_flex_25", "25"),
    ]

    rows = []
    for scenario, col, scenario_key in scenario_defs:
        peak_load = float(day_df[col].max())
        daily_energy = float(day_df[col].sum())
        max_increase = float(np.maximum(0.0, day_df[col] - day_df["utilisation"]).max())
        halfhours_above_original = int(np.sum((day_df[col] - day_df["utilisation"]).to_numpy(dtype=float) > 1e-10))
        shifted_energy = 0.0
        unmet_energy = 0.0

        if scenario_key is not None:
            shifted_energy = float(day_df[f"shift_down_{scenario_key}"].sum() * 0.5)
            daily_subset = flex_daily_stats[
                (flex_daily_stats["scenario_key"] == scenario_key)
                & (pd.to_datetime(flex_daily_stats["date"]) == characteristic_day)
            ]
            if not daily_subset.empty:
                unmet_energy = float(daily_subset["shiftable_unmet"].iloc[0] * 0.5)

        rows.append(
            {
                "scenario": scenario,
                "peak_load": peak_load,
                "peak_reduction_vs_original_percent": (
                    (original_peak - peak_load) / original_peak * 100.0 if original_peak > 0 else 0.0
                ),
                "daily_energy": daily_energy,
                "daily_energy_delta_percent": (
                    (daily_energy - original_energy) / original_energy * 100.0 if original_energy > 0 else 0.0
                ),
                "shifted_energy_utilisation_hours": shifted_energy,
                "unmet_energy_utilisation_hours": unmet_energy,
                "max_increase_vs_original": max_increase,
                "halfhours_above_original": halfhours_above_original,
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [c for c in out.columns if c != "scenario"]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def run_rq2(
    day_df: pd.DataFrame,
    year_df: pd.DataFrame,
    flex_daily_stats: pd.DataFrame,
    year: int,
    output_dir: Path,
) -> tuple[Path, Path]:
    _ = year_df

    figure_file = output_dir / "figure1_flex_intermediate.png"
    diagnostic_file = output_dir / "figure1_flex_intermediate_two_day.png"
    diagnostic_agg_file = output_dir / "figure1_flex_intermediate_two_day_aggregated.png"
    summary_file = output_dir / "flexibility_summary_intermediate.csv"

    plot_figure1(day_df, year, figure_file)
    plot_two_day_diagnostic(year_df, pd.Timestamp(day_df["date"].iloc[0]), year, diagnostic_file)
    plot_two_day_aggregated_diagnostic(year_df, pd.Timestamp(day_df["date"].iloc[0]), year, diagnostic_agg_file)
    make_flex_summary(day_df, flex_daily_stats).to_csv(summary_file, index=False)

    return figure_file, summary_file
