"""Dependence-robust p-values by resampling contiguous blocks of trials.

Every other template computes p under an independence assumption that agent
sessions violate: a Browser-Use agent carries its own action history in context
and settles into repeated policies, so 22.6% of proportion tests run at lag-1
rho above 0.3 against 1.5% for the random agent.

``proportion_test`` repairs this with a first-order ``n_eff = n(1-rho)/(1+rho)``
correction. That is a parametric guess — it assumes dependence decays
geometrically with a single rho — and measurement says it over-charges: switching
that template to this bootstrap raises 29 grades and lowers none.

The moving-block bootstrap assumes nothing. Contiguous blocks of length
``l = n^(1/3)`` are resampled with replacement, so dependence WITHIN a block
survives intact while structure across blocks is destroyed. The spread of the
resampled statistic then reflects how much genuinely independent information the
series holds, whatever shape the dependence has.

    p = (1 + #{theta* on the null side}) / (B + 1)

which inverts the percentile confidence interval.

DETERMINISM IS NOT OPTIONAL HERE. Scoring must be reproducible: the same session
must always produce the same score, or a re-score mints a spurious new value and
`scorer_version` stops meaning anything. The seed is therefore derived from the
input series itself rather than from a global RNG, so identical data always
resamples identically, and different data does not share a resampling pattern.

Validated against the archive: reimplementing every template's statistic through
this path reproduced all 1,315 archived test statistics exactly, so only the
inference differs.
"""
from __future__ import annotations

import hashlib

import numpy as np

# 2000 puts the smallest reportable p at 1/2001, two orders of magnitude below
# any threshold_p in use, so the resolution never binds on the decision.
N_RESAMPLES = 2000

# Below this many surviving resamples the percentile inversion is too coarse to
# report; the caller treats it as unmeasurable rather than guessing.
MIN_RETAINED = 100


def _seed_from(*arrays) -> int:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a, dtype=np.float64).tobytes())
    return int.from_bytes(h.digest()[:8], "little")


def default_block_length(n: int) -> float:
    """The standard moving-block rule."""
    return n ** (1.0 / 3.0)


def block_index(n: int, rng, b: int = N_RESAMPLES, length_rule=default_block_length):
    """(b, n) index matrix of contiguous blocks drawn with replacement.

    ``length_rule`` exists so ``scripts/block_bootstrap.py`` can run the
    block-length sensitivity against THIS implementation rather than a copy —
    the published robustness table has to describe the estimator that actually
    scores, and two implementations drifting apart would break that silently.
    """
    length = min(max(2, int(round(length_rule(n)))), n)
    k = int(np.ceil(n / length))
    starts = rng.integers(0, n - length + 1, size=(b, k))
    idx = (starts[:, :, None] + np.arange(length)[None, None, :]).reshape(b, k * length)
    return idx[:, :n], length


def contrast_resamples(values, group, rng, b: int = N_RESAMPLES,
                       length_rule=default_block_length):
    """Bootstrap distribution of ``mean(values[group]) - mean(values[~group])``.

    Split out from :func:`bootstrap_contrast_p` so callers that need the raw
    draws (the sensitivity analysis) share this arithmetic instead of copying it.
    """
    values = np.asarray(values, dtype=float)
    group = np.asarray(group, dtype=bool)
    n = len(values)
    if n < 2 or group.sum() == 0 or (~group).sum() == 0:
        return None, 0

    idx, length = block_index(n, rng, b, length_rule)
    V, G = values[idx], group[idx]
    na, nb = G.sum(1), (~G).sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = np.where(
            (na > 0) & (nb > 0),
            (V * G).sum(1) / np.maximum(na, 1) - (V * ~G).sum(1) / np.maximum(nb, 1),
            np.nan,
        )
    return boot[~np.isnan(boot)], length


def p_from_resamples(boot, null: float, higher: bool) -> float | None:
    """Percentile-inverted one-sided p, or None if too few draws survived."""
    if boot is None or len(boot) < MIN_RETAINED:
        return None
    hits = (boot <= null).sum() if higher else (boot >= null).sum()
    return float((1.0 + hits) / (len(boot) + 1.0))


def bootstrap_contrast_p(values, group, higher: bool,
                         b: int = N_RESAMPLES) -> tuple[float, int] | None:
    """One-sided p for ``mean(values[group]) - mean(values[~group])`` against 0.

    ``values`` and ``group`` must be in TRIAL ORDER — the whole point is to
    resample runs of adjacent trials, so a reordered series measures nothing.

    Returns ``(p_value, block_length)``, or None when the resampling degenerates
    (too few resamples retained a non-empty group on both sides).
    """
    rng = np.random.default_rng(_seed_from(values, group))
    boot, length = contrast_resamples(values, group, rng, b)
    p = p_from_resamples(boot, 0.0, higher)
    return None if p is None else (p, length)
