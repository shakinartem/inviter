from __future__ import annotations


BIN_COUNT = 10


def build_monotonic_mapping(
    predictions: list[float],
    outcomes: list[int],
    *,
    prior_strength: float = 8.0,
) -> list[dict]:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    prior = max(float(prior_strength), 1.0)
    bins: list[dict] = []
    width = 1.0 / BIN_COUNT
    for index in range(BIN_COUNT):
        lower = index * width
        upper = 1.0 if index == BIN_COUNT - 1 else (index + 1) * width
        selected = [
            (min(max(float(p), 0.0), 1.0), 1 if int(y) else 0)
            for p, y in zip(predictions, outcomes)
            if lower <= min(max(float(p), 0.0), 1.0) <= upper
            and (index == BIN_COUNT - 1 or min(max(float(p), 0.0), 1.0) < upper)
        ]
        midpoint = (lower + upper) / 2.0
        mean_raw = sum(p for p, _ in selected) / len(selected) if selected else midpoint
        successes = sum(y for _, y in selected)
        observed = successes / len(selected) if selected else None
        posterior = (successes + prior * mean_raw) / (len(selected) + prior)
        bins.append(
            {
                "lower_bound": round(lower, 4),
                "upper_bound": round(upper, 4),
                "samples": len(selected),
                "mean_raw_prediction": round(mean_raw, 6),
                "observed_rate": round(observed, 6) if observed is not None else None,
                "calibrated_probability": float(posterior),
                "_weight": len(selected) + prior,
            }
        )

    blocks: list[dict] = []
    for index, item in enumerate(bins):
        block = {
            "start": index,
            "end": index,
            "weight": float(item["_weight"]),
            "value": float(item["calibrated_probability"]),
        }
        blocks.append(block)
        while len(blocks) >= 2 and blocks[-2]["value"] > blocks[-1]["value"]:
            right = blocks.pop()
            left = blocks.pop()
            weight = left["weight"] + right["weight"]
            value = (left["value"] * left["weight"] + right["value"] * right["weight"]) / weight
            blocks.append(
                {
                    "start": left["start"],
                    "end": right["end"],
                    "weight": weight,
                    "value": value,
                }
            )

    for block in blocks:
        for index in range(block["start"], block["end"] + 1):
            bins[index]["calibrated_probability"] = round(min(max(block["value"], 0.0), 1.0), 6)
            bins[index].pop("_weight", None)
    return bins


def apply_mapping(probability: float, mapping: list[dict]) -> float:
    p = min(max(float(probability), 0.0), 1.0)
    if not mapping:
        return p
    for index, item in enumerate(mapping):
        lower = float(item["lower_bound"])
        upper = float(item["upper_bound"])
        if lower <= p < upper or (index == len(mapping) - 1 and p <= upper):
            return min(max(float(item["calibrated_probability"]), 0.0), 1.0)
    return p


def activation_eligible(
    *,
    test_count: int,
    raw_brier: float,
    calibrated_brier: float,
    raw_ece: float,
    calibrated_ece: float,
    raw_bias: float,
    calibrated_bias: float,
) -> bool:
    return (
        int(test_count) >= 20
        and calibrated_brier <= raw_brier + 0.002
        and calibrated_ece <= raw_ece + 0.02
        and abs(calibrated_bias) <= abs(raw_bias) + 0.02
    )
