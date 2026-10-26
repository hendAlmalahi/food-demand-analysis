---
name: demand-metrics
description: "Use when analyzing weekly meal demand, calculating demand KPIs, comparing demand by meal, category, cuisine, center or week, evaluating promotions and relative price differences, measuring volatility, or preparing demand forecasts and reports for this food-demand project."
argument-hint: "Optional: specify the demand question, time range, and desired report format."
---

# Demand Metrics

Use this skill to calculate, validate, visualize, and explain demand indicators for this project. Treat every result as an observed-data summary unless a suitable evaluation design supports a stronger claim.

## Project data

- Use `data/row/train.csv` for historical demand. `num_orders` is the target.
- Use `data/row/test.csv` only for features and forecasts; it has no observed `num_orders`.
- Join `meal_info.csv` by `meal_id` and `fulfilment_center_info.csv` by `center_id` only when those attributes are needed.
- One logical row represents one meal at one center in one week. Its key is `(week, center_id, meal_id)`.
- Keep source CSVs unchanged. Transform in memory or write derived files to a separate output location.
- Project data rules and known caveats are documented in `AGENTS.md`.

## Workflow

### 1. Inspect and validate inputs

1. Resolve paths relative to the project root; do not use machine-specific absolute paths in reusable code.
2. Inspect columns, row counts, week coverage, unique meal/center counts, and target availability.
3. Confirm required columns exist, analysis columns contain no missing values, promotion flags are binary, and prices and target values are valid for the requested calculation.
4. Check duplicate logical keys using `(week, center_id, meal_id)`, not `id`.
5. Before and after each join, print row counts and the number of unmatched keys. Use many-to-one validation for reference-table joins. Stop if row counts change unexpectedly or unmatched keys are nonzero.
6. Whenever filtering or removing records is necessary, state the reason and criteria, and report rows before, after, and removed.

### 2. Calculate demand measures

Use `num_orders` rather than row counts as the demand measure.

- **Total demand:** sum `num_orders` over the explicitly stated population and period.
- **Weekly demand:** group by `week` and sum `num_orders`; include the number of weeks and observed rows.
- **Category/cuisine demand:** join the meal reference, aggregate order counts, and calculate each share as category or cuisine demand divided by total demand for the same population.
- **Center demand:** report total and mean per observed week. State how weeks without records are treated; absence of a row does not prove zero demand.
- **Concentration:** rank meals, categories, or centers by summed orders, and state the population and period covered. A high total may reflect availability and exposure as well as demand.
- **Volatility:** first aggregate orders to meal-week (or center-meal-week when that is the question), then calculate mean, standard deviation, and coefficient of variation (`std / mean`). Report observed-week counts. Do not fill absent meal-weeks with zero unless source evidence confirms zero demand.

### 3. Evaluate promotions and prices

- Define separate groups for email-only, homepage-only, both, and no promotion when the data supports those comparisons.
- For skewed order counts, compare promoted and unpromoted observations within the same `(center_id, meal_id)` using Mann–Whitney U. Include only strata containing both groups, and report how many strata and centers contribute.
- Report a descriptive percentage difference alongside the rank test, clearly naming the statistic used (for example, median difference or equally weighted stratum-mean difference). Mann–Whitney tests rank/distribution differences; it does not directly test a difference in means or prove a causal lift.
- Account for dependence within centers when computing inferential uncertainty. Do not treat all weekly observations as independent. If a reliable clustered or stratified inference is unavailable, label p-values as approximate or omit inferential claims.
- When testing multiple promotion contrasts, adjust p-values (for example, Holm) and report both the adjustment and threshold.
- Define relative price gap as `(base_price - checkout_price) / base_price` only when `base_price > 0`. A positive value is an exploratory price-difference proxy, not a documented discount.
- Use Spearman rank correlation for the association between relative price gap and `num_orders`. Report sample size, rho, subgroup definition, and whether ties or missing records were handled.
- Quantify overlap between promotions and positive price gaps. Discuss this overlap as a confounder; subgroup correlations do not isolate causal effects.

### 4. Forecast demand when requested

- Never use test targets; `test.csv` does not contain `num_orders`.
- Split training data chronologically. Do not shuffle weeks or allow future observations into training.
- Establish a simple baseline such as the same center-meal pair's previous-week demand.
- Compare models against the baseline with MAE on identical eligible rows, and state the evaluated weeks, scored row count, and coverage.
- For multi-week forecasts, explain whether predictions are recursive and how missing history is handled. Label test predictions as forecasts, not actual demand.
- Do not convert meal demand directly into ingredient purchase quantities without recipes, on-hand inventory, inbound orders, waste, and lead-time/service-level assumptions.

### 5. Report and visualize

- Use a chart suited to the question: weekly line chart, ranked category/center bars, promotion comparison with uncertainty or distributions, price-gap relationship, or volatility ranking.
- Label axes, units, period, and population. Use actual computed output; do not hard-code statistics into charts.
- For every reported number, identify its reproducible source: notebook cell, result table, generated CSV, or chart.
- Distinguish observed facts from hypotheses and recommendations. Say “associated with” or “coincided with,” not “caused,” unless the design supports causality.
- Include a **حدود** section in every analytical report.

## Required caveats

For this project, consider and state relevant limitations:

- Weeks are sequence numbers, not verified calendar dates.
- City/region/center identifiers are coded; do not invent real place names.
- Correlation and observational promotion comparisons do not prove causation.
- The currency and `op_area` unit are undocumented.
- The price gap is not a documented discount, and checkout price need not always be lower than base price.
- The test set has no observed target.
- Missing meal-week records are not necessarily zero demand.
- Demand alone does not measure profit, stockouts, customer counts, or service quality.

## Output checklist

Before delivering results, verify that:

- All aggregates use `num_orders` and state their population and week range.
- Joins preserve order-row counts and have zero unmatched keys, or analysis stopped with the reason.
- Comparisons specify their groups, unit, eligible sample/strata, test, and any multiple-testing correction.
- Forecast validation is temporal and includes baseline MAE.
- Charts and report figures match computed outputs.
- Recommendations name a supporting result and a measurable success indicator without overstating causality.
- The report includes **حدود**, including unavailable calendar dates, coded locations, and the fact that association does not establish cause.
