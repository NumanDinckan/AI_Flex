from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

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


@dataclass
class CoreAnalysisResults:
    battery_daily_stats: pd.DataFrame
    flex_daily_stats: pd.DataFrame
    timeseries: pd.DataFrame
    characteristic_days: dict[int, pd.Timestamp]


@dataclass
class ReportContext:
    year: int
    min_utilisation: float
    dt_hours: float
    output_dir: Path
    characteristic_day: pd.Timestamp
    day_df: pd.DataFrame
    year_df: pd.DataFrame
    centres_year_df: pd.DataFrame | None
    flex_daily_stats: pd.DataFrame
    battery_daily_stats: pd.DataFrame


def add_common_report_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--input", type=str, default="data/raw/ukpn-data-centre-demand-profiles.csv")
    parser.add_argument("--output-dir", type=str, default=".")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--dt-hours", type=float, default=0.5)
    parser.add_argument("--dc-type", type=str, default="")
    parser.add_argument("--voltage-level", type=str, default="High Voltage Import")
    parser.add_argument("--centres", type=str, default="")
    parser.add_argument(
        "--min-utilisation",
        type=float,
        default=0.1,
        help="Keep only rows with hh_utilisation_ratio strictly greater than this threshold.",
    )
    parser.add_argument("--chunksize", type=int, default=750_000)
    return parser


def detect_delimiter(csv_path: Path) -> str:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
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


def find_characteristic_days(df: pd.DataFrame) -> dict[int, pd.Timestamp]:
    daily_peaks = (
        df.groupby(["year", "date"], as_index=False)["utilisation"].max().rename(columns={"utilisation": "day_peak"})
    )

    characteristic: dict[int, pd.Timestamp] = {}
    for year, g in daily_peaks.groupby("year", sort=True):
        idx = g["day_peak"].idxmax()
        characteristic[int(year)] = pd.Timestamp(g.loc[idx, "date"])

    return characteristic


def run_core_analysis(df: pd.DataFrame, dt_hours: float) -> CoreAnalysisResults:
    ts = prepare_features(df)
    ts = add_baselines(ts)
    ts, flex_daily_stats = add_flex(ts, dt_hours=dt_hours)
    ts, battery_daily_stats = simulate_bess(ts)
    characteristic_days = find_characteristic_days(ts)

    return CoreAnalysisResults(
        battery_daily_stats=battery_daily_stats,
        flex_daily_stats=flex_daily_stats,
        timeseries=ts,
        characteristic_days=characteristic_days,
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

    results = run_core_analysis(df, dt_hours=args.dt_hours)

    if args.year not in results.characteristic_days:
        available = sorted(results.characteristic_days.keys())
        raise ValueError(f"Requested year {args.year} not available. Available years: {available}")

    characteristic_day = results.characteristic_days[args.year]

    day_df = results.timeseries[
        (results.timeseries["year"] == args.year) & (results.timeseries["date"] == characteristic_day)
    ].sort_values("halfhour_index")
    year_df = results.timeseries[results.timeseries["year"] == args.year].sort_values("timestamp").copy()
    flex_daily_stats = results.flex_daily_stats[results.flex_daily_stats["year"] == args.year].copy()

    if day_df.empty:
        raise ValueError(f"No characteristic-day data found for year {args.year}.")

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
        characteristic_day=characteristic_day,
        day_df=day_df,
        year_df=year_df,
        centres_year_df=centres_year_df,
        flex_daily_stats=flex_daily_stats,
        battery_daily_stats=results.battery_daily_stats,
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
        rq1_files = run_rq1(
            centres_year_df=context.centres_year_df,
            year=context.year,
            characteristic_day=context.characteristic_day,
            output_dir=context.output_dir,
        )
        saved_files.extend([str(p.resolve()) for p in rq1_files])

    if args.rq in {"all", "rq2"}:
        fig, table = run_rq2(
            day_df=context.day_df,
            year_df=context.year_df,
            flex_daily_stats=context.flex_daily_stats,
            year=context.year,
            output_dir=context.output_dir,
        )
        saved_files.extend([str(fig.resolve()), str(table.resolve())])

    if args.rq in {"all", "rq3"}:
        fig10, fig25, table = run_rq3(
            day_df=context.day_df,
            battery_daily_stats=context.battery_daily_stats,
            year=context.year,
            output_dir=context.output_dir,
        )
        saved_files.extend([str(fig10.resolve()), str(fig25.resolve()), str(table.resolve())])

    print(f"RQ selection: {args.rq}")
    print(f"Year selected: {context.year}")
    print(f"Characteristic day: {context.characteristic_day.date()}")
    print(f"Min utilisation filter: > {context.min_utilisation}")
    print(f"dt_hours: {context.dt_hours}")
    for path in saved_files:
        print(f"Saved: {path}")


if __name__ == "__main__":
    main()
