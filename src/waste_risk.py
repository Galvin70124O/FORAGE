"""Waste-risk classifier: will this purchase end up as high waste?

Label: a record is "high waste" when more than 30% of the purchase is thrown
away (Waste_Percentage > 30). In the demo data that is roughly the top fifth
of records (the 78th percentile), i.e. clearly worse than a typical purchase,
and it is a threshold a household can act on ("nearly a third went in the bin").

Features are only things known when the food is bought:
    Expiry_Days            shelf life of the purchase
    Category               food category
    Quantity_Purchased     how much was bought
    Recent_Consumption     the food's mean consumption rate (consumed / purchased)
                           over its previous 7 records, shifted so the current
                           record is never included
    Day_of_Week            day of the purchase
No waste, consumption or remaining value of the record itself is used.

Models: Logistic Regression and a Random Forest classifier, both with
class_weight="balanced" for the imbalance. Chronological split (last 20% of
dates = test). The decision threshold favours recall: it is the highest
threshold that still catches at least 80% of high-waste records on a
validation slice (the last 20% of the training period), never chosen on the
test set. Each model is also trained without Quantity_Purchased to show how
much of the score comes from that one feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from prediction import FOREST

HIGH_WASTE_PCT = 30.0
TARGET_RECALL = 0.80
NUMERIC = ["Expiry_Days", "Quantity_Purchased", "Recent_Consumption"]
CATEGORICAL = ["Category", "Day_of_Week"]
ALL_FEATURES = NUMERIC + CATEGORICAL


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Purchase-time features and the label; the first record of each food has no history and is dropped."""
    out = df.sort_values(["Food", "Date"]).copy()
    if "Recent_Consumption" not in out:  # My data supplies a resolution-safe version (pantry.purchase_outcomes)
        rate = out["Quantity_Consumed"] / out["Quantity_Purchased"].where(out["Quantity_Purchased"] > 0)
        out["Recent_Consumption"] = rate.groupby(out["Food"]).transform(
            lambda values: values.shift(1).rolling(7, min_periods=1).mean())
    out["Day_of_Week"] = out["Date"].dt.day_name()
    out["High_Waste"] = (out["Waste_Percentage"] > HIGH_WASTE_PCT).astype(int)
    return out.dropna(subset=["Recent_Consumption", "Waste_Percentage", "Expiry_Days"]).reset_index(drop=True)


def classifiers(numeric: list[str]) -> dict:
    preprocess = lambda scale: ColumnTransformer([  # noqa: E731
        ("num", StandardScaler() if scale else "passthrough", numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)])
    return {
        "Logistic Regression": Pipeline([("prep", preprocess(True)), ("model", LogisticRegression(
            class_weight="balanced", max_iter=2000))]),
        "Random Forest": Pipeline([("prep", preprocess(False)), ("model", RandomForestClassifier(
            **FOREST, class_weight="balanced"))]),
    }


def time_split(df: pd.DataFrame, fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = np.sort(df["Date"].unique())
    cutoff = dates[min(max(int(len(dates) * (1 - fraction)), 1), len(dates) - 1)]
    return df[df["Date"] < cutoff].copy(), df[df["Date"] >= cutoff].copy()


def recall_first_threshold(y_true, scores, target: float = TARGET_RECALL) -> float:
    """Highest threshold whose recall is still >= target (falls back to 0.5 if none reach it)."""
    y_true, scores = np.asarray(y_true), np.round(np.asarray(scores, float), 4)
    positives = y_true.sum()
    if positives == 0:
        return 0.5
    for threshold in np.unique(scores)[::-1]:  # vectorised recall: positives scoring at or above the threshold
        if (y_true[scores >= threshold] == 1).sum() / positives >= target:
            return float(threshold)
    return 0.5


def metrics(y_true, scores, threshold: float) -> dict:
    predicted = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {"Threshold": threshold, "Precision": precision_score(y_true, predicted, zero_division=0),
            "Recall": recall_score(y_true, predicted, zero_division=0), "F1": f1_score(y_true, predicted, zero_division=0),
            "ROC_AUC": roc_auc_score(y_true, scores) if len(set(y_true)) > 1 else float("nan"),
            "TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)}


def evaluate(df: pd.DataFrame) -> dict:
    """Train and score all four variants. Returns comparison, the chosen model and its test scores."""
    data = add_features(df)
    train, test = time_split(data)
    fit_part, validation = time_split(train)
    rows, fitted, test_scores = [], {}, {}
    for features_name, numeric in (("All features", NUMERIC),
                                   ("Without quantity purchased", [c for c in NUMERIC if c != "Quantity_Purchased"])):
        features = numeric + CATEGORICAL
        for name, model in classifiers(numeric).items():
            model.fit(fit_part[features], fit_part["High_Waste"])
            threshold = recall_first_threshold(validation["High_Waste"], model.predict_proba(validation[features])[:, 1])
            model.fit(train[features], train["High_Waste"])  # refit on the whole training period
            scores = model.predict_proba(test[features])[:, 1]
            key = f"{name} · {features_name}"
            rows.append({"Model": name, "Features": features_name, **metrics(test["High_Waste"], scores, threshold)})
            fitted[key], test_scores[key] = (model, features, threshold), scores
    comparison = pd.DataFrame(rows).sort_values(["Features", "ROC_AUC"], ascending=[True, False]).reset_index(drop=True)
    best_row = comparison[comparison["Features"] == "All features"].iloc[0]
    best_key = f"{best_row['Model']} · All features"
    return {"comparison": comparison, "best": best_key, "model": fitted[best_key], "fitted": fitted,
            "threshold": fitted[best_key][2],
            "test": test, "scores": test_scores, "train_rows": len(train), "test_rows": len(test),
            "positive_rate": float(data["High_Waste"].mean()), "cutoff": test["Date"].min()}


def score_purchases(model_info: tuple, rows: pd.DataFrame) -> pd.Series:
    """Probability of high waste for planned purchases (same purchase-time features)."""
    model, features, _ = model_info
    return pd.Series(model.predict_proba(rows[features])[:, 1], index=rows.index)


def planned_rows(records: pd.DataFrame, foods: pd.Series, quantities: pd.Series, date) -> pd.DataFrame:
    """Purchase-time features for planned purchases of `foods` (quantities aligned) on `date`.

    Category and shelf life come from each food's records; Recent_Consumption is
    the food's mean consumption rate over its last 7 records.
    """
    history = records.sort_values("Date")
    rate = history["Quantity_Consumed"] / history["Quantity_Purchased"].where(history["Quantity_Purchased"] > 0)
    recent = rate.groupby(history["Food"]).apply(lambda r: r.tail(7).mean())
    info = history.groupby("Food").agg(Category=("Category", "last"), Expiry_Days=("Expiry_Days", "median"))
    rows = pd.DataFrame({"Food": foods.to_numpy(), "Quantity_Purchased": quantities.to_numpy()})
    rows["Category"] = rows["Food"].map(info["Category"])
    rows["Expiry_Days"] = rows["Food"].map(info["Expiry_Days"])
    rows["Recent_Consumption"] = rows["Food"].map(recent)
    rows["Day_of_Week"] = pd.Timestamp(date).day_name()
    return rows
