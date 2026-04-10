from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


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
) -> None:
    peak_mask = (x >= 16) & (x <= 36)
    valley_mask = ~peak_mask

    reduced = shifted < original
    increased = shifted > original

    ax.fill_between(
        x,
        original,
        shifted,
        where=(peak_mask & reduced),
        color="#2ca02c",
        alpha=0.18,
        label=reduction_label,
    )
    ax.fill_between(
        x,
        original,
        shifted,
        where=(valley_mask & increased),
        color="#ff9896",
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


def plot_figure1(day_df: pd.DataFrame, year: int, out_file: Path) -> None:
    x = day_df["halfhour_index"].to_numpy(dtype=int)

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.plot(x, day_df["utilisation"], label="Original Load", linewidth=2.2, color="#1f77b4")
    ax.plot(x, day_df["med_base"], label="Baseline (med_base)", linewidth=2.0, linestyle="--", color="#4d4d4d")
    ax.plot(x, day_df["load_flex_10"], label="10% Flex", linewidth=2.0, color="#ff7f0e")
    ax.plot(x, day_df["load_flex_25"], label="25% Flex", linewidth=2.0, color="#2ca02c")

    add_peak_valley_shading(
        ax=ax,
        x=x,
        original=day_df["utilisation"],
        shifted=day_df["load_flex_25"],
        reduction_label="Peak reduction by flex (8:00-18:00)",
        up_label="Valley up-shift by flex",
    )

    ax.set_title(f"AI Data Center Flexibility: 10-25% Load Shifting Reduces Daily Peaks ({year})", fontsize=13, pad=16)
    ax.text(
        0.5,
        1.01,
        "Annual peak profile - 10% and 25% flexible demand shifting vs baseline",
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
    ax.legend(loc="best", frameon=False)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def make_flex_summary(day_df: pd.DataFrame) -> pd.DataFrame:
    original_peak = float(day_df["utilisation"].max())
    original_energy = float(day_df["utilisation"].sum())

    scenario_defs = [
        ("Original", "utilisation"),
        ("10% Flex only", "load_flex_10"),
        ("25% Flex only", "load_flex_25"),
    ]

    rows = []
    for scenario, col in scenario_defs:
        peak_load = float(day_df[col].max())
        daily_energy = float(day_df[col].sum())
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
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [c for c in out.columns if c != "scenario"]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def run_rq2(day_df: pd.DataFrame, year: int, output_dir: Path) -> tuple[Path, Path]:
    figure_file = output_dir / "figure1_flex_intermediate.png"
    summary_file = output_dir / "flexibility_summary_intermediate.csv"

    plot_figure1(day_df, year, figure_file)
    make_flex_summary(day_df).to_csv(summary_file, index=False)

    return figure_file, summary_file
