import argparse
import gzip
import json
from pathlib import Path

import polars as pl


def load_dataset(file_path):
    """Read all columns as text before detecting numeric types."""
    df = pl.read_csv(
        file_path,
        infer_schema=False,
        encoding="utf8",
    )

    expressions = []

    for column in df.columns:
        cleaned = pl.col(column).str.strip_chars()

        expressions.append(
            pl.when(cleaned == "")
            .then(None)
            .otherwise(cleaned)
            .alias(column)
        )

    return df.with_columns(expressions)


def infer_and_convert_types(df):
    """Classify columns using all nonmissing values."""
    types = {}
    conversions = []

    for column in df.columns:
        valid = df[column].drop_nulls()

        if len(valid) == 0:
            types[column] = "unknown"
            continue

        numbers = valid.cast(pl.Float64, strict=False)

        # A failed conversion becomes null.
        if numbers.null_count() > 0:
            types[column] = "string"
            continue

        if not numbers.is_finite().all():
            types[column] = "string"
            continue

        if (numbers == numbers.floor()).all():
            types[column] = "integer"
        else:
            types[column] = "float"

        conversions.append(
            pl.col(column).cast(pl.Float64).alias(column)
        )

    if conversions:
        df = df.with_columns(conversions)

    return df, types


def summarize_dataframe(df, types):
    """Calculate numeric and categorical statistics using Polars."""
    row_count = df.height
    missing_counts = df.null_count().row(0, named=True)
    summaries = {}

    for column in df.columns:
        series = df[column]
        valid = series.drop_nulls()

        missing = int(missing_counts[column])
        count = row_count - missing
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
            # Expression-based summaries are the Polars equivalent
            # of the numeric descriptive analysis.
            stats = df.select(
                pl.col(column).mean().alias("mean"),
                pl.col(column).min().alias("min"),
                pl.col(column).max().alias("max"),
                pl.col(column).std(ddof=1).alias("standard_deviation"),
                pl.col(column).median().alias("median"),
            ).row(0, named=True)

            result.update(stats)

        else:
            ranked = (
                valid.value_counts(name="frequency")
                .sort(
                    ["frequency", column],
                    descending=[True, False],
                )
                .head(5)
                .to_dicts()
            )

            result.update({
                "unique_count": int(valid.n_unique()),
                "mode": ranked[0][column] if ranked else None,
                "mode_frequency": (
                    int(ranked[0]["frequency"]) if ranked else 0
                ),
                "top_5": [
                    {
                        "value": item[column],
                        "frequency": int(item["frequency"]),
                    }
                    for item in ranked
                ],
            })

        summaries[column] = result

    return {
        "row_count": row_count,
        "column_count": df.width,
        "columns": summaries,
    }


def summarize_single_row(row, types):
    """Exact statistics for a group containing one record."""
    summaries = {}

    for column, value in row.items():
        missing = value is None
        inferred_type = types[column]

        result = {
            "type": inferred_type,
            "count": 0 if missing else 1,
            "missing_count": 1 if missing else 0,
            "missing_percentage": 100.0 if missing else 0.0,
        }

        if inferred_type in {"integer", "float"}:
            result.update({
                "mean": value,
                "min": value,
                "max": value,
                "standard_deviation": None,
                "median": value,
            })

        else:
            result.update({
                "unique_count": 0 if missing else 1,
                "mode": value,
                "mode_frequency": 0 if missing else 1,
                "top_5": (
                    [] if missing
                    else [{"value": value, "frequency": 1}]
                ),
            })

        summaries[column] = result

    return {
        "row_count": 1,
        "column_count": len(row),
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
    """Group with Polars and save complete statistics for every group."""
    group_sizes = (
        df.group_by(keys, maintain_order=True)
        .agg(pl.len().alias("__group_size"))
    )

    group_count = group_sizes.height
    all_single_rows = (
        df.height > 0
        and group_sizes["__group_size"].eq(1).all()
    )

    with gzip.open(path, "wt", encoding="utf-8") as file:
        if all_single_rows:
            # Group sizes are checked before using this shortcut.
            for number, row in enumerate(
                df.iter_rows(named=True), start=1
            ):
                write_record(file, {
                    "group": {key: row[key] for key in keys},
                    **summarize_single_row(row, types),
                })

                if number % 25000 == 0:
                    print(
                        f"  Written {number:,} / {group_count:,} groups",
                        flush=True,
                    )

        else:
            grouped = df.group_by(keys, maintain_order=True)

            for number, (group_key, group_df) in enumerate(
                grouped, start=1
            ):
                if not isinstance(group_key, tuple):
                    group_key = (group_key,)

                write_record(file, {
                    "group": dict(zip(keys, group_key)),
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
        description="Polars descriptive statistics for Facebook ads."
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
        default=project_folder / "outputs" / "polars",
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
    df, types = infer_and_convert_types(df)

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
    print(f"Rows: {df.height:,}")
    print(f"Columns: {df.width}")
    print(f"Page groups: {page_groups:,}")
    print(f"Page/ad groups: {ad_groups:,}")
    print(f"\nReports saved to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()