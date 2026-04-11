from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rq2_figure1 import (
    add_peak_valley_shading,
    apply_delta_ylim,
    apply_granular_x_axis,
    apply_zoomed_ylim,
    format_index_ranges,
)


def _plot_figure2(
    day_df: pd.DataFrame,
    year: int,
    out_file: Path,
    flex_col: str,
    batt4_col: str,
    batt8_col: str,
    title: str,
    flex_label: str,
    peak_reduction_label: str,
    valley_label: str,
) -> None:
    x = day_df["halfhour_index"].to_numpy(dtype=int)
    flex = day_df[flex_col]
    batt4 = day_df[batt4_col]
    batt8 = day_df[batt8_col]
    delta4 = batt4 - flex
    delta8 = batt8 - flex

    kick4_down = x[delta4.to_numpy(dtype=float) < -1e-10].tolist()
    kick8_down = x[delta8.to_numpy(dtype=float) < -1e-10].tolist()

    fig, (ax, axd) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 2]})

    ax.plot(x, day_df["utilisation"], label="Original Load", linewidth=2.2, color="#1f77b4")
    ax.plot(
        x,
        flex,
        label=f"{flex_label} Flex only",
        linewidth=1.9,
        color="#2ca02c" if "25%" in flex_label else "#ff7f0e",
    )
    ax.plot(x, batt4, label=f"{flex_label} Flex + 4h Battery", linewidth=1.9, color="#d62728")
    ax.plot(x, batt8, label=f"{flex_label} Flex + 8h Battery", linewidth=1.9, color="#9467bd")
    ax.axvspan(28, 44, color="#999999", alpha=0.08)

    add_peak_valley_shading(
        ax=ax,
        x=x,
        original=day_df["utilisation"],
        shifted=batt8,
        reduction_label=peak_reduction_label,
        up_label=valley_label,
    )

    ax.scatter(
        kick4_down,
        batt4.iloc[[np.where(x == k)[0][0] for k in kick4_down]],
        marker="v",
        s=28,
        color="#d62728",
        alpha=0.9,
        label="4h discharge kick",
    )
    ax.scatter(
        kick8_down,
        batt8.iloc[[np.where(x == k)[0][0] for k in kick8_down]],
        marker="v",
        s=28,
        color="#9467bd",
        alpha=0.9,
        label="8h discharge kick",
    )

    ax.set_title(f"AI Data Center Flexibility with 4h and 8h Co-Located Battery ({year}, {title})", fontsize=13, pad=12)
    ax.text(
        0.01,
        0.02,
        f"4h down:{format_index_ranges(kick4_down)} | 8h down:{format_index_ranges(kick8_down)}",
        transform=ax.transAxes,
        fontsize=8.8,
        color="#444444",
        va="bottom",
    )
    ax.set_ylabel("utilisation")
    apply_granular_x_axis(ax)
    apply_zoomed_ylim(ax, day_df["utilisation"], flex, batt4, batt8)
    ax.legend(loc="best", frameon=False, fontsize=8)

    axd.plot(x, delta4, color="#d62728", linewidth=1.8, label="4h - Flex only")
    axd.plot(x, delta8, color="#9467bd", linewidth=1.8, label="8h - Flex only")
    axd.axhline(0.0, color="#333333", linewidth=1.0, alpha=0.8)
    axd.fill_between(x, 0.0, delta4, where=(delta4 < 0), color="#d62728", alpha=0.12)
    axd.fill_between(x, 0.0, delta8, where=(delta8 < 0), color="#9467bd", alpha=0.12)
    axd.fill_between(x, 0.0, delta4, where=(delta4 > 0), color="#d62728", alpha=0.08)
    axd.fill_between(x, 0.0, delta8, where=(delta8 > 0), color="#9467bd", alpha=0.08)
    axd.set_xlabel("time of day (HH:MM)")
    axd.set_ylabel("delta vs flex")
    apply_granular_x_axis(axd)
    apply_delta_ylim(axd, delta4, delta8)
    axd.legend(loc="best", frameon=False, fontsize=8)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def make_bess_summary(day_df: pd.DataFrame, battery_daily_stats: pd.DataFrame, year: int) -> pd.DataFrame:
    peak_original = float(day_df["utilisation"].max())
    peak_flex_10 = float(day_df["load_flex_10"].max())
    peak_flex_25 = float(day_df["load_flex_25"].max())
    char_day = pd.Timestamp(day_df["date"].iloc[0])

    rows = [
        {
            "scenario": "Original (no flex, no BESS)",
            "peak_load": peak_original,
            "peak_reduction_vs_original_percent": 0.0,
            "peak_reduction_vs_matching_flex_only_percent": np.nan,
            "total_battery_discharge_energy_year": 0.0,
            "total_battery_charge_energy_year": 0.0,
            "discharge_threshold_char_day": np.nan,
            "charge_threshold_char_day": np.nan,
            "dynamic_peak_region_char_day": "",
            "dynamic_valley_region_char_day": "",
        }
    ]

    scenarios = [
        ("10% Flex + 4h BESS", "10%_flex + 4h-Battery", "4h", "load_10_flex_4h_batt", "load_flex_10", peak_flex_10),
        ("10% Flex + 8h BESS", "10%_flex + 8h-Battery", "8h", "load_10_flex_8h_batt", "load_flex_10", peak_flex_10),
        ("25% Flex + 4h BESS", "25%_flex + 4h-Battery", "4h", "load_25_flex_4h_batt", "load_flex_25", peak_flex_25),
        ("25% Flex + 8h BESS", "25%_flex + 8h-Battery", "8h", "load_25_flex_8h_batt", "load_flex_25", peak_flex_25),
    ]

    for label, raw_scenario, batt_duration, day_col, flex_col, flex_only_peak in scenarios:
        by_year = battery_daily_stats[
            (battery_daily_stats["year"] == year)
            & (battery_daily_stats["battery_duration"] == batt_duration)
            & (battery_daily_stats["scenario"] == raw_scenario)
        ]
        by_char_day = by_year[by_year["date"] == char_day]
        day_row = by_char_day.iloc[0] if not by_char_day.empty else (by_year.iloc[0] if not by_year.empty else None)

        peak_post = float(day_df[day_col].max())
        delta = day_df[day_col].to_numpy(dtype=float) - day_df[flex_col].to_numpy(dtype=float)
        hh_idx = day_df["halfhour_index"].to_numpy(dtype=int)
        kick_down = hh_idx[delta < -1e-10].tolist()
        kick_up = hh_idx[delta > 1e-10].tolist()

        rows.append(
            {
                "scenario": label,
                "peak_load": peak_post,
                "peak_reduction_vs_original_percent": (
                    (peak_original - peak_post) / peak_original * 100.0 if peak_original > 0 else 0.0
                ),
                "peak_reduction_vs_matching_flex_only_percent": (
                    (flex_only_peak - peak_post) / flex_only_peak * 100.0 if flex_only_peak > 0 else 0.0
                ),
                "total_battery_discharge_energy_year": float(by_year["total_discharge"].sum()),
                "total_battery_charge_energy_year": float(by_year["total_charge"].sum()),
                "kick_down_idx_char_day": format_index_ranges(kick_down),
                "kick_up_idx_char_day": format_index_ranges(kick_up),
                "kick_down_steps_char_day": int(len(kick_down)),
                "kick_up_steps_char_day": int(len(kick_up)),
                "discharge_threshold_char_day": float(day_row["discharge_threshold"]) if day_row is not None else np.nan,
                "charge_threshold_char_day": float(day_row["charge_threshold"]) if day_row is not None else np.nan,
                "dynamic_peak_region_char_day": str(day_row["dynamic_peak_region"]) if day_row is not None else "",
                "dynamic_valley_region_char_day": str(day_row["dynamic_valley_region"]) if day_row is not None else "",
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [c for c in out.columns if c != "scenario"]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def run_rq3(day_df: pd.DataFrame, battery_daily_stats: pd.DataFrame, year: int, output_dir: Path) -> tuple[Path, Path, Path]:
    fig2_10 = output_dir / "figure2_flex_bess_10_intermediate.png"
    fig2_25 = output_dir / "figure2_flex_bess_25_intermediate.png"
    summary = output_dir / "bess_summary_intermediate.csv"

    _plot_figure2(
        day_df=day_df,
        year=year,
        out_file=fig2_10,
        flex_col="load_flex_10",
        batt4_col="load_10_flex_4h_batt",
        batt8_col="load_10_flex_8h_batt",
        title="10% Flex",
        flex_label="10%",
        peak_reduction_label="Peak reduction (10% + 8h)",
        valley_label="Valley up-shift (10% + 8h)",
    )
    _plot_figure2(
        day_df=day_df,
        year=year,
        out_file=fig2_25,
        flex_col="load_flex_25",
        batt4_col="load_25_flex_4h_batt",
        batt8_col="load_25_flex_8h_batt",
        title="25% Flex",
        flex_label="25%",
        peak_reduction_label="Peak reduction (25% + 8h)",
        valley_label="Valley up-shift (25% + 8h)",
    )

    make_bess_summary(day_df, battery_daily_stats, year).to_csv(summary, index=False)

    return fig2_10, fig2_25, summary
