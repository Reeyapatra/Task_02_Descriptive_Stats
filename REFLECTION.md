# Reflection on Three Approaches to Descriptive Statistics

## Producing Consistent Results

The three implementations produced matching dataset-level and grouped
results within the verification tolerance. The comparison returned PASS
with zero differences.

Consistency required explicit rules for missing values, column types,
standard deviation, and categorical frequency ties. Empty and
whitespace-only cells were treated as missing. Missing numeric values
were excluded rather than replaced with zero.

All implementations used sample standard deviation with ddof=1.
Groups containing fewer than two valid numeric values reported null
for standard deviation. Frequency ties were resolved alphabetically.

Floating-point statistics were compared with a relative tolerance of
1e-9 and an absolute tolerance of 1e-8. Counts and frequencies were
required to match exactly.

Agreement between implementations establishes consistency, but it
does not prove that every shared assumption is correct. Additional
tests with independently calculated expected results would strengthen
the verification.

## Comparing the Approaches

### Pure Python

The pure Python implementation makes the analysis steps explicit.
CSV loading, missing-value handling, type detection, frequency
counting, and grouping are visible in the code.

This helps explain what DataFrame libraries automate. However,
implementing these operations requires more manual code and creates
more opportunities for inconsistent behavior.

### Pandas

Pandas provides convenient tools such as describe(), value_counts(),
nunique(), and groupby(). These operations make exploratory analysis
and categorical summaries easier to express.

Default behavior still requires attention. For example, this project
loaded columns as text first and applied explicit missing-value and
type rules to make the results comparable with the other approaches.

### Polars

The Polars implementation uses expression-based numeric summaries,
value_counts(), n_unique(), and group_by().

Its expression syntax provides a different way to describe data
transformations. The implementation also requires deliberate handling
of nulls and conversion failures to preserve the project's rules.

This project used eager DataFrames. It did not evaluate Polars lazy
execution or streaming capabilities.

## Performance and Implementation Choices

No controlled performance benchmark was conducted, so this project
does not establish which library is fastest.

Runtime includes CSV reading, type detection, statistical calculations,
JSON serialization, and compression. Comparing complete scripts would
measure all these activities, not only each library's aggregation speed.

All three implementations load the dataset into memory. This limits
their suitability for files larger than available memory.

The dataset contains 246,745 unique ad identifiers. Consequently,
every page_id and ad_id group contains one record. The implementations
handle single-record summaries directly to avoid unnecessary repeated
calculations.

Grouped reports are written incrementally to compressed JSON Lines
files. Verification reads those reports incrementally rather than
loading every group report into memory.

## Recommendation for a Junior Analyst

I would recommend learning basic Python data structures and statistical
concepts first, followed by Pandas for practical tabular analysis.

Understanding lists, dictionaries, missing values, and grouping makes
DataFrame operations easier to interpret. Pandas then provides a
convenient way to apply those concepts.

Polars would be a useful next step for learning expression-based
analysis and investigating alternative execution approaches. Tool
selection should depend on the workload, team requirements, and
measured performance.

## Complex Values and Data Cleaning

Columns such as publisher_platforms, delivery_by_region, and
demographic_distribution contain stored lists or dictionary-like text.

This project preserved those values as complete strings. Their
categorical summaries therefore describe complete stored values,
rather than individual platforms, regions, or demographic categories.

This choice supports consistent summaries across the implementations,
but limits analytical depth. Equivalent structures written in different
orders may be counted as different values.

Further analysis would require safely parsing the structures,
normalizing their representation, and defining how their elements
should contribute to statistics. Arbitrary eval() should not be used
to parse dataset contents.

## Interpreting Grouped Results

Page-level grouping revealed concentration that a row count alone
would not show. The largest page accounts for 22.49% of records, and
the three largest pages account for 38.22%.

These figures describe record volume. They do not establish spending
share, audience reach, or political influence.

The page_id and ad_id grouping fulfills the assignment requirement,
but contains only single-record groups in this dataset. Page-level
grouping is more informative for comparing collections of records.

## Currency and Other Limitations

The dataset contains 18 currencies. Overall estimated spending
statistics combine different monetary units and should not be
interpreted as dollar statistics.

A meaningful financial comparison would require separate analysis
by currency or a documented currency conversion method.

Estimated impressions are not necessarily unique people reached.
The dataset's automated labels also require supporting documentation
before drawing conclusions about their meaning or accuracy.

## Use of AI Assistance

ChatGPT provided code drafts, explanations, troubleshooting guidance,
and documentation drafts during this project.

The generated scripts were run locally, and their dataset-level and
grouped outputs were compared using a separate verification script.
The final comparison returned PASS with zero differences.

This illustrates a useful role for AI assistance: accelerating
implementation while making validation an explicit part of the work.

The project did not conduct a systematic comparison of ChatGPT,
Claude, or Copilot. It therefore does not establish which AI tool
produces the best starter code.

## Improvements for Future Work

Useful improvements include:
- Tests with independently calculated expected statistics.
- Controlled runtime and memory benchmarks.
- Parsing and normalizing nested structures.
- Currency-specific spending analysis.
- Visualizations supporting the grouped findings.
- Grouping configuration for datasets with different schemas.