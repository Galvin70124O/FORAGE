"""Market-basket analysis of the Instacart extract (association rules with FP-growth).

To keep it fast, only the `top_n` most-ordered products are used: each order
becomes a basket of the top products it contains, and orders with fewer than
two of them are dropped (a single item cannot form a rule).

    support     share of baskets that contain all items of the rule
    confidence  of the baskets with the "if" items, the share that also have the "then" items
    lift        confidence ÷ how common the "then" items are anyway (1 = no association, > 1 = bought together
                more often than chance)
"""

from __future__ import annotations

import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth

DEFINITIONS = {
    "Support": "Share of baskets that contain every item in the rule.",
    "Confidence": "Of baskets with the 'if' item(s), the share that also contain the 'then' item(s).",
    "Lift": "Confidence divided by how common the 'then' item(s) are anyway: 1 means no link, 2 means twice as likely.",
}


def baskets(orders: pd.DataFrame, top_n: int = 150, *, order: str = "Order_ID", item: str = "Product_Name") -> pd.DataFrame:
    """One boolean row per order (with at least two top products), one column per top product."""
    top = orders[item].value_counts().head(top_n).index
    subset = orders[orders[item].isin(top)][[order, item]].drop_duplicates()
    sizes = subset.groupby(order)[item].transform("size")
    subset = subset[sizes >= 2]
    matrix = pd.crosstab(subset[order], subset[item].astype(str)).astype(bool)
    matrix.columns.name = None
    return matrix


def find_rules(matrix: pd.DataFrame, *, min_support: float = 0.01, min_lift: float = 1.2,
               max_len: int = 3) -> pd.DataFrame:
    """Rules with lift above `min_lift`, strongest first, with readable "if" and "then" text."""
    itemsets = fpgrowth(matrix, min_support=min_support, use_colnames=True, max_len=max_len)
    if itemsets.empty:
        return pd.DataFrame(columns=["If", "Then", "Support", "Confidence", "Lift", "Antecedents", "Consequents"])
    rules = association_rules(itemsets, metric="lift", min_threshold=min_lift)
    rules = rules.assign(
        If=rules["antecedents"].map(lambda s: " + ".join(sorted(s))),
        Then=rules["consequents"].map(lambda s: " + ".join(sorted(s))),
    ).rename(columns={"support": "Support", "confidence": "Confidence", "lift": "Lift",
                      "antecedents": "Antecedents", "consequents": "Consequents"})
    columns = ["If", "Then", "Support", "Confidence", "Lift", "Antecedents", "Consequents"]
    return rules[columns].sort_values(["Lift", "Confidence"], ascending=False).reset_index(drop=True)


def bought_together(rules: pd.DataFrame, product: str, top: int = 8) -> pd.DataFrame:
    """Rules whose 'if' side is exactly `product`: what else tends to be in the basket."""
    single = rules[rules["Antecedents"].map(lambda s: s == frozenset([product]))]
    return single.sort_values(["Lift", "Confidence"], ascending=False).head(top)[["Then", "Support", "Confidence", "Lift"]]


def strongest_rules(rules: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    """Top rules by lift, keeping each item set once (in the direction with the higher confidence)."""
    keyed = rules.assign(Items=[a | c for a, c in zip(rules["Antecedents"], rules["Consequents"])])
    keyed = keyed.sort_values(["Lift", "Confidence"], ascending=False).drop_duplicates("Items")
    return keyed.head(top).drop(columns="Items").reset_index(drop=True)
