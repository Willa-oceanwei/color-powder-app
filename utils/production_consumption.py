"""Production-order consumption in grams, based on a recorded recipe."""

import re

FROZEN_CONSUMPTION_KEY = "inventory_consumption_v1"


def parse_pack_value(raw_value):
    if raw_value is None:
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", str(raw_value).strip().replace(",", ""))
    return float(match.group(0)) if match else 0.0


def package_total(row):
    total = 0.0
    for index in range(1, 5):
        total += (
            parse_pack_value(row.get(f"包裝重量{index}")) *
            parse_pack_value(row.get(f"包裝份數{index}"))
        )
    return total


def _weight(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def consumption_in_grams(main, additions, package_total):
    """Apply the stock formula to a main recipe and its recorded additions."""
    pigments = {}
    categories = {}
    if package_total <= 0:
        return {"pigments": pigments, "categories": categories}

    for recipe in (main, *additions):
        weights = {}
        powder_sum = 0.0
        for index in range(1, 9):
            powder_id = str(recipe.get(f"色粉編號{index}", "")).strip()
            weight = _weight(recipe.get(f"色粉重量{index}"))
            powder_sum += weight
            if powder_id:
                weights.setdefault(powder_id, weight)

        for powder_id, weight in weights.items():
            if weight > 0:
                pigments[powder_id] = pigments.get(powder_id, 0.0) + weight * package_total

        category = str(recipe.get("合計類別") or "").strip().upper()
        remainder = _weight(recipe.get("淨重")) - powder_sum
        if category and remainder > 0:
            categories[category] = categories.get(category, 0.0) + remainder * package_total

    return {"pigments": pigments, "categories": categories}
