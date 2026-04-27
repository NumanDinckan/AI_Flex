from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rq2_figure1 import add_price_axis, apply_delta_ylim, apply_horizon_hour_axis, apply_zoomed_ylim, merge_legends


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


def _plot_figure2_mean_horizon(
    horizon_df: pd.DataFrame,
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
    x = (
        horizon_df["horizon_hour"].to_numpy(dtype=float)
        if "horizon_hour" in horizon_df.columns
        else np.arange(len(horizon_df), dtype=float) * 0.5
    )

    flex = horizon_df[flex_col]
    batt4 = horizon_df[batt4_col]
    batt8 = horizon_df[batt8_col]
    net4 = horizon_df[net4_col]
    net8 = horizon_df[net8_col]

    soc4_pct = 100.0 * horizon_df[soc4_col] / battery_energy_4h if battery_energy_4h > 0 else np.nan
    soc8_pct = 100.0 * horizon_df[soc8_col] / battery_energy_8h if battery_energy_8h > 0 else np.nan

    fig, (ax_load, ax_power, ax_soc) = plt.subplots(
        3,
        1,
        figsize=(14, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3.0, 1.8, 1.6]},
    )

    ax_load.plot(x, horizon_df["utilisation"], label="Original Load", linewidth=2.0, color="#1f77b4", alpha=0.78)
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
    ax_load.set_title(f"AI Data Center Flexibility with BESS: Annual Mean 48-Hour Horizon ({year}, {title})", fontsize=12.5, pad=28)
    ax_load.text(
        0.5,
        1.01,
        "Annual mean 0-48h profile averaged from all rolling 48-hour windows in the selected year; no specific calendar days are shown.",
        transform=ax_load.transAxes,
        ha="center",
        va="bottom",
        fontsize=9.5,
        color="#444444",
    )
    ax_load.set_ylabel("utilisation")
    apply_zoomed_ylim(ax_load, horizon_df["utilisation"], flex, batt4, batt8)
    price_ax = add_price_axis(ax_load, x, horizon_df, label="UK electricity price")
    ax_load.grid(alpha=0.22)
    merge_legends(ax_load, [price_ax], loc="best", frameon=False, fontsize=8)

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
    ax_soc.set_xlabel("hour of annual mean 48-hour profile")
    ax_soc.set_ylim(0, 100)
    ax_soc.grid(alpha=0.22)
    ax_soc.legend(loc="best", frameon=False, fontsize=8)
    apply_horizon_hour_axis(ax_soc, x)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def make_bess_summary(
    mean_horizon_df: pd.DataFrame,
    year_df: pd.DataFrame,
    battery_daily_stats: pd.DataFrame,
    year: int,
    dt_hours: float,
) -> pd.DataFrame:
    annual_peak_original = float(year_df["utilisation"].max())
    annual_peak_flex_10 = float(year_df["load_flex_10"].max())
    annual_peak_flex_25 = float(year_df["load_flex_25"].max())

    mean_horizon_peak_original = float(mean_horizon_df["utilisation"].max())
    mean_horizon_peak_flex_10 = float(mean_horizon_df["load_flex_10"].max())
    mean_horizon_peak_flex_25 = float(mean_horizon_df["load_flex_25"].max())

    rows = [
        {
            "scenario": "Original (no flex, no BESS)",
            "controller_method": "",
            "battery_duration": "",
            "profile_basis": "annual_mean_48h_horizon",
            "original_peak_load": annual_peak_original,
            "residual_peak_after_flex": annual_peak_original,
            "residual_peak_after_flex_and_bess": annual_peak_original,
            "annual_peak_load": annual_peak_original,
            "mean_horizon_peak_load": mean_horizon_peak_original,
            "annual_peak_reduction_vs_original_percent": 0.0,
            "annual_peak_reduction_vs_matching_flex_only_percent": np.nan,
            "mean_horizon_peak_reduction_vs_original_percent": 0.0,
            "mean_horizon_peak_reduction_vs_matching_flex_only_percent": np.nan,
            "total_battery_discharge_energy_year": 0.0,
            "total_battery_charge_energy_year": 0.0,
            "total_cycles_year": 0.0,
            "mean_target_grid_power_year": np.nan,
            "mean_horizon_charge_steps": 0,
            "mean_horizon_discharge_steps": 0,
            "mean_horizon_min_soc": np.nan,
            "mean_horizon_max_soc": np.nan,
            "terminal_soc_slack_year": 0.0,
            "price_signal_used": False,
            "total_grid_cost_proxy_year": np.nan,
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
            mean_horizon_peak_flex_10,
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
            mean_horizon_peak_flex_10,
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
            mean_horizon_peak_flex_25,
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
            mean_horizon_peak_flex_25,
        ),
    ]

    for label, raw_scenario, batt_duration, load_col, flex_col, charge_col, discharge_col, soc_col, annual_peak_flex, mean_horizon_peak_flex in scenarios:
        by_year = battery_daily_stats[
            (battery_daily_stats["year"] == year)
            & (battery_daily_stats["battery_duration"] == batt_duration)
            & (battery_daily_stats["scenario"] == raw_scenario)
        ].copy()

        annual_peak_post = float(year_df[load_col].max())
        mean_horizon_peak_post = float(mean_horizon_df[load_col].max()) if not mean_horizon_df.empty else np.nan
        price_signal_used = bool(by_year["price_signal_used"].any()) if "price_signal_used" in by_year else False
        total_grid_cost = (
            float(by_year["energy_cost_proxy"].sum())
            if "energy_cost_proxy" in by_year and by_year["energy_cost_proxy"].notna().any()
            else np.nan
        )

        rows.append(
            {
                "scenario": label,
                "controller_method": str(by_year["controller_method"].iloc[0]) if not by_year.empty else "",
                "battery_duration": batt_duration,
                "profile_basis": "annual_mean_48h_horizon",
                "original_peak_load": annual_peak_original,
                "residual_peak_after_flex": annual_peak_flex,
                "residual_peak_after_flex_and_bess": annual_peak_post,
                "annual_peak_load": annual_peak_post,
                "mean_horizon_peak_load": mean_horizon_peak_post,
                "annual_peak_reduction_vs_original_percent": (
                    (annual_peak_original - annual_peak_post) / annual_peak_original * 100.0 if annual_peak_original > 0 else 0.0
                ),
                "annual_peak_reduction_vs_matching_flex_only_percent": (
                    (annual_peak_flex - annual_peak_post) / annual_peak_flex * 100.0 if annual_peak_flex > 0 else 0.0
                ),
                "mean_horizon_peak_reduction_vs_original_percent": (
                    (mean_horizon_peak_original - mean_horizon_peak_post) / mean_horizon_peak_original * 100.0 if mean_horizon_peak_original > 0 else 0.0
                ),
                "mean_horizon_peak_reduction_vs_matching_flex_only_percent": (
                    (mean_horizon_peak_flex - mean_horizon_peak_post) / mean_horizon_peak_flex * 100.0 if mean_horizon_peak_flex > 0 else 0.0
                ),
                "total_battery_discharge_energy_year": float(by_year["total_discharge"].sum()),
                "total_battery_charge_energy_year": float(by_year["total_charge"].sum()),
                "total_cycles_year": float(by_year["cycles"].sum()),
                "mean_target_grid_power_year": float(by_year["target_grid_power"].mean()) if not by_year.empty else np.nan,
                "mean_horizon_charge_steps": int(np.sum(mean_horizon_df[charge_col].to_numpy(dtype=float) > 1e-10)) if not mean_horizon_df.empty else 0,
                "mean_horizon_discharge_steps": int(np.sum(mean_horizon_df[discharge_col].to_numpy(dtype=float) > 1e-10)) if not mean_horizon_df.empty else 0,
                "mean_horizon_min_soc": float(mean_horizon_df[soc_col].min()) if not mean_horizon_df.empty else np.nan,
                "mean_horizon_max_soc": float(mean_horizon_df[soc_col].max()) if not mean_horizon_df.empty else np.nan,
                "terminal_soc_slack_year": float(by_year["terminal_soc_slack"].sum()) if "terminal_soc_slack" in by_year else np.nan,
                "price_signal_used": price_signal_used,
                "total_grid_cost_proxy_year": total_grid_cost,
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [
        c
        for c in out.columns
        if c not in {"scenario", "controller_method", "battery_duration", "profile_basis", "price_signal_used"}
    ]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def _price_weighted_cost_proxy(year_df: pd.DataFrame, load_col: str, dt_hours: float) -> float:
    if "uk_price" not in year_df.columns or load_col not in year_df.columns:
        return np.nan

    load = pd.to_numeric(year_df[load_col], errors="coerce")
    price = pd.to_numeric(year_df["uk_price"], errors="coerce")
    valid = load.notna() & price.notna()
    if not bool(valid.any()):
        return np.nan

    return float((load[valid] * price[valid]).sum() * dt_hours)


def make_scenario_comparison_table(year_df: pd.DataFrame, dt_hours: float) -> pd.DataFrame:
    original_peak = float(year_df["utilisation"].max())
    original_cost = _price_weighted_cost_proxy(year_df, "utilisation", dt_hours)

    scenarios = [
        ("10% Flex only", "10%", "No BESS", "load_flex_10"),
        ("25% Flex only", "25%", "No BESS", "load_flex_25"),
        ("10% Flex + 4h BESS", "10%", "4h", "load_10_flex_4h_batt"),
        ("10% Flex + 8h BESS", "10%", "8h", "load_10_flex_8h_batt"),
        ("25% Flex + 4h BESS", "25%", "4h", "load_25_flex_4h_batt"),
        ("25% Flex + 8h BESS", "25%", "8h", "load_25_flex_8h_batt"),
    ]

    rows: list[dict[str, object]] = []
    for scenario, flex_case, bess_duration, load_col in scenarios:
        residual_peak = float(year_df[load_col].max())
        scenario_cost = _price_weighted_cost_proxy(year_df, load_col, dt_hours)
        rows.append(
            {
                "scenario": scenario,
                "flex_case": flex_case,
                "bess_duration": bess_duration,
                "residual_peak_utilisation": residual_peak,
                "annual_peak_reduction_vs_original_percent": (
                    (original_peak - residual_peak) / original_peak * 100.0 if original_peak > 0 else np.nan
                ),
                "price_weighted_cost_reduction_vs_original_percent": (
                    (original_cost - scenario_cost) / original_cost * 100.0
                    if np.isfinite(original_cost) and np.isfinite(scenario_cost) and original_cost != 0
                    else np.nan
                ),
            }
        )

    out = pd.DataFrame(rows)
    numeric_cols = [
        "residual_peak_utilisation",
        "annual_peak_reduction_vs_original_percent",
        "price_weighted_cost_reduction_vs_original_percent",
    ]
    out[numeric_cols] = out[numeric_cols].round(4)
    return out


def run_rq3(
    mean_horizon_df: pd.DataFrame,
    year_df: pd.DataFrame,
    battery_daily_stats: pd.DataFrame,
    year: int,
    dt_hours: float,
    output_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig2_10 = output_dir / "figure2_flex_bess_10_intermediate.png"
    fig2_25 = output_dir / "figure2_flex_bess_25_intermediate.png"
    summary = output_dir / "bess_summary_intermediate.csv"
    scenario_table = output_dir / f"scenario_comparison_table_{year}.csv"

    battery_energy_4h = _lookup_battery_energy(battery_daily_stats, year, "10%_flex + 4h-Battery")
    battery_energy_8h = _lookup_battery_energy(battery_daily_stats, year, "10%_flex + 8h-Battery")

    _plot_figure2_mean_horizon(
        horizon_df=mean_horizon_df,
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
    _plot_figure2_mean_horizon(
        horizon_df=mean_horizon_df,
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

    make_bess_summary(mean_horizon_df, year_df, battery_daily_stats, year, dt_hours=dt_hours).to_csv(summary, index=False)
    make_scenario_comparison_table(year_df, dt_hours=dt_hours).to_csv(scenario_table, index=False)

    return fig2_10, fig2_25, summary, scenario_table
