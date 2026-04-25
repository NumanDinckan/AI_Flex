from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


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

        jump_threshold = float(np.quantile(deltas, 0.90)) if deltas.size else np.nan
        jump_count = int(np.sum(deltas >= jump_threshold)) if deltas.size and not np.isnan(jump_threshold) else 0
        mean_abs_delta_1h = float(np.mean(deltas)) if deltas.size else 0.0

        rows.append(
            {
                "centre": str(centre),
                "n_timesteps": int(len(g)),
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

    # Bucket centres by variability using percentile rank (stable even with tied CV values).
    cv_rank = metrics["coefficient_of_variation"].rank(method="average", pct=True)
    metrics["variability_bucket"] = pd.cut(
        cv_rank,
        bins=[0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0],
        labels=["low", "medium", "high"],
        include_lowest=True,
    )

    return metrics


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
    annual_mean, weekday_mean, weekend_mean, weekday_p10, weekday_p90 = _build_profiles(centres_year_df)

    center_hour = _hourly_center_distribution(centres_year_df)
    deltas = _center_hourly_delta_frame(centres_year_df)

    fig, axs = plt.subplots(2, 2, figsize=(16, 12))
    ax1, ax2, ax3, ax4 = axs[0, 0], axs[0, 1], axs[1, 0], axs[1, 1]

    x = np.arange(48)
    ax1.fill_between(
        x,
        weekday_p10.to_numpy(dtype=float),
        weekday_p90.to_numpy(dtype=float),
        color="#9ecae1",
        alpha=0.22,
        label="Weekday p10-p90 (all 2025 weekdays)",
    )
    ax1.plot(x, annual_mean.to_numpy(dtype=float), color="#2f2f2f", linewidth=2.4, label="Annual mean day")
    ax1.plot(x, weekday_mean.to_numpy(dtype=float), color="#1f77b4", linewidth=2.1, label="Weekday mean")
    ax1.plot(x, weekend_mean.to_numpy(dtype=float), color="#ff7f0e", linewidth=2.0, label="Weekend mean")

    ax1.set_title(f"RQ1 ({year}): Annual Mean-Day Load Shape", fontsize=13, pad=12)
    ax1.set_ylabel("utilisation")
    ax1.set_xlabel("time of day (HH:MM)")
    apply_granular_x_axis(ax1)
    ax1.legend(loc="best", frameon=False)

    # Panel B: cross-centre level distribution by hour.
    box_data_util = []
    for hour in range(24):
        vals = center_hour.loc[center_hour["hour"] == hour, "utilisation"].to_numpy(dtype=float)
        box_data_util.append(vals if vals.size else np.array([0.0]))

    ax2.boxplot(
        box_data_util,
        positions=np.arange(24),
        widths=0.6,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "#d9d9d9", "alpha": 0.7},
    )
    ax2.set_title(f"Cross-Centre Variability by Hour ({year}, annual centre-level averages)", fontsize=12, pad=10)
    ax2.set_xlabel("hour of day")
    ax2.set_ylabel("utilisation")
    ax2.set_xticks(np.arange(0, 24, 2))
    ax2.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax2.grid(alpha=0.25)

    # Panel C: distribution of absolute 1h jumps by hour.
    box_data_jump = []
    for hour in range(24):
        vals = deltas.loc[deltas["hour"] == hour, "abs_delta_1h"].to_numpy(dtype=float)
        box_data_jump.append(vals if vals.size else np.array([0.0]))
    ax3.boxplot(
        box_data_jump,
        positions=np.arange(24),
        widths=0.6,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "#c7dcef", "alpha": 0.8},
    )
    ax3.set_title(f"One-Hour Load Jump Distribution by Hour ({year})", fontsize=12, pad=10)
    ax3.set_xlabel("hour of day")
    ax3.set_ylabel("|delta_1h| utilisation")
    ax3.set_xticks(np.arange(0, 24, 2))
    ax3.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax3.grid(alpha=0.25)

    # Panel D: per-centre jump-count ranking.
    top = metrics_df.sort_values("jump_count_1h", ascending=False).head(20).copy()
    color_map = {"low": "#8dd3c7", "medium": "#80b1d3", "high": "#fb8072"}
    colors = [color_map.get(str(v), "#bdbdbd") for v in top["variability_bucket"]]

    ax4.bar(np.arange(len(top)), top["jump_count_1h"].to_numpy(dtype=float), color=colors, alpha=0.9)
    ax4.set_title("Top 20 Data Centres by One-Hour Jump Count", fontsize=12, pad=10)
    ax4.set_ylabel("jump_count_1h")
    ax4.set_xticks(np.arange(len(top)))
    ax4.set_xticklabels(top["centre"].tolist(), rotation=70, ha="right", fontsize=8)
    ax4.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out_file, dpi=220)
    plt.close(fig)


