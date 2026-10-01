import argparse
import gzip
import json
import math
from pathlib import Path

import pandas as pd


def load_dataset(file_path):
    """Read text first so type and missing-value rules are explicit."""
    df = pd.read_csv(
        file_path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )

    for column in df.columns:
        cleaned = df[column].str.strip()
        df[column] = cleaned.mask(cleaned.eq(""), pd.NA)

    return df


def infer_and_convert_types(df):
    """Use the same numeric classification as the pure Python script."""
    types = {}

    for column in df.columns:
        valid = df[column].dropna()

        if valid.empty:
            types[column] = "unknown"
            continue

        try:
            numbers = valid.map(float)
        except (ValueError, OverflowError):
            types[column] = "string"
            continue

        if not numbers.map(math.isfinite).all():
            types[column] = "string"
            continue

        if numbers.map(float.is_integer).all():
            types[column] = "integer"
            converted = valid.map(int)
        else:
            types[column] = "float"
            converted = numbers

        # Float64 supports missing values and Pandas numeric operations.
        df[column] = pd.to_numeric(
            converted.reindex(df.index)
        ).astype("Float64")

    return types


def summarize_dataframe(df, types):
    """Produce the same report structure as the pure Python script."""
    row_count = len(df)
    missing_counts = df.isna().sum()
    summaries = {}

    for column in df.columns:
        series = df[column]
        valid = series.dropna()
        count = int(series.count())
        missing = int(missing_counts[column])
        inferred_type = types[column]

        result = {
            "type": inferred_type,
            "count": count,
            "missing_count": missing,
            "missing_percentage": (
                missing / row_count * 100 if row_count else 0.0
            ),
        }

        if inferred_type in {"integer", "float"}:
            result.update({
                "mean": float(valid.mean()) if count else None,
                "min": float(valid.min()) if count else None,
                "max": float(valid.max()) if count else None,
                "standard_deviation": (
                    float(valid.std(ddof=1)) if count >= 2 else None
                ),
                "median": float(valid.median()) if count else None,
            })

        else:
            frequencies = valid.value_counts()

            # Match the pure Python rule for tied frequencies.
            ranked = sorted(
                frequencies.items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )

            result.update({
                "unique_count": int(valid.nunique()),
                "mode": str(ranked[0][0]) if ranked else None,
                "mode_frequency": int(ranked[0][1]) if ranked else 0,
                "top_5": [
                    {"value": str(value), "frequency": int(frequency)}
                    for value, frequency in ranked[:5]
                ],
            })

        summaries[column] = result

    return {
        "row_count": row_count,
        "column_count": len(df.columns),
        "columns": summaries,
    }


def summarize_single_row(row, columns, types):
    """Calculate exact summaries for a group containing one record."""
    summaries = {}

    for column, value in zip(columns, row):
        missing = bool(pd.isna(value))
        inferred_type = types[column]

        result = {
            "type": inferred_type,
            "count": 0 if missing else 1,
            "missing_count": 1 if missing else 0,
            "missing_percentage": 100.0 if missing else 0.0,
        }

        if inferred_type in {"integer", "float"}:
            number = None if missing else float(value)

            result.update({
                "mean": number,
                "min": number,
                "max": number,
                "standard_deviation": None,
                "median": number,
            })

        else:
            text = None if missing else str(value)

            result.update({
                "unique_count": 0 if missing else 1,
                "mode": text,
                "mode_frequency": 0 if missing else 1,
                "top_5": (
                    [] if missing
                    else [{"value": text, "frequency": 1}]
                ),
            })

        summaries[column] = result

    return {
        "row_count": 1,
        "column_count": len(columns),
        "columns": summaries,
    }


def write_record(file, result):
    file.write(
        json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    )


def write_grouped_report(path, df, keys, types):
    """Perform Pandas grouping and save every group's statistics."""
    grouping = keys[0] if len(keys) == 1 else keys
    grouped = df.groupby(grouping, sort=False, dropna=False)
    group_sizes = grouped.size()
    group_count = len(group_sizes)

    with gzip.open(path, "wt", encoding="utf-8") as file:
        if not df.empty and group_sizes.eq(1).all():
            # Avoid constructing hundreds of thousands of tiny DataFrames.
            # This branch is valid only after checking every group size.
            columns = list(df.columns)
            positions = [columns.index(key) for key in keys]

            for number, row in enumerate(
                df.itertuples(index=False, name=None), start=1
            ):
                group_values = {
                    key: (
                        None if pd.isna(row[position])
                        else str(row[position])
                    )
                    for key, position in zip(keys, positions)
                }

                write_record(file, {
                    "group": group_values,
                    **summarize_single_row(row, columns, types),
                })

                if number % 25000 == 0:
                    print(
                        f"  Written {number:,} / {group_count:,} groups",
                        flush=True,
                    )

        else:
            for number, (group_key, group_df) in enumerate(
                grouped, start=1
            ):
                values = (
                    (group_key,) if len(keys) == 1 else group_key
                )

                group_values = {
                    key: None if pd.isna(value) else str(value)
                    for key, value in zip(keys, values)
                }

                write_record(file, {
                    "group": group_values,
                    **summarize_dataframe(group_df, types),
                })

                if number % 500 == 0:
                    print(
                        f"  Written {number:,} / {group_count:,} groups",
                        flush=True,
                    )

    return group_count


def main():
    project_folder = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Pandas descriptive statistics for Facebook ads."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=(
            project_folder
            / "data"
            / "2024_fb_ads_president_scored_anon.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_folder / "outputs" / "pandas",
    )
    args = parser.parse_args()

    if not args.input_file.is_file():
        parser.error(f"Dataset not found: {args.input_file}")

    print(f"Reading: {args.input_file.name}", flush=True)
    df = load_dataset(args.input_file)

    missing_keys = {"page_id", "ad_id"}.difference(df.columns)
    if missing_keys:
        parser.error(
            "Required grouping columns missing: "
            + ", ".join(sorted(missing_keys))
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Detecting column types...", flush=True)
    types = infer_and_convert_types(df)

    # Required Pandas describe() analysis for numeric and text columns.
    df.describe(include="all").to_csv(
        args.output_dir / "pandas_describe.csv",
        encoding="utf-8",
    )

    print("Calculating dataset statistics...", flush=True)
    report = {
        "dataset": args.input_file.name,
        "rules": {
            "missing_values": "Empty or whitespace-only cells",
            "standard_deviation": "Sample standard deviation with ddof=1",
            "undefined_statistics": "Represented as null",
            "frequency_ties": "Alphabetical ascending order",
            "group_column_types": "Inherited from the full dataset",
            "complex_values": "Summarized as complete strings",
        },
        **summarize_dataframe(df, types),
    }

    with (args.output_dir / "dataset_summary.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            report, file, indent=2, ensure_ascii=False, allow_nan=False
        )

    print("Grouping by page_id...", flush=True)
    page_groups = write_grouped_report(
        args.output_dir / "grouped_by_page_id.jsonl.gz",
        df,
        ["page_id"],
        types,
    )

    print("Grouping by page_id and ad_id...", flush=True)
    ad_groups = write_grouped_report(
        args.output_dir / "grouped_by_page_id_ad_id.jsonl.gz",
        df,
        ["page_id", "ad_id"],
        types,
    )

    print("\nANALYSIS COMPLETE")
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")
    print(f"Page groups: {page_groups:,}")
    print(f"Page/ad groups: {ad_groups:,}")
    print(f"\nReports saved to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()