# Task 02 Descriptive Statistics

This project analyzes Facebook political advertising data using three
independent approaches: pure Python, Pandas, and Polars. It compares
dataset-level statistics and statistics grouped by page_id and by
page_id plus ad_id.

## Dataset

Source:
[2024 Facebook Political Ads](https://drive.google.com/file/d/1Jq0fPb-tq76Ee_RtM58fT0_M3o-JDBwe/view?usp=sharing)

Download the dataset and place it at:

data/2024_fb_ads_president_scored_anon.csv

The dataset is excluded from this repository.

The analyzed file contains:
- 246,745 records
- 41 columns
- 4,475 unique page identifiers
- 246,745 unique ad identifiers

## Installation

Python 3.14.3 was used for this analysis.

Create a virtual environment:

```powershell
py -3.14 -m venv .venv_work
```

Install the dependencies:

```powershell
.\.venv_work\Scripts\python.exe -m pip install -r requirements.txt
```

The pure Python script and verification script use only the Python
standard library.

## Running the Analysis

Run these commands from the project folder, one at a time:

```powershell
.\.venv_work\Scripts\python.exe pure_python_stats.py
.\.venv_work\Scripts\python.exe pandas_stats.py
.\.venv_work\Scripts\python.exe polars_stats.py
.\.venv_work\Scripts\python.exe verify_results.py
```

Each analysis script also accepts an input path:

```powershell
.\.venv_work\Scripts\python.exe pure_python_stats.py "data/2024_fb_ads_president_scored_anon.csv"
```

The scripts load the dataset into memory. Grouped report generation
may take several minutes.

## Statistics Produced

Numeric columns:
- Nonmissing count
- Mean
- Minimum and maximum
- Sample standard deviation
- Median

Non-numeric columns:
- Nonmissing count
- Unique value count
- Mode and its frequency
- Top five values by frequency

Dataset and group summaries:
- Row count and column count
- Missing-value counts and percentages
- Inferred column types

Both required grouping levels are included:
- page_id
- page_id and ad_id

## Statistical Rules

Empty and whitespace-only cells are treated as missing. Missing
values are excluded from descriptive statistics and are not
replaced with zero.

Column types are inferred from all nonmissing values. A column is
numeric only when every nonmissing value converts to a finite
number. Group summaries retain the types inferred from the full
dataset.

Sample standard deviation uses ddof=1. It is represented as null
when fewer than two valid numeric values are present.

Categorical frequency ties are resolved alphabetically. Stored
lists and dictionaries are summarized as complete strings; their
individual elements are not expanded.

## Findings

### Advertising records are concentrated among a few pages

The page with the most records accounts for 55,503 records, or
22.49% of the dataset. The three largest pages together account for
38.22%.

This concentration means that dataset-wide statistics are strongly
influenced by high-volume pages. Record volume does not necessarily
represent spending, reach, or political influence.

### Estimated impressions have a strongly asymmetric distribution

Mean estimated impressions are approximately 45,601.53, compared
with a median of 3,499.

The large difference suggests that high-impression records pull
the average upward. Reporting the median alongside the mean gives
a more informative description of a typical record.

### Missing advertiser information affects a small share of records

The bylines column contains 1,009 blank values, representing 0.41%
of the dataset. The other columns contain no blank values under
the project's missing-value definition.

A nonblank value does not guarantee that its contents are valid
or complete.

### Spending values use multiple currencies

The currency column contains 18 distinct currencies. USD appears
in 246,599 records, while 146 records use other currencies.

The required overall spending statistics mix currency units.
They should not be interpreted as a dollar average or total.
Financial comparisons require a common currency or separate
analysis by currency.

### Every page and ad combination contains one record

All 246,745 ad identifiers are unique. Consequently, grouping by
page_id and ad_id produces 246,745 single-record groups.

For these groups, numeric mean, median, minimum, and maximum are
equal to the recorded value. Sample standard deviation is
undefined. Grouping by page_id provides more useful comparisons
between collections of records.

## Verification

verify_results.py compares the Pandas and Polars reports against
the independently calculated pure Python reports.

It checks dataset summaries and every group summary, including
missing values, inferred types, numeric statistics, and categorical
frequencies.

Counts and frequencies must match exactly. Floating-point values
are compared using:
- Relative tolerance: 1e-9
- Absolute tolerance: 1e-8

The completed comparison returned PASS with zero differences.

Agreement demonstrates consistency between the implementations.
It does not independently establish the accuracy of the source
data or the interpretation of its labels.

## Output Files

Each approach writes reports to its own folder under outputs:

- dataset_summary.json
- grouped_by_page_id.jsonl.gz
- grouped_by_page_id_ad_id.jsonl.gz

The grouped reports are compressed JSON Lines files, with one
complete group summary per line.

Pandas also produces pandas_describe.csv.

Verification produces outputs/verification_report.json.

Large grouped reports are excluded from GitHub and can be
regenerated by running the scripts.

## Reflection

See REFLECTION.md for a comparison of the approaches, design
choices, limitations, and the use of AI assistance.