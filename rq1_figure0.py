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


def plot_intro_typical_day_with_all_centres(
    day_df: pd.DataFrame,
    centre_day_df: pd.DataFrame,
    year: int,
    char_day: pd.Timestamp,
    out_file: Path,
) -> None:
    raw_median = (
        centre_day_df.groupby("halfhour_index", sort=True)["utilisation"]
        .median()
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )
    baseline = day_df.set_index("halfhour_index")["med_base"].reindex(range(48)).interpolate(limit_direction="both")
    p10 = (
        centre_day_df.groupby("halfhour_index", sort=True)["utilisation"]
        .quantile(0.10)
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )
    p90 = (
        centre_day_df.groupby("halfhour_index", sort=True)["utilisation"]
        .quantile(0.90)
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )

    centre_profiles = (
        centre_day_df.groupby(["centre", "halfhour_index"], observed=True)["utilisation"].median().reset_index()
    )
    centre_q25 = (
        centre_profiles.groupby("halfhour_index")["utilisation"]
        .quantile(0.25)
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )
    centre_q75 = (
        centre_profiles.groupby("halfhour_index")["utilisation"]
        .quantile(0.75)
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )

    x = raw_median.index.to_numpy(dtype=int)

    fig, ax = plt.subplots(figsize=(12, 6))

    first = True
    for _centre, g in centre_profiles.groupby("centre", sort=True):
        g = g.sort_values("halfhour_index")
        ax.plot(
            g["halfhour_index"].to_numpy(dtype=int),
            g["utilisation"].to_numpy(dtype=float),
            color="#7f7f7f",
            linewidth=0.6,
            alpha=0.18,
            label="All data centres (median per centre)" if first else None,
            zorder=1,
        )
        first = False

    ax.fill_between(
        x,
        centre_q25.to_numpy(dtype=float),
        centre_q75.to_numpy(dtype=float),
        color="#bdbdbd",
        alpha=0.18,
        label="Centre IQR (q25-q75)",
        zorder=1.5,
    )
    ax.fill_between(
        x,
        p10.to_numpy(dtype=float),
        p90.to_numpy(dtype=float),
        color="#9ecae1",
        alpha=0.24,
        label="p10-p90 band",
        zorder=2,
    )
    ax.plot(x, raw_median.to_numpy(dtype=float), linewidth=2.4, color="#1f77b4", label="Raw median utilisation", zorder=3)
    ax.plot(
        x,
        baseline.to_numpy(dtype=float),
        linewidth=2.1,
        linestyle="--",
        color="#2f2f2f",
        label="Baseline (median by weekday + halfhour)",
        zorder=4,
    )

    ax.set_title(f"Typical Daily Utilisation with Baseline and Centre Spread ({year})", fontsize=13, pad=16)
    ax.text(
        0.5,
        1.01,
        f"{pd.Timestamp(char_day).date()} | all data centres: raw median, baseline and p10-p90 envelope",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#444444",
    )
    ax.set_xlabel("time of day (HH:MM)")
    ax.set_ylabel("utilisation")
    apply_granular_x_axis(ax)
    apply_zoomed_ylim(ax, raw_median, baseline, p10, p90)
    ax.legend(loc="best", frameon=False)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def run_rq1(
    day_df: pd.DataFrame,
    centres_day_df: pd.DataFrame,
    year: int,
    characteristic_day: pd.Timestamp,
    output_dir: Path,
) -> Path:
    out_file = output_dir / "figure0_intro_typical_day_all_centres.png"
    plot_intro_typical_day_with_all_centres(day_df, centres_day_df, year, characteristic_day, out_file)
    return out_file
