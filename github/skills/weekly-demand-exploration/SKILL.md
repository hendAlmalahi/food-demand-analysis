---
name: weekly-demand-exploration
description: "Use when exploring weekly meal demand trends, week-over-week changes, spikes and drops, rolling averages, shared meal-center comparisons, category or meal trends by week, and weekly demand charts or summaries in this food-demand project."
argument-hint: "Optional: provide the week range, comparison groups, and desired chart or report."
---

# Weekly Demand Exploration

Explore how recorded meal demand changes over time and identify weeks, meals, categories, or centers that merit follow-up. This is a descriptive workflow unless a suitable temporal model and validation design are explicitly used.

## Data and grain

- Read historical orders from `data/row/train.csv`; use `num_orders` as the demand measure.
- A row represents one meal at one center in one week. Check the logical key `(week, center_id, meal_id)` for duplicates.
- The training data covers weeks 1–145; the test data covers weeks 146–155 and does not contain `num_orders`.
- Week numbers are sequence identifiers, not calendar dates. Do not assign months, holidays, seasons, or real dates without a documented mapping.
- Keep source CSVs unchanged. Save derived tables, charts, and reports outside the source-data directory.

## Exploration procedure

### 1. Validate and establish scope

1. Resolve project paths relatively and load the training file.
2. Verify the target and required keys exist; check missing values, target validity, duplicate logical keys, week range, and record counts.
3. State the exact week interval and population for each result.
4. If joining meal or center references, report rows before and after, removed/affected rows, and unmatched keys. Stop if the join changes order-row counts unexpectedly or leaves unmatched keys.
5. Do not silently filter weeks or records. State the rule and report before/after counts.

### 2. Build the weekly demand series

- Aggregate by week with `sum(num_orders)`; also report observed row count per week.
- Sort by week before calculating change. For adjacent observed weeks, calculate:

  `week_over_week_pct = (current_week_orders / previous_week_orders - 1) * 100`

- If week numbers are not consecutive, identify the interval explicitly; do not call non-adjacent records a week-over-week change.
- Summarize period average and median, maxima/minima with their week numbers, and counts of increases/decreases only when useful to the question.
- For a smoother trend, compare explicitly defined rolling means (for example, four-week windows) or fixed beginning/end windows. State window definitions and avoid implying a seasonal pattern from sequence numbers alone.
- Flag large movements for investigation, not as proof of an event or cause.

### 3. Distinguish composition changes from like-for-like changes

- A total can change because demand changed, because recorded meal-center combinations changed, or both.
- For adjacent-week comparisons, optionally restrict to the intersection of `(center_id, meal_id)` pairs observed in both weeks.
- Report pair counts and demand totals before and after restricting to the intersection; document this as a comparison subset, not a deletion from the source.
- Do not interpret an absent meal-center-week record as zero demand, a stockout, closure, or discontinuation without evidence.
- When comparing category/meal trends, join `meal_info.csv` on `meal_id` with many-to-one validation, report unmatched keys and row counts, and distinguish total orders from the number of records.
- When comparing center trends, note unequal coverage. Report totals together with averages over observed weeks, and do not equate demand volume with efficiency or profitability.

### 4. Identify changes worth investigation

- Rank largest absolute and percentage weekly movements, showing both the current and prior totals and their record coverage.
- If a movement is driven by a few meals or centers, decompose the total by those dimensions and state how much of the aggregate difference they represent.
- Compare matched pairs for coverage sensitivity when possible.
- Describe a change as “observed,” “increased,” “decreased,” or “coincided with.” Do not attribute it to promotions, prices, availability, seasonality, or operations without a design that supports that explanation.
- For statistical claims, use a method suited to the dependence and distribution in the data; report the tested population and uncertainty. Descriptive week-to-week differences alone are not significance tests.

### 5. Visualize and report

- Use a chronological line chart for weekly totals and optionally overlay a clearly labeled rolling mean.
- Label the x-axis as week number and the y-axis as total recorded orders. Note record coverage and any excluded/nonconsecutive weeks.
- Use a paired chart or table for adjacent-week totals; use a separate chart for matched-pair comparisons where coverage may differ.
- For category or meal contributions, use ranked bars or small multiples with a stated week range and denominator.
- Ensure chart values are computed from the same data and definitions as the report.
- Include a **الحدود** section and cite the table, notebook, output file, or calculation cell that produced every reported number.

## Required interpretation boundaries

For this project, consider these limitations when relevant:

- The observed time field is week number only; no real calendar dates are supplied.
- The available training period is weeks 1–145. The later test weeks have no actual target values.
- A missing order record is not necessarily zero demand.
- Aggregate changes may reflect a changing mix of observed center-meal pairs.
- The data is observational; temporal coincidence does not prove cause.
- Orders alone do not reveal unserved demand, inventory availability, stockouts, unique customers, costs, or profitability.
- Center and location identifiers are coded and should not be replaced with guessed place names.

## Delivery checklist

Before sharing a weekly exploration:

- Confirm the week range, chronological sorting, row counts, and key validation.
- Check that each reported weekly delta compares consecutive weeks or clearly labels a longer interval.
- State observed record coverage and distinguish total change from matched-pair change.
- Verify that missing rows were not silently treated as zero.
- Include a labeled time-series chart and cite its computed source.
- Separate observed findings from hypotheses and recommendations.
- Include **الحدود** and avoid causal wording not supported by study design.
