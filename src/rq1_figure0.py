from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MIN_CENTRE_TIMESTEPS_FOR_VARIABILITY = 48 * 7
PEAK_CAP_PERCENTILES = (99, 95, 90, 85, 80)


def apply_granular_x_axis(ax: plt.Axes) -> None:
    ax.set_xlim(0, 47)
    ax.set_xticks(np.arange(0, 48, 4))
    ax.set_xticks(np.arange(0, 48, 1), minor=True)
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)])
    ax.grid(True, which="major", alpha=0.28)
    ax.grid(True, which="minor", alpha=0.12)


def _build_profiles(centres_year_df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    df = centres_year_df.copy()
    df["date"] = df["timestamp"].dt.floor("D")
    df["weekday"] = df["timestamp"].dt.weekday

    # Aggregate centre-level rows into one load profile per calendar day.
    day_profile = (
        df.groupby(["date", "halfhour_index"], observed=True)["utilisation"]
        .mean()
        .reset_index()
    )

    annual_mean = (
        day_profile.groupby("halfhour_index", observed=True)["utilisation"]
        .mean()
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )

    if annual_mean.isna().all():
        raise ValueError("Annual mean-day profile is empty after centre aggregation.")

    day_profile = day_profile.merge(
        df[["date", "weekday"]].drop_duplicates(),
        on="date",
        how="left",
    )

    weekday_df = day_profile[day_profile["weekday"] < 5]
    weekend_df = day_profile[day_profile["weekday"] >= 5]

    weekday_mean = (
        weekday_df.groupby("halfhour_index", observed=True)["utilisation"]
        .mean()
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )
    weekend_mean = (
        weekend_df.groupby("halfhour_index", observed=True)["utilisation"]
        .mean()
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )

    weekday_p10 = (
        weekday_df.groupby("halfhour_index", observed=True)["utilisation"]
        .quantile(0.10)
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )
    weekday_p90 = (
        weekday_df.groupby("halfhour_index", observed=True)["utilisation"]
        .quantile(0.90)
        .reindex(range(48))
        .interpolate(limit_direction="both")
    )

    return annual_mean, weekday_mean, weekend_mean, weekday_p10, weekday_p90


def _center_variability_metrics(centres_year_df: pd.DataFrame) -> pd.DataFrame:
    df = _add_timestamp_exact_1h_delta(centres_year_df)
    df["abs_delta_1h"] = df["delta_1h"].abs()

    rows: list[dict[str, float | int | str]] = []
    for centre, g in df.groupby("centre", observed=True, sort=True):
        util = g["utilisation"].to_numpy(dtype=float)
        deltas = g["abs_delta_1h"].dropna().to_numpy(dtype=float)

        mean_u = float(np.mean(util)) if util.size else 0.0
        std_u = float(np.std(util, ddof=0)) if util.size else 0.0
        peak_u = float(np.max(util)) if util.size else 0.0
        peak_to_avg = float(peak_u / mean_u) if mean_u > 0 else np.nan
        cv = float(std_u / mean_u) if mean_u > 0 else np.nan

        positive_deltas = deltas[deltas > 0.0]
        jump_threshold = float(np.quantile(positive_deltas, 0.90)) if positive_deltas.size else np.nan
        jump_count = (
            int(np.sum(deltas >= jump_threshold))
            if positive_deltas.size and not np.isnan(jump_threshold)
            else 0
        )
        mean_abs_delta_1h = float(np.mean(deltas)) if deltas.size else 0.0

        rows.append(
            {
                "centre": str(centre),
                "n_timesteps": int(len(g)),
                "n_valid_1h_deltas": int(deltas.size),
                "mean_utilisation": mean_u,
                "std_utilisation": std_u,
                "peak_utilisation": peak_u,
                "peak_to_average_ratio": peak_to_avg,
                "coefficient_of_variation": cv,
                "mean_abs_delta_1h": mean_abs_delta_1h,
                "jump_threshold_p90_abs_delta_1h": jump_threshold,
                "jump_count_1h": jump_count,
                "jump_share_1h": float(jump_count / deltas.size) if deltas.size else 0.0,
            }
        )

    metrics = pd.DataFrame(rows)

    if metrics.empty:
        raise ValueError("No centre-level metrics could be computed.")

    metrics = metrics.sort_values("coefficient_of_variation", ascending=False).reset_index(drop=True)
    metrics["sufficient_coverage"] = metrics["n_timesteps"] >= MIN_CENTRE_TIMESTEPS_FOR_VARIABILITY

    metrics["variability_bucket"] = "insufficient coverage"
    eligible = metrics["sufficient_coverage"] & metrics["coefficient_of_variation"].notna()
    if eligible.any():
        # Bucket centres by variability using percentile rank (stable even with tied CV values).
        cv_rank = metrics.loc[eligible, "coefficient_of_variation"].rank(method="average", pct=True)
        metrics.loc[eligible, "variability_bucket"] = pd.cut(
            cv_rank,
            bins=[0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0],
            labels=["low", "medium", "high"],
            include_lowest=True,
        ).astype(str)

    return metrics


def _aggregate_year_timeseries(centres_year_df: pd.DataFrame) -> pd.DataFrame:
    df = centres_year_df.copy()
    agg = (
        df.groupby("timestamp", observed=True)["utilisation"]
        .mean()
        .sort_index()
        .rename("utilisation")
        .reset_index()
    )
    agg["hour"] = agg["timestamp"].dt.hour.astype(int)
    agg["halfhour_index"] = (agg["timestamp"].dt.hour * 2 + (agg["timestamp"].dt.minute // 30)).astype(int)
    return agg


def _infer_dt_hours(timestamps: pd.Series) -> float:
    ts = pd.to_datetime(timestamps).dropna().sort_values()
    diffs = ts.diff().dropna().dt.total_seconds() / 3600.0
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return 0.5
    return float(diffs.median())


def _load_duration_frame(agg_df: pd.DataFrame) -> pd.DataFrame:
    util = np.sort(agg_df["utilisation"].to_numpy(dtype=float))[::-1]
    n = len(util)
    if n == 0:
        raise ValueError("Cannot build RQ1 load-duration frame from empty data.")
    return pd.DataFrame(
        {
            "highest_load_halfhours_included_percent": (np.arange(1, n + 1) / n) * 100.0,
            "utilisation": util,
        }
    )


def _top_fraction_metrics(util: np.ndarray, dt_hours: float, fraction: float) -> dict[str, float]:
    if util.size == 0:
        return {
            "interval_count": 0.0,
            "hours": 0.0,
            "share_of_total_energy_percent": np.nan,
            "share_of_above_mean_energy_percent": np.nan,
        }

    n_top = max(1, int(np.ceil(util.size * fraction)))
    ordered = np.sort(util)[::-1]
    top_vals = ordered[:n_top]
    total_energy = float(np.sum(util) * dt_hours)
    mean_util = float(np.mean(util))
    above_mean = np.maximum(util - mean_util, 0.0)
    top_above_mean = np.maximum(top_vals - mean_util, 0.0)
    above_mean_energy = float(np.sum(above_mean) * dt_hours)

    return {
        "interval_count": float(n_top),
        "hours": float(n_top * dt_hours),
        "share_of_total_energy_percent": float(np.sum(top_vals) * dt_hours / total_energy * 100.0)
        if total_energy > 0
        else np.nan,
        "share_of_above_mean_energy_percent": float(np.sum(top_above_mean) * dt_hours / above_mean_energy * 100.0)
        if above_mean_energy > 0
        else np.nan,
    }


def _peak_shaving_opportunity(agg_df: pd.DataFrame) -> pd.DataFrame:
    util = agg_df["utilisation"].to_numpy(dtype=float)
    if util.size == 0:
        raise ValueError("Cannot compute RQ1 peak-shaving opportunity from empty data.")

    dt_hours = _infer_dt_hours(agg_df["timestamp"])
    peak = float(np.max(util))
    rows: list[dict[str, float | int | str]] = []
    for percentile in PEAK_CAP_PERCENTILES:
        cap = float(np.quantile(util, percentile / 100.0))
        excess = np.maximum(util - cap, 0.0)
        intervals = int(np.count_nonzero(excess > 1e-12))
        peak_reduction = peak - cap
        rows.append(
            {
                "cap_percentile": f"p{percentile}",
                "cap_percentile_value": int(percentile),
                "cap_utilisation": cap,
                "intervals_above_cap": intervals,
                "hours_above_cap": float(intervals * dt_hours),
                "excess_utilisation_hours_to_shift": float(np.sum(excess) * dt_hours),
                "peak_reduction_utilisation": float(peak_reduction),
                "peak_reduction_percent_of_peak": float(peak_reduction / peak * 100.0) if peak > 0 else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _rq1_profile_summary(agg_df: pd.DataFrame, metrics_df: pd.DataFrame) -> pd.DataFrame:
    util = agg_df["utilisation"].to_numpy(dtype=float)
    if util.size == 0:
        raise ValueError("Cannot compute RQ1 profile summary from empty data.")

    dt_hours = _infer_dt_hours(agg_df["timestamp"])
    eligible_metrics = metrics_df[metrics_df["sufficient_coverage"]].copy()
    mean_util = float(np.mean(util))
    peak = float(np.max(util))

    row: dict[str, float | int] = {
        "n_halfhours": int(util.size),
        "covered_hours": float(util.size * dt_hours),
        "n_centres_total": int(metrics_df["centre"].nunique()),
        "n_centres_sufficient_coverage": int(metrics_df["sufficient_coverage"].sum()),
        "mean_utilisation": mean_util,
        "median_utilisation": float(np.median(util)),
        "std_utilisation": float(np.std(util, ddof=0)),
        "coefficient_of_variation": float(np.std(util, ddof=0) / mean_util) if mean_util > 0 else np.nan,
        "peak_utilisation": peak,
        "peak_to_average_ratio": float(peak / mean_util) if mean_util > 0 else np.nan,
        "p90_utilisation": float(np.quantile(util, 0.90)),
        "p95_utilisation": float(np.quantile(util, 0.95)),
        "p99_utilisation": float(np.quantile(util, 0.99)),
        "median_centre_cv": float(eligible_metrics["coefficient_of_variation"].median())
        if not eligible_metrics.empty
        else np.nan,
        "p90_centre_cv": float(eligible_metrics["coefficient_of_variation"].quantile(0.90))
        if not eligible_metrics.empty
        else np.nan,
        "mean_centre_mean_abs_delta_1h": float(eligible_metrics["mean_abs_delta_1h"].mean())
        if not eligible_metrics.empty
        else np.nan,
        "p95_centre_mean_abs_delta_1h": float(eligible_metrics["mean_abs_delta_1h"].quantile(0.95))
        if not eligible_metrics.empty
        else np.nan,
    }

    for label, fraction in [("top_1pct", 0.01), ("top_5pct", 0.05), ("top_10pct", 0.10)]:
        values = _top_fraction_metrics(util=util, dt_hours=dt_hours, fraction=fraction)
        for key, value in values.items():
            row[f"{label}_{key}"] = value

    return pd.DataFrame([row])


def _hourly_center_distribution(centres_year_df: pd.DataFrame) -> pd.DataFrame:
    df = centres_year_df.copy()
    df["hour"] = (df["halfhour_index"] // 2).astype(int)

    # For each centre and hour, annual average utilisation.
    center_hour = (
        df.groupby(["centre", "hour"], observed=True)["utilisation"]
        .mean()
        .reset_index()
    )
    return center_hour


def _center_hourly_delta_frame(centres_year_df: pd.DataFrame) -> pd.DataFrame:
    df = _add_timestamp_exact_1h_delta(centres_year_df)
    df = df.dropna(subset=["delta_1h"]).copy()
    df["abs_delta_1h"] = df["delta_1h"].abs()
    df["hour"] = (df["halfhour_index"] // 2).astype(int)

    return df[["centre", "timestamp", "hour", "delta_1h", "abs_delta_1h"]]


def _add_timestamp_exact_1h_delta(centres_year_df: pd.DataFrame) -> pd.DataFrame:
    df = centres_year_df.sort_values(["centre", "timestamp"]).copy()
    previous = df[["centre", "timestamp", "utilisation"]].copy()
    previous["timestamp"] = previous["timestamp"] + pd.Timedelta(hours=1)
    previous = previous.rename(columns={"utilisation": "utilisation_1h_prior"})
    df = df.merge(previous, on=["centre", "timestamp"], how="left")
    df["delta_1h"] = df["utilisation"] - df["utilisation_1h_prior"]
    return df


def plot_rq1_year_overview(
    centres_year_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    year: int,
    out_file: Path,
) -> None:
    agg = _aggregate_year_timeseries(centres_year_df)
    load_duration = _load_duration_frame(agg)
    peak_opportunity = _peak_shaving_opportunity(agg)
    deltas = _center_hourly_delta_frame(centres_year_df)
    util = agg["utilisation"].to_numpy(dtype=float)
    peak_threshold = float(np.quantile(util, 0.90))

    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    ax1, ax2, ax3, ax4 = axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]

    # Panel A: distribution of absolute 1h jumps by hour.
    box_data_jump = []
    for hour in range(24):
        vals = deltas.loc[deltas["hour"] == hour, "abs_delta_1h"].to_numpy(dtype=float)
        box_data_jump.append(vals if vals.size else np.array([0.0]))
    jump_axis_max = float(deltas["abs_delta_1h"].quantile(0.95) * 1.30) if not deltas.empty else 0.01
    ax1.boxplot(
        box_data_jump,
        positions=np.arange(24),
        widths=0.6,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "#c7dcef", "alpha": 0.8},
    )
    ax1.set_title(f"Variability: One-Hour Load Jump Distribution by Hour ({year})", fontsize=12, pad=10)
    ax1.set_xlabel("hour of day")
    ax1.set_ylabel("|delta_1h| utilisation")
    ax1.set_xticks(np.arange(0, 24, 2))
    ax1.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax1.set_ylim(0, max(0.012, jump_axis_max))
    ax1.grid(alpha=0.25)

    # Panel B: top of the annual load-duration curve.
    ax2.plot(
        load_duration["highest_load_halfhours_included_percent"],
        load_duration["utilisation"],
        color="#2f2f2f",
        linewidth=2.2,
    )
    threshold_colors = {99: "#756bb1", 95: "#3182bd", 90: "#31a354"}
    for percentile, color in threshold_colors.items():
        cap = float(np.quantile(util, percentile / 100.0))
        top_share = 100 - percentile
        ax2.axhline(cap, color=color, linewidth=1.2, linestyle="--", alpha=0.85)
        ax2.axvline(top_share, color=color, linewidth=1.0, linestyle=":", alpha=0.75)
        ax2.text(
            top_share + 0.35,
            cap,
            f"p{percentile}",
            color=color,
            fontsize=9,
            va="bottom",
        )
    ax2.set_xlim(0, 20)
    ax2.set_title("Peak Concentration: Highest-Load Half-Hours", fontsize=12, pad=10)
    ax2.set_xlabel("highest-load half-hours included (%)")
    ax2.set_ylabel("utilisation")
    ax2.grid(alpha=0.25)

    mean_util = float(np.mean(util))
    peak_util = float(np.max(util))
    top_10 = _top_fraction_metrics(util=util, dt_hours=_infer_dt_hours(agg["timestamp"]), fraction=0.10)
    summary_text = (
        f"peak/mean: {peak_util / mean_util:.2f}x\n"
        f"top 10% share of above-mean load: "
        f"{top_10['share_of_above_mean_energy_percent']:.1f}%"
    )
    ax2.text(
        0.98,
        0.95,
        summary_text,
        transform=ax2.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )

    # Panel C: timing of peak intervals.
    top_peak = agg[agg["utilisation"] >= peak_threshold].copy()
    peak_hour_share = (
        top_peak.groupby("hour", observed=True)
        .size()
        .reindex(range(24), fill_value=0)
        .astype(float)
    )
    if peak_hour_share.sum() > 0:
        peak_hour_share = peak_hour_share / peak_hour_share.sum() * 100.0
    ax3.bar(np.arange(24), peak_hour_share.to_numpy(dtype=float), color="#9ecae1", edgecolor="#4a6f8a")
    ax3.set_title("Peak Timing: Top 10% Load Intervals by Hour", fontsize=12, pad=10)
    ax3.set_xlabel("hour of day")
    ax3.set_ylabel("share of top-10% intervals (%)")
    ax3.set_xticks(np.arange(0, 24, 2))
    ax3.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax3.grid(axis="y", alpha=0.25)

    # Panel D: energy that would need to be shifted for peak caps.
    labels = peak_opportunity["cap_percentile"].tolist()
    x_pos = np.arange(len(labels))
    bars = ax4.bar(
        x_pos,
        peak_opportunity["excess_utilisation_hours_to_shift"].to_numpy(dtype=float),
        color="#74c476",
        edgecolor="#3f7f46",
        alpha=0.88,
        label="excess above cap",
    )
    ax4.set_title("Potential Flexibility: Peak-Shaving Opportunity", fontsize=12, pad=10)
    ax4.set_xlabel("target cap on annual load profile")
    ax4.set_ylabel("utilisation-hours above cap")
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(labels)
    ax4.grid(axis="y", alpha=0.25)

    ax4b = ax4.twinx()
    ax4b.plot(
        x_pos,
        peak_opportunity["peak_reduction_percent_of_peak"].to_numpy(dtype=float),
        color="#de2d26",
        marker="o",
        linewidth=2.0,
        label="peak reduction",
    )
    ax4b.set_ylabel("peak reduction (% of peak)")
    ax4b.tick_params(axis="y", colors="#8b1a16")

    for bar, hours in zip(bars, peak_opportunity["hours_above_cap"].to_numpy(dtype=float)):
        ax4.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{hours:.0f}h",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_rq1_year_overview_left_panels(
    centres_year_df: pd.DataFrame,
    year: int,
    out_file: Path,
) -> None:
    agg = _aggregate_year_timeseries(centres_year_df)
    peak_opportunity = _peak_shaving_opportunity(agg)
    deltas = _center_hourly_delta_frame(centres_year_df)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={"height_ratios": [1.15, 1.0]})

    box_data_jump = []
    for hour in range(24):
        vals = deltas.loc[deltas["hour"] == hour, "abs_delta_1h"].to_numpy(dtype=float)
        box_data_jump.append(vals if vals.size else np.array([0.0]))
    jump_axis_max = float(deltas["abs_delta_1h"].quantile(0.95) * 1.30) if not deltas.empty else 0.01

    ax1.boxplot(
        box_data_jump,
        positions=np.arange(24),
        widths=0.6,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "#c7dcef", "alpha": 0.8},
    )
    ax1.set_title(f"Variability: One-Hour Load Jump Distribution by Hour ({year})", fontsize=12, pad=10)
    ax1.set_xlabel("hour of day")
    ax1.set_ylabel("|delta_1h| utilisation")
    ax1.set_xticks(np.arange(0, 24, 2))
    ax1.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax1.set_ylim(0, max(0.012, jump_axis_max))
    ax1.grid(alpha=0.25)

    labels = peak_opportunity["cap_percentile"].tolist()
    y_pos = np.arange(len(labels))
    ax2.barh(
        y_pos,
        peak_opportunity["excess_utilisation_hours_to_shift"].to_numpy(dtype=float),
        color="#74c476",
        edgecolor="#3f7f46",
        alpha=0.88,
    )
    ax2.set_title("Potential Flexibility: Energy Above Candidate Peak Caps", fontsize=12, pad=10)
    ax2.set_xlabel("utilisation-hours above cap")
    ax2.set_ylabel("target cap")
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(labels)
    ax2.invert_yaxis()
    ax2.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_rq1_center_load_jump_detail(
    centres_year_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    year: int,
    out_file: Path,
) -> None:
    deltas = _center_hourly_delta_frame(centres_year_df)
    eligible_metrics = metrics_df[metrics_df["sufficient_coverage"]].copy()
    if eligible_metrics.empty:
        eligible_metrics = metrics_df.copy()

    # Mean absolute 1-hour jump by centre and hour (0-23).
    heatmap_df = (
        deltas.groupby(["centre", "hour"], observed=True)["abs_delta_1h"]
        .mean()
        .reset_index()
    )
    heatmap = heatmap_df.pivot(index="centre", columns="hour", values="abs_delta_1h")
    center_order = eligible_metrics.sort_values("mean_abs_delta_1h", ascending=False)["centre"].tolist()
    heatmap = heatmap.reindex(center_order)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 11), gridspec_kw={"height_ratios": [2.2, 1.6]})

    mat = heatmap.to_numpy(dtype=float)
    im = ax1.imshow(mat, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    cbar = fig.colorbar(im, ax=ax1, fraction=0.03, pad=0.02)
    cbar.set_label("mean |delta_1h|")

    ax1.set_title(f"RQ1.1 ({year}): One-Hour Load Jumps by Data Centre and Hour", fontsize=13, pad=10)
    ax1.set_xlabel("hour of day")
    ax1.set_ylabel("data centre (sorted by mean |delta_1h|)")
    ax1.set_xticks(np.arange(0, 24, 2))
    ax1.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])

    # Show only a subset of centre labels for readability when many centres exist.
    if len(center_order) <= 20:
        yticks = np.arange(len(center_order))
    else:
        step = max(1, len(center_order) // 20)
        yticks = np.arange(0, len(center_order), step)
    ax1.set_yticks(yticks)
    ax1.set_yticklabels([center_order[i] for i in yticks], fontsize=7)

    # Top centres: hourly jump profile lines to compare centre-specific patterns.
    top_centres = eligible_metrics.sort_values("mean_abs_delta_1h", ascending=False)["centre"].head(10).tolist()
    for centre in top_centres:
        profile = (
            deltas[deltas["centre"] == centre]
            .groupby("hour", observed=True)["abs_delta_1h"]
            .mean()
            .reindex(range(24))
            .interpolate(limit_direction="both")
        )
        ax2.plot(np.arange(24), profile.to_numpy(dtype=float), linewidth=1.7, alpha=0.95, label=str(centre))

    ax2.set_title("Top 10 Centres: Hourly One-Hour Jump Profiles", fontsize=12, pad=10)
    ax2.set_xlabel("hour of day")
    ax2.set_ylabel("mean |delta_1h|")
    ax2.set_xticks(np.arange(0, 24, 2))
    ax2.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax2.grid(alpha=0.25)
    ax2.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, fontsize=8)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def run_rq1(
    centres_year_df: pd.DataFrame,
    year: int,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    figure_file = output_dir / "figure0_intro_annual_mean_day_all_centres.png"
    figure_file_left = output_dir / "figure0_intro_annual_mean_day_all_centres_left.png"
    figure_file_center_jumps = output_dir / f"figure0_1_rq1_center_load_jumps_{year}.png"
    metrics_file = output_dir / f"rq1_center_variability_metrics_{year}.csv"
    bucket_file = output_dir / f"rq1_center_variability_bucket_summary_{year}.csv"
    profile_summary_file = output_dir / f"rq1_profile_answer_summary_{year}.csv"
    peak_opportunity_file = output_dir / f"rq1_peak_shaving_opportunity_{year}.csv"

    metrics = _center_variability_metrics(centres_year_df)
    metrics.to_csv(metrics_file, index=False)

    aggregate_profile = _aggregate_year_timeseries(centres_year_df)
    _rq1_profile_summary(aggregate_profile, metrics).to_csv(profile_summary_file, index=False)
    _peak_shaving_opportunity(aggregate_profile).to_csv(peak_opportunity_file, index=False)

    plot_rq1_year_overview(
        centres_year_df=centres_year_df,
        metrics_df=metrics,
        year=year,
        out_file=figure_file,
    )
    plot_rq1_year_overview_left_panels(
        centres_year_df=centres_year_df,
        year=year,
        out_file=figure_file_left,
    )
    plot_rq1_center_load_jump_detail(
        centres_year_df=centres_year_df,
        metrics_df=metrics,
        year=year,
        out_file=figure_file_center_jumps,
    )

    eligible_metrics = metrics[metrics["sufficient_coverage"]].copy()
    bucket_summary = (
        eligible_metrics.groupby("variability_bucket", observed=True)
        .agg(
            n_centres=("centre", "count"),
            mean_cv=("coefficient_of_variation", "mean"),
            mean_abs_delta_1h=("mean_abs_delta_1h", "mean"),
            mean_jump_share_1h=("jump_share_1h", "mean"),
            mean_peak_to_average=("peak_to_average_ratio", "mean"),
        )
        .reset_index()
    )
    bucket_summary.to_csv(bucket_file, index=False)

    return [
        figure_file,
        figure_file_left,
        figure_file_center_jumps,
        metrics_file,
        bucket_file,
        profile_summary_file,
        peak_opportunity_file,
    ]
