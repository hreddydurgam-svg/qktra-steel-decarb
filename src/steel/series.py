"""Fit stored price series: normal fit, KS test against it, and linear trend."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import stats


def _ks_norm_stat(z: np.ndarray) -> np.ndarray:
    """KS statistic vs N(0,1) for each row of z (rows are samples)."""
    z = np.sort(z, axis=-1)
    n = z.shape[-1]
    cdf = stats.norm.cdf(z)
    i = np.arange(1, n + 1)
    return np.maximum((i / n - cdf).max(axis=-1), (cdf - (i - 1) / n).max(axis=-1))


def fit_series(values, log=False, n_boot=2000, seed=0) -> dict:
    x = np.asarray(values, float)
    if log:
        if np.any(x <= 0):
            raise ValueError("log fit requires all values > 0")
        x = np.log(x)
    n = int(x.size)
    if n < 3:
        raise ValueError(f"need at least 3 values, got {n}")
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    if sd == 0:
        raise ValueError("sd is 0 (constant values); cannot fit")
    ks = stats.kstest((x - mean) / sd, "norm")
    rng = np.random.default_rng(seed)
    b = rng.normal(mean, sd, size=(n_boot, n))
    z = (b - b.mean(axis=1, keepdims=True)) / b.std(axis=1, ddof=1, keepdims=True)
    boot = _ks_norm_stat(z)
    p_boot = (1 + int(np.sum(boot >= ks.statistic))) / (n_boot + 1)
    lr = stats.linregress(np.arange(n), x)
    return {"n": n, "dist": "lognormal" if log else "normal", "mean": mean, "sd": sd,
            "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue), "ks_p_boot": float(p_boot),
            "trend_slope": float(lr.slope), "trend_p": float(lr.pvalue)}


def fit_file(series_csv, log=False) -> dict:
    with open(series_csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = fit_series([float(r["value"]) for r in rows], log=log)
    out["first_date"], out["last_date"] = rows[0]["date"], rows[-1]["date"]
    return out


def write_fits(series_dir, log_ids=()):
    for p in sorted(Path(series_dir).glob("*.csv")):
        fit = fit_file(p, log=p.stem in log_ids)
        p.with_name(p.stem + ".fit.json").write_text(json.dumps(fit, indent=2) + "\n", encoding="utf-8")
