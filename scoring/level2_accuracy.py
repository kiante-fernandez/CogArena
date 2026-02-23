import numpy as np
from scipy import stats


def score_accuracy(trial_data: list[dict], metrics_spec: dict) -> dict:
    metric_results = []

    for metric in metrics_spec["metrics"]:
        filtered = _apply_filter(trial_data, metric.get("filter"))
        raw_value = _compute_metric(filtered, metric)

        if raw_value is None:
            metric_results.append({
                "name": metric["name"],
                "raw_value": None,
                "normalized_score": 0.0,
            })
            continue

        human_mean = metric.get("human_mean")
        human_sd = metric.get("human_sd")

        if human_mean is not None and human_sd is not None and human_sd > 0:
            z = (raw_value - human_mean) / human_sd
            if metric.get("direction") == "lower_is_better":
                z = -z
            normalized = float(min(1.0, max(0.0, stats.norm.cdf(z))))
        else:
            normalized = float(min(1.0, max(0.0, raw_value)))

        metric_results.append({
            "name": metric["name"],
            "raw_value": raw_value,
            "normalized_score": normalized,
        })

    if metric_results:
        score = float(np.mean([m["normalized_score"] for m in metric_results]))
    else:
        score = 0.0

    return {"score": score, "metrics": metric_results}


def _apply_filter(trials: list[dict], filter_spec: dict | None) -> list[dict]:
    if not filter_spec:
        return trials
    return [
        t for t in trials
        if all(t.get(k) == v for k, v in filter_spec.items())
    ]


def _compute_metric(trials: list[dict], metric: dict) -> float:
    metric_type = metric["type"]

    # d_prime uses hit_field/fa_field instead of field
    if metric_type == "d_prime":
        hit_field = metric.get("hit_field", "hit")
        fa_field = metric.get("fa_field", "false_alarm")
        hits = sum(1 for t in trials if t.get(hit_field))
        misses = sum(1 for t in trials if t.get("miss"))
        fas = sum(1 for t in trials if t.get(fa_field))
        crs = sum(1 for t in trials if t.get("correct_rejection"))
        n_signal = hits + misses
        n_noise = fas + crs
        if n_signal == 0 or n_noise == 0:
            return None
        hit_rate = hits / n_signal
        fa_rate = fas / n_noise
        half_signal = 1 / (2 * n_signal)
        half_noise = 1 / (2 * n_noise)
        hit_rate = max(half_signal, min(1 - half_signal, hit_rate))
        fa_rate = max(half_noise, min(1 - half_noise, fa_rate))
        return float(stats.norm.ppf(hit_rate) - stats.norm.ppf(fa_rate))

    field = metric["field"]
    values = [t[field] for t in trials if field in t and t[field] is not None]

    if not values:
        return None

    if metric_type == "proportion_correct":
        return sum(1 for v in values if v) / len(values)
    elif metric_type == "mean":
        return float(np.mean(values))
    elif metric_type == "median":
        return float(np.median(values))
    elif metric_type == "sd":
        return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    else:
        raise ValueError(f"Unknown metric type: {metric_type}")
