"""Forecast meal-center weekly demand and compare with a previous-week baseline."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "row"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "client_report"
PAIR_KEYS = ["center_id", "meal_id"]
NUMERIC_FEATURES = [
    "week",
    "checkout_price",
    "base_price",
    "emailer_for_promotion",
    "homepage_featured",
    "lag_orders",
]
CATEGORICAL_FEATURES = ["center_id", "meal_id"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def read_and_validate_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(DATA_DIR / "train.csv")
    test = pd.read_csv(DATA_DIR / "test.csv")
    required = {
        "week",
        "center_id",
        "meal_id",
        "checkout_price",
        "base_price",
        "emailer_for_promotion",
        "homepage_featured",
        "num_orders",
    }
    missing = required - set(train.columns)
    if missing:
        raise ValueError(f"Training data is missing columns: {sorted(missing)}")
    missing_test = (required - {"num_orders"}) - set(test.columns)
    if missing_test:
        raise ValueError(f"Test data is missing columns: {sorted(missing_test)}")
    if "num_orders" in test.columns:
        raise ValueError("Test data unexpectedly contains num_orders.")
    if train[list(required)].isna().any().any() or test[list(required - {"num_orders"})].isna().any().any():
        raise ValueError("Missing values found in forecast input columns.")
    if train.duplicated(["week", *PAIR_KEYS]).any():
        raise ValueError("Training data contains duplicate logical order keys.")
    if test.duplicated(["week", *PAIR_KEYS]).any():
        raise ValueError("Test data contains duplicate logical order keys.")
    for column in ["emailer_for_promotion", "homepage_featured"]:
        if not set(train[column].unique()).issubset({0, 1}):
            raise ValueError(f"Non-binary values found in train[{column}].")
        if not set(test[column].unique()).issubset({0, 1}):
            raise ValueError(f"Non-binary values found in test[{column}].")
    if (train["num_orders"] < 0).any():
        raise ValueError("Negative training targets are not supported.")
    return train, test


def make_supervised_rows(data: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    previous = data[["week", *PAIR_KEYS, "num_orders"]].copy()
    previous["week"] += 1
    previous = previous.rename(columns={"num_orders": "lag_orders"})
    before = len(data)
    supervised = data.merge(
        previous,
        on=["week", *PAIR_KEYS],
        how="left",
        validate="one_to_one",
    )
    unmatched = int(supervised["lag_orders"].isna().sum())
    supervised = supervised.loc[supervised["lag_orders"].notna()].copy()
    if len(supervised) + unmatched != before:
        raise RuntimeError("Lag join row accounting failed.")
    print(
        f"Supervised lag join: before={before:,}, after={len(supervised):,}, "
        f"rows without exact prior-week match={unmatched:,}"
    )
    return supervised, unmatched


def make_model() -> Pipeline:
    preprocessing = ColumnTransformer(
        transformers=[
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
            (
                "category",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
    regression = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("regression", LinearRegression()),
        ]
    )
    return regression


def get_lag(
    history: dict[tuple[int, int], tuple[int, float]],
    pair: tuple[int, int],
    target_week: int,
    meal_fallback: dict[int, float],
) -> tuple[float, int | None, str]:
    previous = history.get(pair)
    if previous is not None:
        previous_week, previous_orders = previous
        kind = "exact_previous_week" if previous_week == target_week - 1 else "last_observed_pair"
        return previous_orders, previous_week, kind
    return meal_fallback[pair[1]], None, "meal_median_fallback"


def forecast_sequentially(
    model: Pipeline,
    initial_history: pd.DataFrame,
    forecast_rows: pd.DataFrame,
    meal_fallback: dict[int, float],
    actuals: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_history: dict[tuple[int, int], tuple[int, float]] = {
        (int(row.center_id), int(row.meal_id)): (int(row.week), float(row.num_orders))
        for row in initial_history.itertuples(index=False)
    }
    baseline_history = model_history.copy()
    predictions: list[pd.DataFrame] = []
    weekly_metrics: list[dict[str, float | int]] = []

    actual_lookup = None
    if actuals is not None:
        actual_lookup = actuals.set_index(["week", *PAIR_KEYS])["num_orders"]

    for week in sorted(forecast_rows["week"].unique()):
        current = forecast_rows.loc[forecast_rows["week"].eq(week)].copy()
        lag_info = [
            get_lag(
                model_history,
                (int(row.center_id), int(row.meal_id)),
                int(week),
                meal_fallback,
            )
            for row in current.itertuples(index=False)
        ]
        current["lag_orders"] = [entry[0] for entry in lag_info]
        current["lag_source_week"] = [entry[1] for entry in lag_info]
        current["lag_source"] = [entry[2] for entry in lag_info]
        baseline_lags = [
            get_lag(
                baseline_history,
                (int(row.center_id), int(row.meal_id)),
                int(week),
                meal_fallback,
            )
            for row in current.itertuples(index=False)
        ]
        current["baseline_lag_source"] = [entry[2] for entry in baseline_lags]
        current["model_prediction"] = np.maximum(
            0.0,
            model.predict(current[FEATURES]),
        )
        current["previous_week_baseline"] = [entry[0] for entry in baseline_lags]

        actual_by_pair: dict[tuple[int, int], float] = {}
        if actual_lookup is not None:
            for row in current.itertuples(index=False):
                key = (int(week), int(row.center_id), int(row.meal_id))
                if key in actual_lookup.index:
                    actual_by_pair[(key[1], key[2])] = float(actual_lookup.loc[key])
            current["actual_orders"] = [
                actual_by_pair.get((int(row.center_id), int(row.meal_id)), np.nan)
                for row in current.itertuples(index=False)
            ]
            current["has_exact_prior_week"] = current["lag_source"].eq("exact_previous_week")
            scored = current.loc[current["has_exact_prior_week"]].copy()
            if not scored.empty:
                weekly_metrics.append(
                    {
                        "week": int(week),
                        "scored_rows": int(len(scored)),
                        "eligible_rows": int(len(current)),
                        "model_mae": float(
                            np.mean(np.abs(scored["actual_orders"] - scored["model_prediction"]))
                        ),
                        "previous_week_mae": float(
                            np.mean(np.abs(scored["actual_orders"] - scored["previous_week_baseline"]))
                        ),
                    }
                )

        predictions.append(current)
        # The holdout is rolling one-week-ahead: actuals become available after
        # each scored week. The test horizon has no actuals, so update each
        # history with its own recursive forecast.
        if actual_lookup is not None:
            model_values = current["actual_orders"].to_numpy()
            baseline_values = model_values
        else:
            model_values = current["model_prediction"].to_numpy()
            baseline_values = current["previous_week_baseline"].to_numpy()
        for row, model_value, baseline_value in zip(
            current.itertuples(index=False),
            model_values,
            baseline_values,
        ):
            pair = (int(row.center_id), int(row.meal_id))
            if not pd.isna(model_value):
                model_history[pair] = (int(week), float(model_value))
            if not pd.isna(baseline_value):
                baseline_history[pair] = (int(week), float(baseline_value))

    result = pd.concat(predictions, ignore_index=True)
    metrics = pd.DataFrame(weekly_metrics)
    return result, metrics


def create_charts(
    weekly_validation: pd.DataFrame,
    forecast_test: pd.DataFrame,
    actual_validation: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actual_totals = (
        actual_validation.groupby("week")["num_orders"].sum().rename("actual_orders")
    )
    predicted_totals = (
        weekly_validation.set_index("week")["model_prediction_total"].rename("model_prediction")
    )
    baseline_totals = (
        weekly_validation.set_index("week")["previous_week_baseline_total"].rename(
            "previous_week_baseline"
        )
    )
    comparison = pd.concat([actual_totals, predicted_totals, baseline_totals], axis=1)

    fig, ax = plt.subplots(figsize=(10, 5))
    comparison.plot(ax=ax, marker="o", linewidth=2)
    ax.set_title("Rolling one-week-ahead validation: actual and predicted")
    ax.set_xlabel("Holdout training week")
    ax.set_ylabel("Orders in matched meal-center rows")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "forecast_validation.png", dpi=170)
    plt.close(fig)

    future = (
        forecast_test.groupby("week")
        .agg(
            model_forecast=("model_prediction", "sum"),
            previous_week_baseline=("previous_week_baseline", "sum"),
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    future.plot(ax=ax, marker="o", linewidth=2)
    ax.set_title("Demand forecasts from test.csv (weeks 146-155)")
    ax.set_xlabel("Test week")
    ax.set_ylabel("Forecast orders")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "forecast_test_weeks.png", dpi=170)
    plt.close(fig)


def main() -> None:
    train, test = read_and_validate_data()
    split_week = int(train["week"].max()) - 10
    print(
        f"Validated train rows={len(train):,}, weeks={train.week.min()}-{train.week.max()}; "
        f"test rows={len(test):,}, weeks={test.week.min()}-{test.week.max()}"
    )

    supervised, _ = make_supervised_rows(train)
    model_train = supervised.loc[supervised["week"].le(split_week)].copy()
    if model_train.empty:
        raise ValueError("Not enough supervised training rows before holdout.")
    backtest_rows = train.loc[train["week"].gt(split_week)].copy()
    print(
        f"Temporal split of supervised rows: before={len(supervised):,}, "
        f"model training weeks<={split_week}={len(model_train):,}, "
        f"holdout rows={len(backtest_rows):,}, "
        f"supervised rows outside training period="
        f"{len(supervised) - len(model_train):,}."
    )
    meal_fallback = train.groupby("meal_id")["num_orders"].median().to_dict()

    backtest_model = make_model()
    backtest_model.fit(model_train[FEATURES], model_train["num_orders"])
    warmup_history = train.loc[train["week"].le(split_week)].copy()
    backtest, weekly_metrics = forecast_sequentially(
        backtest_model,
        warmup_history,
        backtest_rows,
        meal_fallback,
        actuals=backtest_rows[["week", *PAIR_KEYS, "num_orders"]],
    )
    scored = backtest.loc[backtest["has_exact_prior_week"]].copy()
    model_mae = float(np.mean(np.abs(scored["actual_orders"] - scored["model_prediction"])))
    baseline_mae = float(
        np.mean(np.abs(scored["actual_orders"] - scored["previous_week_baseline"]))
    )
    improvement_pct = (baseline_mae - model_mae) / baseline_mae * 100
    print(
        f"Rolling holdout weeks={split_week + 1}-{int(train.week.max())}; "
        f"eligible exact-prior-week rows={len(scored):,}/{len(backtest):,} "
        f"({len(scored) / len(backtest) * 100:.2f}%)."
    )
    print(
        f"10-week rolling one-week-ahead MAE: linear regression={model_mae:.2f}, "
        f"previous-week baseline={baseline_mae:.2f}, "
        f"MAE change={improvement_pct:.2f}% (positive means lower MAE)."
    )

    final_model = make_model()
    final_training = supervised.loc[supervised["week"].le(int(train["week"].max()))]
    final_model.fit(final_training[FEATURES], final_training["num_orders"])
    test_forecast, _ = forecast_sequentially(
        final_model,
        train,
        test,
        meal_fallback,
    )

    weekly_forecast = (
        test_forecast.groupby("week")
        .agg(
            records=("id", "size"),
            model_prediction_total=("model_prediction", "sum"),
            previous_week_baseline_total=("previous_week_baseline", "sum"),
            lag_fallback_rows=("lag_source", lambda values: int(values.ne("exact_previous_week").sum())),
        )
        .reset_index()
    )
    weekly_validation = (
        backtest.loc[backtest["has_exact_prior_week"]]
        .groupby("week")
        .agg(
            model_prediction_total=("model_prediction", "sum"),
            previous_week_baseline_total=("previous_week_baseline", "sum"),
        )
        .reset_index()
    )
    validation_summary = (
        backtest.groupby("week")
        .agg(
            rows=("id", "size"),
            scored_rows=("has_exact_prior_week", "sum"),
            model_mae=(
                "model_prediction",
                lambda predictions: float(
                    np.mean(
                        np.abs(
                            backtest.loc[predictions.index, "actual_orders"]
                            - predictions
                        )[backtest.loc[predictions.index, "has_exact_prior_week"]]
                    )
                ),
            ),
        )
        .reset_index()
    )
    # Compute weekly baseline errors on the same exact-lag records used for model MAE.
    baseline_weekly_mae = (
        backtest.loc[backtest["has_exact_prior_week"]]
        .assign(
            abs_error=lambda frame: (
                frame["actual_orders"] - frame["previous_week_baseline"]
            ).abs()
        )
        .groupby("week")["abs_error"]
        .mean()
    )
    validation_summary["previous_week_mae"] = validation_summary["week"].map(
        baseline_weekly_mae
    )
    validation_summary["exact_lag_coverage_pct"] = (
        validation_summary["scored_rows"] / validation_summary["rows"] * 100
    )
    validation_summary.to_csv(
        OUTPUT_DIR / "forecast_validation_metrics.csv",
        index=False,
        float_format="%.4f",
    )
    test_forecast[
        [
            "id",
            "week",
            "center_id",
            "meal_id",
            "model_prediction",
            "previous_week_baseline",
            "lag_source",
            "lag_source_week",
        ]
    ].to_csv(
        OUTPUT_DIR / "test_demand_forecast.csv",
        index=False,
        float_format="%.2f",
    )
    weekly_forecast.to_csv(
        OUTPUT_DIR / "test_weekly_forecast_summary.csv",
        index=False,
        float_format="%.2f",
    )
    create_charts(
        weekly_validation,
        test_forecast,
        backtest.loc[backtest["has_exact_prior_week"]],
    )

    metrics = {
        "holdout_weeks": [split_week + 1, int(train["week"].max())],
        "model": "LinearRegression on order counts with center, meal, week, price, promotion, and lagged demand features; negative outputs clipped to zero",
        "evaluation": "rolling one-week-ahead forecasts over the final 10 training weeks; MAE scored only where the same center-meal pair had an observed prior-week record; both methods compared on identical rows",
        "scored_holdout_rows": len(scored),
        "holdout_rows": len(backtest),
        "exact_prior_week_coverage_pct": len(scored) / len(backtest) * 100,
        "linear_regression_mae": model_mae,
        "previous_week_baseline_mae": baseline_mae,
        "mae_improvement_pct": improvement_pct,
        "forecast_test_weeks": [int(test.week.min()), int(test.week.max())],
        "forecast_test_rows": len(test_forecast),
        "test_forecast_total": float(test_forecast.model_prediction.sum()),
        "test_baseline_total": float(test_forecast.previous_week_baseline.sum()),
        "test_exact_lag_rows": int(test_forecast.lag_source.eq("exact_previous_week").sum()),
        "test_stale_pair_fallback_rows": int(test_forecast.lag_source.eq("last_observed_pair").sum()),
        "test_meal_median_fallback_rows": int(test_forecast.lag_source.eq("meal_median_fallback").sum()),
    }
    (OUTPUT_DIR / "forecast_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Test forecast weekly totals:")
    print(weekly_forecast.to_string(index=False))
    print("Test prediction rows=", len(test_forecast))
    print("Test forecast total=", f"{metrics['test_forecast_total']:,.0f}")
    print(
        "Lag sources: "
        f"exact={metrics['test_exact_lag_rows']:,}, "
        f"stale_pair={metrics['test_stale_pair_fallback_rows']:,}, "
        f"meal_median={metrics['test_meal_median_fallback_rows']:,}"
    )
    print("Forecast artifacts saved:", (OUTPUT_DIR / "test_demand_forecast.csv").exists())


if __name__ == "__main__":
    main()
