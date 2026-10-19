"""Uncertainty for results: cluster bootstrap CIs and paired differences.

Questions about the same company are not independent, so we resample companies (the
clusters) with replacement, as pre-registered in docs/hypotheses.md section 4. Items
without a company are their own cluster.
"""

from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel


class Estimate(BaseModel):
    mean: float | None
    lo: float | None
    hi: float | None
    n: int


def cluster_bootstrap(
    values: Sequence[float | None],
    clusters: Sequence[str],
    n_boot: int = 2000,
    seed: int = 20261013,
    alpha: float = 0.05,
) -> Estimate:
    pairs = [(v, c) for v, c in zip(values, clusters, strict=True) if v is not None]
    if not pairs:
        return Estimate(mean=None, lo=None, hi=None, n=0)
    groups: dict[str, list[float]] = defaultdict(list)
    for v, c in pairs:
        groups[c].append(float(v))
    keys = list(groups)
    sums = np.array([sum(groups[k]) for k in keys])
    counts = np.array([len(groups[k]) for k in keys])
    mean = float(sums.sum() / counts.sum())
    if len(keys) < 2:
        return Estimate(mean=mean, lo=None, hi=None, n=len(pairs))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(n_boot, len(keys)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return Estimate(mean=mean, lo=float(lo), hi=float(hi), n=len(pairs))


def paired_difference(
    a: dict[str, float | None],
    b: dict[str, float | None],
    cluster_of: dict[str, str],
    **kw,
) -> Estimate:
    """Mean of (a - b) over items both systems answered, with a cluster bootstrap CI."""
    shared = [k for k in a if k in b and a[k] is not None and b[k] is not None]
    diffs = [a[k] - b[k] for k in shared]  # type: ignore[operator]
    return cluster_bootstrap(diffs, [cluster_of.get(k, k) for k in shared], **kw)
