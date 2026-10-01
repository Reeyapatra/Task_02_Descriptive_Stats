import argparse
import csv
import gzip
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path


def configure_csv():
    """Allow large CSV fields on Windows and other platforms."""
    limit = sys.maxsize

    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def clean_value(value):
    """Treat empty and whitespace-only cells as missing."""
    if value is None:
        return None

    value = value.strip()
    return value if value else None


def read_dataset(file_path):
    """Read and validate the CSV using only the standard library."""
    configure_csv()

    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames

        if not columns:
            raise ValueError("The CSV has no column headers.")

        if len(columns) != len(set(columns)):
            raise ValueError("The CSV contains duplicate column names.")

        rows = []

        for record_number, row in enumerate(reader, start=1):
            if None in row or any(
                row[column] is None for column in columns
            ):
                raise ValueError(
                    f"Record {record_number} does not match the header."
                )

            rows.append({
                column: clean_value(row[column])
                for column in columns
            })

            if record_number % 50000 == 0:
                print(
                    f"  Read {record_number:,} records",
                    flush=True,
                )

    print(f"  Finished reading {len(rows):,} records", flush=True)
    return columns, rows


def infer_types(columns, rows):
    """Infer numeric types from all nonmissing values."""
    types = {}

    for column in columns:
        found_value = False
        all_integer = True
        numeric = True

        for row in rows:
            value = row[column]

            if value is None:
                continue

            found_value = True

            try:
                number = float(value)
            except (ValueError, OverflowError):
                numeric = False
                break

            if not math.isfinite(number):
                numeric = False
                break

            # Decimal avoids rounding a fractional value to an integer.
            exact_number = Decimal(value)

            if exact_number != exact_number.to_integral_value():
                all_integer = False

        if not found_value:
            types[column] = "unknown"
        elif not numeric:
            types[column] = "string"
        elif all_integer:
            types[column] = "integer"
        else:
            types[column] = "float"

        print(f"  {column}: {types[column]}", flush=True)

    return types


def convert_number(value, inferred_type):
    """Support integers written as 100, 100.0, or 1e2."""
    if inferred_type == "integer":
        return int(Decimal(value))

    return float(value)


def summarize_column(values, inferred_type, row_count):
    """Compute numeric or categorical statistics."""
    valid_values = [
        value for value in values if value is not None
    ]

    count = len(valid_values)
    missing = row_count - count

    result = {
        "type": inferred_type,
        "count": count,
        "missing_count": missing,
        "missing_percentage": (
            missing / row_count * 100 if row_count else 0.0
        ),
    }

    if inferred_type in {"integer", "float"}:
        numbers = [
            convert_number(value, inferred_type)
            for value in valid_values
        ]

        result.update({
            "mean": statistics.mean(numbers) if count else None,
            "min": min(numbers) if count else None,
            "max": max(numbers) if count else None,
            "standard_deviation": (
                statistics.stdev(numbers) if count >= 2 else None
            ),
            "median": statistics.median(numbers) if count else None,
        })

    else:
        frequencies = Counter(valid_values)

        ranked = sorted(
            frequencies.items(),
            key=lambda item: (-item[1], item[0]),
        )

        result.update({
            "unique_count": len(frequencies),
            "mode": ranked[0][0] if ranked else None,
            "mode_frequency": ranked[0][1] if ranked else 0,
            "top_5": [
                {"value": value, "frequency": frequency}
                for value, frequency in ranked[:5]
            ],
        })

    return result


def summarize_rows(columns, rows, types):
    """Summarize every column for a dataset or group."""
    row_count = len(rows)

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": {
            column: summarize_column(
                [row[column] for row in rows],
                types[column],
                row_count,
            )
            for column in columns
        },
    }


def summarize_single_row(columns, row, types):
    """Compute exact summaries without unnecessary sorting."""
    summaries = {}

    for column in columns:
        value = row[column]
        inferred_type = types[column]
        missing = value is None

        result = {
            "type": inferred_type,
            "count": 0 if missing else 1,
            "missing_count": 1 if missing else 0,
            "missing_percentage": 100.0 if missing else 0.0,
        }

        if inferred_type in {"integer", "float"}:
            number = (
                None if missing
                else convert_number(value, inferred_type)
            )

            result.update({
                "mean": number,
                "min": number,
                "max": number,
                "standard_deviation": None,
                "median": number,
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
        "column_count": len(columns),
        "columns": summaries,
    }


def write_json(path, result):
    """Save the dataset-level report."""
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )


