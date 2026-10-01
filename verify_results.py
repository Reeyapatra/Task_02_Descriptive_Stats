import gzip
import json
import math
import sys
from itertools import zip_longest
from pathlib import Path


RELATIVE_TOLERANCE = 1e-9
ABSOLUTE_TOLERANCE = 1e-8
MAX_SAVED_EXAMPLES = 20

difference_count = 0
difference_examples = []


def record_difference(location, expected, actual):
    global difference_count

    difference_count += 1

    if len(difference_examples) < MAX_SAVED_EXAMPLES:
        difference_examples.append({
            "location": location,
            "pure_python": expected,
            "other_approach": actual,
        })


def compare_values(expected, actual, location):
    """Compare nested results, with tolerance for floating-point numbers."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)

        if expected_keys != actual_keys:
            record_difference(
                location + ".keys",
                sorted(expected_keys),
                sorted(actual_keys),
            )

        for key in sorted(expected_keys & actual_keys):
            compare_values(
                expected[key],
                actual[key],
                f"{location}.{key}",
            )

    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            record_difference(
                location + ".length",
                len(expected),
                len(actual),
            )

        for index, (left, right) in enumerate(zip(expected, actual)):
            compare_values(left, right, f"{location}[{index}]")

    elif isinstance(expected, int) and isinstance(actual, int):
        # Counts and frequencies must agree exactly.
        if expected != actual:
            record_difference(location, expected, actual)

    elif (
        isinstance(expected, (int, float))
        and isinstance(actual, (int, float))
    ):
        if not math.isclose(
            expected,
            actual,
            rel_tol=RELATIVE_TOLERANCE,
            abs_tol=ABSOLUTE_TOLERANCE,
        ):
            record_difference(location, expected, actual)

    elif expected != actual:
        record_difference(location, expected, actual)


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_group_records(path):
    """Read compressed results one group at a time."""
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                raise ValueError(
                    f"Unexpected blank line in {path}, line {line_number}"
                )

            yield json.loads(line)


def verify_grouped_reports(output_folder, filename):
    """Compare all groups without loading all reports into memory."""
    approaches = ["pure_python", "pandas", "polars"]

    streams = [
        read_group_records(output_folder / approach / filename)
        for approach in approaches
    ]

    end_marker = object()
    records_checked = 0

    for position, records in enumerate(
        zip_longest(*streams, fillvalue=end_marker),
        start=1,
    ):
        reference = records[0]

        for approach, actual in zip(approaches[1:], records[1:]):
            location = f"{filename}.{approach}.record[{position}]"

            if reference is end_marker or actual is end_marker:
                record_difference(
                    location,
                    "End of file" if reference is end_marker else "Record",
                    "End of file" if actual is end_marker else "Record",
                )
            else:
                compare_values(reference, actual, location)

        records_checked += 1

        if position % 25000 == 0:
            print(f"  Checked {position:,} group records", flush=True)

    return records_checked


def main():
    project_folder = Path(__file__).resolve().parent
    output_folder = project_folder / "outputs"

    approaches = ["pure_python", "pandas", "polars"]
    filenames = [
        "dataset_summary.json",
        "grouped_by_page_id.jsonl.gz",
        "grouped_by_page_id_ad_id.jsonl.gz",
    ]

    missing_files = [
        output_folder / approach / filename
        for approach in approaches
        for filename in filenames
        if not (output_folder / approach / filename).is_file()
    ]

    if missing_files:
        print("Verification cannot start. These reports are missing:")

        for path in missing_files:
            print(path)

        print("\nFinish running all three analysis scripts first.")
        return 2

    print("Checking dataset-level results...", flush=True)
    reference = read_json(
        output_folder / "pure_python" / "dataset_summary.json"
    )

    for approach in ["pandas", "polars"]:
        actual = read_json(
            output_folder / approach / "dataset_summary.json"
        )
        compare_values(reference, actual, f"dataset.{approach}")

    group_counts = {}

    for filename in filenames[1:]:
        print(f"\nChecking {filename}...", flush=True)
        group_counts[filename] = verify_grouped_reports(
            output_folder, filename
        )

    passed = difference_count == 0

    verification_report = {
        "status": "PASS" if passed else "FAIL",
        "dataset": reference["dataset"],
        "row_count": reference["row_count"],
        "column_count": reference["column_count"],
        "group_records_checked": group_counts,
        "relative_tolerance": RELATIVE_TOLERANCE,
        "absolute_tolerance": ABSOLUTE_TOLERANCE,
        "difference_count": difference_count,
        "first_differences": difference_examples,
    }

    report_path = output_folder / "verification_report.json"

    with report_path.open("w", encoding="utf-8") as file:
        json.dump(
            verification_report,
            file,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )

    print("\nVERIFICATION RESULT:", verification_report["status"])
    print(f"Differences found: {difference_count:,}")
    print(f"Report saved to: {report_path}")

    if passed:
        print("All three approaches agree within the stated tolerance.")
    else:
        print("Review the first differences in verification_report.json.")

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"Verification stopped: {error}", file=sys.stderr)
        sys.exit(2)