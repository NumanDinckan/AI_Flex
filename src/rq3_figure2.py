from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rq2_figure1 import apply_delta_ylim, apply_two_day_x_axis, apply_zoomed_ylim


def get_forward_two_day_window(year_df: pd.DataFrame, characteristic_day: pd.Timestamp) -> pd.DataFrame:
    start = pd.Timestamp(characteristic_day)
    end = start + pd.Timedelta(days=2)
    out = year_df[(year_df["timestamp"] >= start) & (year_df["timestamp"] < end)].copy()
    return out.sort_values("timestamp").reset_index(drop=True)


def _lookup_battery_energy(
    battery_daily_stats: pd.DataFrame,
    year: int,
    scenario_label: str,
) -> float:
    match = battery_daily_stats[
        (battery_daily_stats["year"] == year)
        & (battery_daily_stats["scenario"] == scenario_label)
    ]
    if match.empty:
        return np.nan
    return float(match["battery_energy"].iloc[0])


def _plot_figure2_two_day(
    window_df: pd.DataFrame,
    year: int,
    out_file: Path,
    flex_col: str,
    batt4_col: str,
    batt8_col: str,
    net4_col: str,
    net8_col: str,
    soc4_col: str,
    soc8_col: str,
    battery_energy_4h: float,
    battery_energy_8h: float,
    title: str,
    flex_label: str,
) -> None:
    x = np.arange(len(window_df))
    timestamps = window_df["timestamp"].reset_index(drop=True)
    characteristic_day = pd.Timestamp(window_df["date"].iloc[0])
    characteristic_steps = int(np.sum(window_df["date"] == characteristic_day))

    flex = window_df[flex_col]
    batt4 = window_df[batt4_col]
    batt8 = window_df[batt8_col]
    net4 = window_df[net4_col]
    net8 = window_df[net8_col]

    soc4_pct = 100.0 * window_df[soc4_col] / battery_energy_4h if battery_energy_4h > 0 else np.nan
    soc8_pct = 100.0 * window_df[soc8_col] / battery_energy_8h if battery_energy_8h > 0 else np.nan

    fig, (ax_load, ax_power, ax_soc) = plt.subplots(
        3,
        1,
        figsize=(14, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3.0, 1.8, 1.6]},
    )

    if 0 < characteristic_steps < len(window_df):
        for ax in (ax_load, ax_power, ax_soc):
            ax.axvline(characteristic_steps - 0.5, color="#777777", linewidth=1.1, alpha=0.7)

    ax_load.plot(x, window_df["utilisation"], label="Original Load", linewidth=2.0, color="#1f77b4", alpha=0.78)
    ax_load.plot(
        x,
        flex,
        label=f"{flex_label} Flex only",
        linewidth=2.0,
        color="#2ca02c" if "25%" in flex_label else "#ff7f0e",
        alpha=0.88,
    )
    ax_load.plot(x, batt4, label=f"{flex_label} Flex + 4h Battery", linewidth=1.9, color="#d62728")
    ax_load.plot(x, batt8, label=f"{flex_label} Flex + 8h Battery", linewidth=1.9, color="#9467bd")
    ax_load.fill_between(x, flex, batt8, where=(batt8 < flex), color="#8fd19e", alpha=0.18, label="8h discharge effect")
    ax_load.fill_between(x, flex, batt8, where=(batt8 > flex), color="#f4b7b2", alpha=0.14, label="8h recharge effect")
    ax_load.set_title(f"AI Data Center Flexibility with Two-Day BESS Dispatch ({year}, {title})", fontsize=13, pad=12)
    ax_load.text(
        0.5,
        1.02,
        "48h look-ahead peak-shaving dispatch. Left of the divider is the characteristic peak day; right is the next day.",
        transform=ax_load.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#444444",
    )
    ax_load.set_ylabel("utilisation")
    apply_zoomed_ylim(ax_load, window_df["utilisation"], flex, batt4, batt8)
    ax_load.grid(alpha=0.22)
    ax_load.legend(loc="best", frameon=False, fontsize=8)

    ax_power.plot(x, net4, color="#d62728", linewidth=1.8, label="4h battery net power")
    ax_power.plot(x, net8, color="#9467bd", linewidth=1.8, label="8h battery net power")
    ax_power.axhline(0.0, color="#333333", linewidth=1.0, alpha=0.85)
    ax_power.fill_between(x, 0.0, net4, where=(net4 > 0), color="#d62728", alpha=0.12)
    ax_power.fill_between(x, 0.0, net4, where=(net4 < 0), color="#d62728", alpha=0.08)
    ax_power.fill_between(x, 0.0, net8, where=(net8 > 0), color="#9467bd", alpha=0.12)
    ax_power.fill_between(x, 0.0, net8, where=(net8 < 0), color="#9467bd", alpha=0.08)
    ax_power.set_ylabel("battery power\n(+ discharge)")
    apply_delta_ylim(ax_power, net4, net8)
    ax_power.grid(alpha=0.22)
    ax_power.legend(loc="best", frameon=False, fontsize=8)

    ax_soc.plot(x, soc4_pct, color="#d62728", linewidth=1.8, label="4h battery SoC")
    ax_soc.plot(x, soc8_pct, color="#9467bd", linewidth=1.8, label="8h battery SoC")
    ax_soc.set_ylabel("SoC (%)")
    ax_soc.set_xlabel("timestamp")
    ax_soc.set_ylim(0, 100)
    ax_soc.grid(alpha=0.22)
    ax_soc.legend(loc="best", frameon=False, fontsize=8)
    apply_two_day_x_axis(ax_soc, timestamps)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def make_bess_summary(
    year_df: pd.DataFrame,
    battery_daily_stats: pd.DataFrame,
    characteristic_day: pd.Timestamp,
    year: int,
) -> pd.DataFrame:
    window_df = get_forward_two_day_window(year_df, characteristic_day)

    annual_peak_original = float(year_df["utilisation"].max())
    annual_peak_flex_10 = float(year_df["load_flex_10"].max())
    annual_peak_flex_25 = float(year_df["load_flex_25"].max())

    window_peak_original = float(window_df["utilisation"].max()) if not window_df.empty else np.nan
    window_peak_flex_10 = float(window_df["load_flex_10"].max()) if not window_df.empty else np.nan
    window_peak_flex_25 = float(window_df["load_flex_25"].max()) if not window_df.empty else np.nan

    rows = [
        {
            "scenario": "Original (no flex, no BESS)",
            "controller_method": "",
            "battery_duration": "",
            "annual_peak_load": annual_peak_original,
            "two_day_window_peak_load": window_peak_original,
            "annual_peak_reduction_vs_original_percent": 0.0,
            "annual_peak_reduction_vs_matching_flex_only_percent": np.nan,
            "two_day_window_peak_reduction_vs_original_percent": 0.0,
            "two_day_window_peak_reduction_vs_matching_flex_only_percent": np.nan,
            "total_battery_discharge_energy_year": 0.0,
            "total_battery_charge_energy_year": 0.0,
            "total_cycles_year": 0.0,
            "mean_target_grid_power_year": np.nan,
            "target_grid_power_window_start": np.nan,
            "initial_soc_window_start": np.nan,
            "final_soc_window_end": np.nan,
            "charge_steps_window": 0,
            "discharge_steps_window": 0,
            "min_soc_window": np.nan,
            "max_soc_window": np.nan,
            "terminal_soc_slack_year": 0.0,
        }
    ]

    scenarios = [
        (
            "10% Flex + 4h BESS",
            "10%_flex + 4h-Battery",
            "4h",
            "load_10_flex_4h_batt",
            "load_flex_10",
            "charge_10_flex_4h_batt",
            "discharge_10_flex_4h_batt",
            "soc_10_flex_4h_batt",
            annual_peak_flex_10,
            window_peak_flex_10,
        ),
        (
            "10% Flex + 8h BESS",
            "10%_flex + 8h-Battery",
            "8h",
            "load_10_flex_8h_batt",
            "load_flex_10",
            "charge_10_flex_8h_batt",
            "discharge_10_flex_8h_batt",
            "soc_10_flex_8h_batt",
            annual_peak_flex_10,
            window_peak_flex_10,
        ),
        (
            "25% Flex + 4h BESS",
            "25%_flex + 4h-Battery",
            "4h",
            "load_25_flex_4h_batt",
            "load_flex_25",
            "charge_25_flex_4h_batt",
            "discharge_25_flex_4h_batt",
            "soc_25_flex_4h_batt",
            annual_peak_flex_25,
            window_peak_flex_25,
        ),
        (
            "25% Flex + 8h BESS",
            "25%_flex + 8h-Battery",
            "8h",
            "load_25_flex_8h_batt",
            "load_flex_25",
            "charge_25_flex_8h_batt",
            "discharge_25_flex_8h_batt",
            "soc_25_flex_8h_batt",
            annual_peak_flex_25,
            window_peak_flex_25,
        ),
    ]

    window_start = pd.Timestamp(characteristic_day)
    window_end = window_start + pd.Timedelta(days=2)

    for label, raw_scenario, batt_duration, load_col, flex_col, charge_col, discharge_col, soc_col, annual_peak_flex, window_peak_flex in scenarios:
        by_year = battery_daily_stats[
            (battery_daily_stats["year"] == year)
            & (battery_daily_stats["battery_duration"] == batt_duration)
            & (battery_daily_stats["scenario"] == raw_scenario)
        ].copy()
        by_year["date"] = pd.to_datetime(by_year["date"])
        by_window = by_year[(by_year["date"] >= window_start) & (by_year["date"] < window_end)].copy()

        annual_peak_post = float(year_df[load_col].max())
        window_peak_post = float(window_df[load_col].max()) if not window_df.empty else np.nan

        start_row = by_year[by_year["date"] == window_start]

        rows.append(
            {
                "scenario": label,
                "controller_method": str(by_year["controller_method"].iloc[0]) if not by_year.empty else "",
                "battery_duration": batt_duration,
                "annual_peak_load": annual_peak_post,
                "two_day_window_peak_load": window_peak_post,
                "annual_peak_reduction_vs_original_percent": (
                    (annual_peak_original - annual_peak_post) / annual_peak_original * 100.0 if annual_peak_original > 0 else 0.0
                ),
                "annual_peak_reduction_vs_matching_flex_only_percent": (
                    (annual_peak_flex - annual_peak_post) / annual_peak_flex * 100.0 if annual_peak_flex > 0 else 0.0
                ),
                "two_day_window_peak_reduction_vs_original_percent": (
                    (window_peak_original - window_peak_post) / window_peak_original * 100.0 if window_peak_original > 0 else 0.0
                ),
                "two_day_window_peak_reduction_vs_matching_flex_only_percent": (
                    (window_peak_flex - window_peak_post) / window_peak_flex * 100.0 if window_peak_flex > 0 else 0.0
                ),
                "total_battery_discharge_energy_year": float(by_year["total_discharge"].sum()),
                "total_battery_charge_energy_year": float(by_year["total_charge"].sum()),
                "total_cycles_year": float(by_year["cycles"].sum()),
                "mean_target_grid_power_year": float(by_year["target_grid_power"].mean()) if not by_year.empty else np.nan,
                "target_grid_power_window_start": float(start_row["target_grid_power"].iloc[0]) if not start_row.empty else np.nan,
                "initial_soc_window_start": float(start_row["initial_soc"].iloc[0]) if not start_row.empty else np.nan,
                "final_soc_window_end": float(window_df[soc_col].iloc[-1]) if not window_df.empty else np.nan,
                "charge_steps_window": int(np.sum(window_df[charge_col].to_numpy(dtype=float) > 1e-10)) if not window_df.empty else 0,
                "discharge_steps_window": int(np.sum(window_df[discharge_col].to_numpy(dtype=float) > 1e-10)) if not window_df.empty else 0,
                "min_soc_window": float(window_df[soc_col].min()) if not window_df.empty else np.nan,
                "max_soc_window": float(window_df[soc_col].max()) if not window_df.empty else np.nan,
                "terminal_soc_slack_year": float(by_year["terminal_soc_slack"].sum()) if "terminal_soc_slack" in by_year else np.nan,
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [c for c in out.columns if c not in {"scenario", "controller_method", "battery_duration"}]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def run_rq3(
    day_df: pd.DataFrame,
    year_df: pd.DataFrame,
    battery_daily_stats: pd.DataFrame,
    year: int,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    characteristic_day = pd.Timestamp(day_df["date"].iloc[0])
    window_df = get_forward_two_day_window(year_df, characteristic_day)

    fig2_10 = output_dir / "figure2_flex_bess_10_intermediate.png"
    fig2_25 = output_dir / "figure2_flex_bess_25_intermediate.png"
    summary = output_dir / "bess_summary_intermediate.csv"

    battery_energy_4h = _lookup_battery_energy(battery_daily_stats, year, "10%_flex + 4h-Battery")
    battery_energy_8h = _lookup_battery_energy(battery_daily_stats, year, "10%_flex + 8h-Battery")

    _plot_figure2_two_day(
        window_df=window_df,
        year=year,
        out_file=fig2_10,
        flex_col="load_flex_10",
        batt4_col="load_10_flex_4h_batt",
        batt8_col="load_10_flex_8h_batt",
        net4_col="net_batt_10_flex_4h_batt",
        net8_col="net_batt_10_flex_8h_batt",
        soc4_col="soc_10_flex_4h_batt",
        soc8_col="soc_10_flex_8h_batt",
        battery_energy_4h=battery_energy_4h,
        battery_energy_8h=battery_energy_8h,
        title="10% Flex",
        flex_label="10%",
    )
    _plot_figure2_two_day(
        window_df=window_df,
        year=year,
        out_file=fig2_25,
        flex_col="load_flex_25",
        batt4_col="load_25_flex_4h_batt",
        batt8_col="load_25_flex_8h_batt",
        net4_col="net_batt_25_flex_4h_batt",
        net8_col="net_batt_25_flex_8h_batt",
        soc4_col="soc_25_flex_4h_batt",
        soc8_col="soc_25_flex_8h_batt",
        battery_energy_4h=battery_energy_4h,
        battery_energy_8h=battery_energy_8h,
        title="25% Flex",
        flex_label="25%",
    )

    make_bess_summary(year_df, battery_daily_stats, characteristic_day, year).to_csv(summary, index=False)

    return fig2_10, fig2_25, summary