def write_grouped_report(path, keys, columns, rows, types):
    """Save a complete summary for every group."""
    groups = defaultdict(list)

    for row in rows:
        group_key = tuple(row[key] for key in keys)
        groups[group_key].append(row)

    group_count = len(groups)
    print(f"  Found {group_count:,} groups", flush=True)

    # Lower compression level speeds up writing large reports.
    with gzip.open(
        path,
        "wt",
        encoding="utf-8",
        compresslevel=1,
    ) as file:
        for group_number, (group_key, group_rows) in enumerate(
            groups.items(),
            start=1,
        ):
            if len(group_rows) == 1:
                summary = summarize_single_row(
                    columns,
                    group_rows[0],
                    types,
                )
            else:
                summary = summarize_rows(
                    columns,
                    group_rows,
                    types,
                )

            result = {
                "group": dict(zip(keys, group_key)),
                **summary,
            }

            file.write(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

            progress_interval = (
                500 if group_count <= 10000 else 25000
            )

            if (
                group_number % progress_interval == 0
                or group_number == group_count
            ):
                print(
                    f"  Written {group_number:,} / "
                    f"{group_count:,} groups",
                    flush=True,
                )

    print(f"  Saved: {path.name}", flush=True)
    return group_count


def main():
    project_folder = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description=(
            "Pure Python descriptive statistics for Facebook ads."
        )
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
        default=project_folder / "outputs" / "pure_python",
    )

    args = parser.parse_args()

    if not args.input_file.is_file():
        parser.error(
            f"Dataset not found: {args.input_file}\n"
            "Place the Facebook ads CSV inside the data folder."
        )

    print(f"Reading: {args.input_file.name}", flush=True)
    columns, rows = read_dataset(args.input_file)

    missing_keys = {"page_id", "ad_id"}.difference(columns)

    if missing_keys:
        parser.error(
            "Required grouping columns missing: "
            + ", ".join(sorted(missing_keys))
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("\nDetecting column types...", flush=True)
    types = infer_types(columns, rows)

    print("\nCalculating dataset statistics...", flush=True)

    dataset_report = {
        "dataset": args.input_file.name,
        "rules": {
            "missing_values": "Empty or whitespace-only cells",
            "standard_deviation": (
                "Sample standard deviation with ddof=1"
            ),
            "undefined_statistics": "Represented as null",
            "frequency_ties": "Alphabetical ascending order",
            "group_column_types": "Inherited from the full dataset",
            "complex_values": "Summarized as complete strings",
        },
        **summarize_rows(columns, rows, types),
    }

    dataset_path = args.output_dir / "dataset_summary.json"
    write_json(dataset_path, dataset_report)
    print(f"  Saved: {dataset_path.name}", flush=True)

    print("\nGrouping by page_id...", flush=True)

    page_groups = write_grouped_report(
        args.output_dir / "grouped_by_page_id.jsonl.gz",
        ["page_id"],
        columns,
        rows,
        types,
    )

    print("\nGrouping by page_id and ad_id...", flush=True)

    ad_groups = write_grouped_report(
        args.output_dir / "grouped_by_page_id_ad_id.jsonl.gz",
        ["page_id", "ad_id"],
        columns,
        rows,
        types,
    )

    print("\nANALYSIS COMPLETE")
    print(f"Rows: {len(rows):,}")
    print(f"Columns: {len(columns)}")
    print(f"Page groups: {page_groups:,}")
    print(f"Page/ad groups: {ad_groups:,}")

    print("\nMissing values per column:")

    for column, summary in dataset_report["columns"].items():
        print(
            f"{column}: {summary['missing_count']:,} "
            f"({summary['missing_percentage']:.2f}%)"
        )

    print(
        f"\nReports saved to: {args.output_dir.resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, csv.Error) as error:
        print(f"\nAnalysis stopped: {error}", file=sys.stderr)
        sys.exit(1)