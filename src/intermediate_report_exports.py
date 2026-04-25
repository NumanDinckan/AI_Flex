from __future__ import annotations

import argparse
import gzip
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from bess_method import simulate_bess
from flex_method import add_flex
from rq1_figure0 import run_rq1
from rq2_figure1 import run_rq2
from rq3_figure2 import run_rq3


REQUIRED_COLUMNS = [
    "cleansed_voltage_level",
    "anonymised_data_centre_name",
    "dc_type",
    "utc_timestamp",
    "hh_utilisation_ratio",
]

DEFAULT_PRICE_INPUT = Path("data/raw/United Kingdom.csv")
DEFAULT_PRICE_TIMESTAMP_COL = "Datetime (UTC)"
DEFAULT_PRICE_COL = "Price (EUR/MWhe)"


@dataclass
class CoreAnalysisResults:
    battery_daily_stats: pd.DataFrame
    flex_daily_stats: pd.DataFrame
    timeseries: pd.DataFrame


@dataclass
class ReportContext:
    year: int
    min_utilisation: float
    dt_hours: float
    output_dir: Path
    mean_day_df: pd.DataFrame
    mean_48h_df: pd.DataFrame
    year_df: pd.DataFrame
    centres_year_df: pd.DataFrame | None
    flex_daily_stats: pd.DataFrame
    battery_daily_stats: pd.DataFrame
    price_input: Path | None


def get_rq_output_dir(base_output_dir: Path, rq_name: str) -> Path:
    out = base_output_dir / rq_name
    out.mkdir(parents=True, exist_ok=True)
    return out


def add_common_report_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--input", type=str, default="data/raw/ukpn-data-centre-demand-profiles.csv")
    parser.add_argument("--output-dir", type=str, default="outputs")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dt-hours", type=float, default=0.5)
    parser.add_argument("--dc-type", type=str, default="")
    parser.add_argument("--voltage-level", type=str, default="High Voltage Import")
    parser.add_argument("--centres", type=str, default="")
    parser.add_argument("--price-input", type=str, default="")
    parser.add_argument("--price-timestamp-col", type=str, default=DEFAULT_PRICE_TIMESTAMP_COL)
    parser.add_argument("--price-col", type=str, default=DEFAULT_PRICE_COL)
    parser.add_argument("--price-tolerance-minutes", type=float, default=30.0)
    parser.add_argument(
        "--min-utilisation",
        type=float,
        default=0.1,
        help="Keep only rows with hh_utilisation_ratio strictly greater than this threshold.",
    )
    parser.add_argument("--chunksize", type=int, default=750_000)
    return parser