def plot_rq1_year_overview_left_panels(
    centres_year_df: pd.DataFrame,
    year: int,
    out_file: Path,
) -> None:
    annual_mean, weekday_mean, weekend_mean, weekday_p10, weekday_p90 = _build_profiles(centres_year_df)
    deltas = _center_hourly_delta_frame(centres_year_df)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={"height_ratios": [1.15, 1.0]})

    x = np.arange(48)
    ax1.fill_between(
        x,
        weekday_p10.to_numpy(dtype=float),
        weekday_p90.to_numpy(dtype=float),
        color="#9ecae1",
        alpha=0.22,
        label="Weekday p10-p90 (all 2025 weekdays)",
    )
    ax1.plot(x, annual_mean.to_numpy(dtype=float), color="#2f2f2f", linewidth=2.4, label="Annual mean day")
    ax1.plot(x, weekday_mean.to_numpy(dtype=float), color="#1f77b4", linewidth=2.1, label="Weekday mean")
    ax1.plot(x, weekend_mean.to_numpy(dtype=float), color="#ff7f0e", linewidth=2.0, label="Weekend mean")
    ax1.set_title(f"RQ1 ({year}): Annual Mean-Day Load Shape", fontsize=13, pad=12)
    ax1.set_ylabel("utilisation")
    ax1.set_xlabel("time of day (HH:MM)")
    apply_granular_x_axis(ax1)
    ax1.legend(loc="best", frameon=False)

    box_data_jump = []
    for hour in range(24):
        vals = deltas.loc[deltas["hour"] == hour, "abs_delta_1h"].to_numpy(dtype=float)
        box_data_jump.append(vals if vals.size else np.array([0.0]))

    ax2.boxplot(
        box_data_jump,
        positions=np.arange(24),
        widths=0.6,
        showfliers=False,
        patch_artist=True,
        boxprops={"facecolor": "#c7dcef", "alpha": 0.8},
    )
    ax2.set_title(f"One-Hour Load Jump Distribution by Hour ({year})", fontsize=12, pad=10)
    ax2.set_xlabel("hour of day")
    ax2.set_ylabel("|delta_1h| utilisation")
    ax2.set_xticks(np.arange(0, 24, 2))
    ax2.set_xticklabels([f"{h:02d}" for h in range(0, 24, 2)])
    ax2.grid(alpha=0.25)

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

    # Mean absolute 1-hour jump by centre and hour (0-23).
    heatmap_df = (
        deltas.groupby(["centre", "hour"], observed=True)["abs_delta_1h"]
        .mean()
        .reset_index()
    )
    heatmap = heatmap_df.pivot(index="centre", columns="hour", values="abs_delta_1h")
    center_order = metrics_df.sort_values("jump_count_1h", ascending=False)["centre"].tolist()
    heatmap = heatmap.reindex(center_order)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 11), gridspec_kw={"height_ratios": [2.2, 1.6]})

    mat = heatmap.to_numpy(dtype=float)
    im = ax1.imshow(mat, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    cbar = fig.colorbar(im, ax=ax1, fraction=0.03, pad=0.02)
    cbar.set_label("mean |delta_1h|")

    ax1.set_title(f"RQ1.1 ({year}): One-Hour Load Jumps by Data Centre and Hour", fontsize=13, pad=10)
    ax1.set_xlabel("hour of day")
    ax1.set_ylabel("data centre (sorted by jump_count_1h)")
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
    top_centres = metrics_df.sort_values("jump_count_1h", ascending=False)["centre"].head(10).tolist()
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

    metrics = _center_variability_metrics(centres_year_df)
    metrics.to_csv(metrics_file, index=False)

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

    bucket_summary = (
        metrics.groupby("variability_bucket", observed=True)
        .agg(
            n_centres=("centre", "count"),
            mean_cv=("coefficient_of_variation", "mean"),
            mean_jump_share_1h=("jump_share_1h", "mean"),
            mean_peak_to_average=("peak_to_average_ratio", "mean"),
        )
        .reset_index()
    )
    bucket_summary.to_csv(bucket_file, index=False)

    return [figure_file, figure_file_left, figure_file_center_jumps, metrics_file, bucket_file]