def detect_delimiter(csv_path: Path) -> str:
    if csv_path.suffix == ".gz":
        open_fn = gzip.open
        open_args = (csv_path,)
    else:
        open_fn = csv_path.open
        open_args = ()

    with open_fn(*open_args, mode="rt", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
    return ";" if first_line.count(";") > first_line.count(",") else ","


def parse_centre_list(raw: str) -> set[str] | None:
    if not raw:
        return None
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return values or None


def load_aggregated_timeseries(
    csv_path: Path,
    dc_type: str | None,
    voltage_level: str | None,
    centres: set[str] | None,
    min_utilisation: float,
    chunksize: int,
) -> pd.DataFrame:
    delimiter = detect_delimiter(csv_path)

    sum_by_ts = pd.Series(dtype="float64")
    count_by_ts = pd.Series(dtype="float64")

    reader = pd.read_csv(
        csv_path,
        usecols=REQUIRED_COLUMNS,
        delimiter=delimiter,
        encoding="utf-8-sig",
        chunksize=chunksize,
        dtype={
            "cleansed_voltage_level": "string",
            "anonymised_data_centre_name": "string",
            "dc_type": "string",
            "utc_timestamp": "string",
            "hh_utilisation_ratio": "float64",
        },
    )

    for chunk in reader:
        if dc_type:
            chunk = chunk[chunk["dc_type"] == dc_type]
        if voltage_level:
            chunk = chunk[chunk["cleansed_voltage_level"] == voltage_level]
        if centres:
            chunk = chunk[chunk["anonymised_data_centre_name"].isin(centres)]
        if chunk.empty:
            continue

        chunk["utc_timestamp"] = pd.to_datetime(chunk["utc_timestamp"], errors="coerce")
        chunk["hh_utilisation_ratio"] = pd.to_numeric(chunk["hh_utilisation_ratio"], errors="coerce")
        chunk = chunk.dropna(subset=["utc_timestamp", "hh_utilisation_ratio"])
        chunk = chunk[chunk["hh_utilisation_ratio"] > min_utilisation]
        if chunk.empty:
            continue

        grouped = chunk.groupby("utc_timestamp", sort=False)["hh_utilisation_ratio"].agg(["sum", "count"])
        sum_by_ts = sum_by_ts.add(grouped["sum"], fill_value=0.0)
        count_by_ts = count_by_ts.add(grouped["count"], fill_value=0.0)

    if count_by_ts.empty:
        raise ValueError("No valid rows found after filtering.")

    utilisation = (sum_by_ts / count_by_ts).sort_index()
    return utilisation.rename("utilisation").rename_axis("timestamp").reset_index()


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values("timestamp").copy()
    out["date"] = out["timestamp"].dt.floor("D")
    out["year"] = out["timestamp"].dt.year.astype(int)
    out["month"] = out["timestamp"].dt.month.astype(int)
    out["weekday"] = out["timestamp"].dt.weekday.astype(int)
    out["halfhour_index"] = (out["timestamp"].dt.hour * 2 + (out["timestamp"].dt.minute // 30)).astype(int)
    return out


def add_baselines(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    mean_day_base = (
        out.groupby(["year", "halfhour_index"], observed=True)["utilisation"]
        .mean()
        .rename("mean_day_base")
    )
    out = out.join(mean_day_base, on=["year", "halfhour_index"])

    med_base = (
        out.groupby(["year", "weekday", "halfhour_index"], observed=True)["utilisation"]
        .median()
        .rename("med_base")
    )
    out = out.join(med_base, on=["year", "weekday", "halfhour_index"])

    med_base_sens = (
        out.groupby(["year", "month", "weekday", "halfhour_index"], observed=True)["utilisation"]
        .median()
        .rename("med_base_sensitivity")
    )
    out = out.join(med_base_sens, on=["year", "month", "weekday", "halfhour_index"])

    return out


def build_annual_mean_day(year_df: pd.DataFrame, year: int, dt_hours: float) -> pd.DataFrame:
    if year_df.empty:
        raise ValueError(f"No rows found for annual mean-day profile in year {year}.")

    steps_per_day = int(round(24.0 / dt_hours))
    index = range(steps_per_day)
    numeric_cols = [
        col
        for col in year_df.columns
        if pd.api.types.is_numeric_dtype(year_df[col])
        and col not in {"year", "month", "weekday", "halfhour_index"}
    ]

    profile = year_df.groupby("halfhour_index", observed=True)[numeric_cols].mean().reindex(index)
    profile = profile.interpolate(limit_direction="both")
    profile = profile.reset_index().rename(columns={"index": "halfhour_index"})

    base_date = pd.Timestamp(f"{year}-01-01")
    profile["timestamp"] = [base_date + pd.Timedelta(hours=i * dt_hours) for i in index]
    profile["date"] = base_date
    profile["year"] = year
    profile["month"] = 0
    profile["weekday"] = -1
    profile["profile_basis"] = "annual_mean_day"
    return profile


def build_annual_mean_horizon(
    year_df: pd.DataFrame,
    year: int,
    dt_hours: float,
    horizon_hours: float = 48.0,
) -> pd.DataFrame:
    if year_df.empty:
        raise ValueError(f"No rows found for annual mean-horizon profile in year {year}.")

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
        if not window.empty:
            windows.append(window[["horizon_index", *numeric_cols]])

    if windows:
        stacked = pd.concat(windows, ignore_index=True)
        profile = stacked.groupby("horizon_index", observed=True)[numeric_cols].mean().reindex(range(steps))
    else:
        mean_day = build_annual_mean_day(year_df, year, dt_hours)
        repeated = pd.concat([mean_day[numeric_cols]] * int(round(horizon_hours / 24.0)), ignore_index=True)
        profile = repeated.iloc[:steps].copy()
        profile.index.name = "horizon_index"

    profile = profile.interpolate(limit_direction="both")
    profile = profile.reset_index()
    profile["horizon_hour"] = profile["horizon_index"] * dt_hours
    profile["halfhour_index"] = profile["horizon_index"] % day_steps
    profile["timestamp"] = pd.NaT
    profile["date"] = pd.NaT
    profile["year"] = year
    profile["month"] = 0
    profile["weekday"] = -1
    profile["profile_basis"] = f"annual_mean_{int(horizon_hours)}h_horizon"
    return profile


def run_core_analysis(df: pd.DataFrame, dt_hours: float) -> CoreAnalysisResults:
    ts = prepare_features(df)
    ts = add_baselines(ts)
    ts, flex_daily_stats = add_flex(ts, dt_hours=dt_hours)
    price_col = "uk_price" if "uk_price" in ts.columns else None
    ts, battery_daily_stats = simulate_bess(ts, step_h=dt_hours, price_col=price_col)

    return CoreAnalysisResults(
        battery_daily_stats=battery_daily_stats,
        flex_daily_stats=flex_daily_stats,
        timeseries=ts,
    )


def load_centre_year_timeseries(
    csv_path: Path,
    year: int,
    target_date: pd.Timestamp | None,
    dc_type: str | None,
    voltage_level: str | None,
    min_utilisation: float,
    chunksize: int,
) -> pd.DataFrame:
    delimiter = detect_delimiter(csv_path)
    parts: list[pd.DataFrame] = []

    reader = pd.read_csv(
        csv_path,
        usecols=REQUIRED_COLUMNS,
        delimiter=delimiter,
        encoding="utf-8-sig",
        chunksize=chunksize,
        dtype={
            "cleansed_voltage_level": "string",
            "anonymised_data_centre_name": "string",
            "dc_type": "string",
            "utc_timestamp": "string",
            "hh_utilisation_ratio": "float64",
        },
    )

    for chunk in reader:
        if dc_type:
            chunk = chunk[chunk["dc_type"] == dc_type]
        if voltage_level:
            chunk = chunk[chunk["cleansed_voltage_level"] == voltage_level]
        if chunk.empty:
            continue

        chunk["timestamp"] = pd.to_datetime(chunk["utc_timestamp"], errors="coerce")
        chunk["utilisation"] = pd.to_numeric(chunk["hh_utilisation_ratio"], errors="coerce")
        chunk = chunk.dropna(subset=["timestamp", "utilisation", "anonymised_data_centre_name"])
        chunk = chunk[chunk["utilisation"] > min_utilisation]
        if chunk.empty:
            continue

        chunk = chunk[chunk["timestamp"].dt.year == year]
        if chunk.empty:
            continue
        if target_date is not None:
            chunk = chunk[chunk["timestamp"].dt.floor("D") == pd.Timestamp(target_date)]
            if chunk.empty:
                continue

        out = chunk.loc[:, ["timestamp", "anonymised_data_centre_name", "utilisation"]].copy()
        out = out.rename(columns={"anonymised_data_centre_name": "centre"})
        out["halfhour_index"] = (out["timestamp"].dt.hour * 2 + (out["timestamp"].dt.minute // 30)).astype(int)
        parts.append(out)

    if not parts:
        raise ValueError(f"No centre-level rows found for year {year} after filtering.")

    return pd.concat(parts, ignore_index=True)


def load_price_timeseries(
    csv_path: Path,
    timestamp_col: str,
    price_col: str,
) -> pd.DataFrame:
    delimiter = detect_delimiter(csv_path)
    prices = pd.read_csv(
        csv_path,
        usecols=[timestamp_col, price_col],
        delimiter=delimiter,
        encoding="utf-8-sig",
    )
    prices = prices.rename(columns={timestamp_col: "timestamp", price_col: "uk_price"})
    prices["timestamp"] = pd.to_datetime(prices["timestamp"], errors="coerce")
    prices["uk_price"] = pd.to_numeric(prices["uk_price"], errors="coerce")
    prices = prices.dropna(subset=["timestamp", "uk_price"])
    if prices.empty:
        raise ValueError(f"No usable price rows found in {csv_path}.")
    return prices.groupby("timestamp", as_index=False)["uk_price"].mean().sort_values("timestamp")


def attach_price_signal(
    load_df: pd.DataFrame,
    price_df: pd.DataFrame,
    tolerance_minutes: float,
) -> pd.DataFrame:
    tolerance = pd.Timedelta(minutes=tolerance_minutes)
    out = pd.merge_asof(
        load_df.sort_values("timestamp"),
        price_df.sort_values("timestamp"),
        on="timestamp",
        direction="nearest",
        tolerance=tolerance,
    )
    matched = int(out["uk_price"].notna().sum())
    if matched == 0:
        raise ValueError("Price input did not match any load timestamps within the configured tolerance.")
    return out


def build_context(args: argparse.Namespace, include_rq1_data: bool) -> ReportContext:
    if args.dt_hours <= 0:
        raise ValueError("--dt-hours must be positive.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_csv = Path(args.input)
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = load_aggregated_timeseries(
        csv_path=input_csv,
        dc_type=args.dc_type.strip() if args.dc_type else None,
        voltage_level=args.voltage_level.strip() if args.voltage_level else None,
        centres=parse_centre_list(args.centres),
        min_utilisation=args.min_utilisation,
        chunksize=args.chunksize,
    )

    price_input = Path(args.price_input) if args.price_input else (DEFAULT_PRICE_INPUT if DEFAULT_PRICE_INPUT.exists() else None)
    if price_input is not None:
        price_csv = price_input
        if not price_csv.exists():
            raise FileNotFoundError(f"Price CSV not found: {price_csv}")
        price_df = load_price_timeseries(
            csv_path=price_csv,
            timestamp_col=args.price_timestamp_col,
            price_col=args.price_col,
        )
        df = attach_price_signal(
            load_df=df,
            price_df=price_df,
            tolerance_minutes=args.price_tolerance_minutes,
        )

    results = run_core_analysis(df, dt_hours=args.dt_hours)

    available_years = sorted(int(year) for year in results.timeseries["year"].dropna().unique())
    if args.year not in available_years:
        available = available_years
        raise ValueError(f"Requested year {args.year} not available. Available years: {available}")

    year_df = results.timeseries[results.timeseries["year"] == args.year].sort_values("timestamp").copy()
    mean_day_df = build_annual_mean_day(year_df=year_df, year=args.year, dt_hours=args.dt_hours)
    mean_48h_df = build_annual_mean_horizon(year_df=year_df, year=args.year, dt_hours=args.dt_hours, horizon_hours=48.0)
    flex_daily_stats = results.flex_daily_stats[results.flex_daily_stats["year"] == args.year].copy()

    if mean_day_df.empty:
        raise ValueError(f"No annual mean-day profile could be built for year {args.year}.")

    centres_year_df: pd.DataFrame | None = None
    if include_rq1_data:
        centres_year_df = load_centre_year_timeseries(
            csv_path=input_csv,
            year=args.year,
            target_date=None,
            dc_type=args.dc_type.strip() if args.dc_type else None,
            voltage_level=args.voltage_level.strip() if args.voltage_level else None,
            min_utilisation=args.min_utilisation,
            chunksize=args.chunksize,
        )

    return ReportContext(
        year=args.year,
        min_utilisation=args.min_utilisation,
        dt_hours=args.dt_hours,
        output_dir=output_dir,
        mean_day_df=mean_day_df,
        mean_48h_df=mean_48h_df,
        year_df=year_df,
        centres_year_df=centres_year_df,
        flex_daily_stats=flex_daily_stats,
        battery_daily_stats=results.battery_daily_stats,
        price_input=price_input,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run intermediate report outputs for RQ1/RQ2/RQ3.")
    add_common_report_args(parser)
    parser.add_argument(
        "--rq",
        choices=["all", "rq1", "rq2", "rq3"],
        default="all",
        help="Select which research-question output set to generate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    include_rq1_data = args.rq in {"all", "rq1"}
    context = build_context(args, include_rq1_data=include_rq1_data)

    saved_files: list[str] = []

    if args.rq in {"all", "rq1"}:
        if context.centres_year_df is None:
            raise ValueError("RQ1 selected but centre-level year data is unavailable.")
        rq1_output_dir = get_rq_output_dir(context.output_dir, "rq1")
        rq1_files = run_rq1(
            centres_year_df=context.centres_year_df,
            year=context.year,
            output_dir=rq1_output_dir,
        )
        saved_files.extend([str(p.resolve()) for p in rq1_files])

    if args.rq in {"all", "rq2"}:
        rq2_output_dir = get_rq_output_dir(context.output_dir, "rq2")
        rq2_files = run_rq2(
            mean_day_df=context.mean_day_df,
            year_df=context.year_df,
            flex_daily_stats=context.flex_daily_stats,
            year=context.year,
            dt_hours=context.dt_hours,
            output_dir=rq2_output_dir,
        )
        saved_files.extend([str(path.resolve()) for path in rq2_files])

    if args.rq in {"all", "rq3"}:
        rq3_output_dir = get_rq_output_dir(context.output_dir, "rq3")
        fig10, fig25, table = run_rq3(
            mean_horizon_df=context.mean_48h_df,
            year_df=context.year_df,
            battery_daily_stats=context.battery_daily_stats,
            year=context.year,
            dt_hours=context.dt_hours,
            output_dir=rq3_output_dir,
        )
        saved_files.extend([str(fig10.resolve()), str(fig25.resolve()), str(table.resolve())])

    print(f"RQ selection: {args.rq}")
    print(f"Year selected: {context.year}")
    print("RQ1/RQ2 profile basis: annual mean day")
    print("RQ3 profile basis: annual mean 48-hour horizon")
    print(f"Price input: {context.price_input if context.price_input is not None else 'none'}")
    print(f"Min utilisation filter: > {context.min_utilisation}")
    print(f"dt_hours: {context.dt_hours}")
    for path in saved_files:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
