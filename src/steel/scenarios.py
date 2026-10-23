"""Monte Carlo price sampling (Gaussian copula) and k-means scenario reduction.

Price dependence: Spearman rank correlation of the stored monthly series (data/correlation.csv, written by
write_correlation). sample() converts Spearman rho to the Gaussian-copula Pearson parameter 2 sin(pi rho / 6)
and repairs the result to the nearest positive semi-definite correlation matrix (eigenvalue clip)."""
import csv
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.cluster.vq import kmeans2


MIN_OVERLAP = 24   # fewer overlapping months than this: the pair is set to 0 (not estimated)


def _monthly(path):
    """{YYYY-MM: value}; daily rows are averaged within their month."""
    acc = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            acc.setdefault(r["date"][:7], []).append(float(r["value"]))
    return {m: float(np.mean(v)) for m, v in acc.items()}


def spearman_matrix(series_dir, ids, min_overlap=MIN_OVERLAP):
    """Spearman rho on the overlapping months of each pair of series (series_dir/<id>.csv).
    Returns (R, N): N[i, j] = overlapping months. Pairs with N < min_overlap, or an id without a series, get 0."""
    from scipy import stats
    series = {k: _monthly(Path(series_dir) / f"{k}.csv") for k in ids if (Path(series_dir) / f"{k}.csv").exists()}
    d = len(ids)
    R, N = np.eye(d), np.zeros((d, d), int)
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i >= j or a not in series or b not in series:
                continue
            common = sorted(set(series[a]) & set(series[b]))
            N[i, j] = N[j, i] = len(common)
            if len(common) >= min_overlap:
                rho = stats.spearmanr([series[a][m] for m in common], [series[b][m] for m in common]).statistic
                R[i, j] = R[j, i] = float(rho)
    return R, N


def write_correlation(series_dir, ids, out_csv, min_overlap=MIN_OVERLAP):
    R, N = spearman_matrix(series_dir, ids, min_overlap)
    lines = [f"# ids: {','.join(ids)}",
             f"# Spearman rank correlation of monthly series in {Path(series_dir).name}/; pairs with < {min_overlap} "
             "overlapping months or without a series are 0",
             "# overlap months: " + "; ".join(f"{ids[i]}~{ids[j]}={N[i, j]}" for i in range(len(ids))
                                               for j in range(i + 1, len(ids)))]
    lines += [",".join(repr(float(x)) for x in row) for row in R]
    Path(out_csv).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return R, N


def load_correlation(path, ids):
    """Matrix aligned to ids (order from the '# ids:' header); ids absent from the file get 0 off-diagonal."""
    text = Path(path).read_text(encoding="utf-8").splitlines()
    head = next(ln for ln in text if ln.startswith("# ids:"))
    file_ids = [x.strip() for x in head.split(":", 1)[1].split(",")]
    M = np.array([[float(x) for x in ln.split(",")] for ln in text if ln.strip() and not ln.startswith("#")])
    pos = {k: i for i, k in enumerate(file_ids)}
    out = np.eye(len(ids))
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i != j and a in pos and b in pos:
                out[i, j] = M[pos[a], pos[b]]
    return out


def copula_corr(rho):
    """Spearman rho -> Gaussian-copula Pearson 2 sin(pi rho / 6), repaired to the nearest PSD correlation matrix."""
    P = 2.0 * np.sin(np.pi * np.asarray(rho, float) / 6.0)
    P = (P + P.T) / 2.0
    np.fill_diagonal(P, 1.0)
    w, V = np.linalg.eigh(P)
    if w.min() < 0:
        P = (V * np.clip(w, 0.0, None)) @ V.T
        dd = np.sqrt(np.diag(P))
        P = P / np.outer(dd, dd)
        P = (P + P.T) / 2.0
        np.fill_diagonal(P, 1.0)
    return P


def sample(inp, n, seed, corr=None):
    """corr: Spearman rank correlation matrix in inp.stochastic_ids() order (None = independent)."""
    ids = inp.stochastic_ids()
    rng = np.random.default_rng(seed)
    corr = np.eye(len(ids)) if corr is None else copula_corr(corr)
    u = stats.norm.cdf(rng.multivariate_normal(np.zeros(len(ids)), corr, size=n))
    out = np.empty_like(u)
    for j, k in enumerate(ids):
        d, mean = inp.dist[k], inp.v[k]
        if d.kind == "normal":
            out[:, j] = stats.norm.ppf(u[:, j], mean, d.low)
        elif d.kind == "lognormal":
            s2 = np.log(1.0 + (d.low / mean) ** 2)
            out[:, j] = stats.lognorm.ppf(u[:, j], s=np.sqrt(s2), scale=mean * np.exp(-s2 / 2.0))
        else:  # triangular
            out[:, j] = stats.triang.ppf(u[:, j], c=(mean - d.low) / (d.high - d.low),
                                         loc=d.low, scale=d.high - d.low)
    return np.maximum(out, 1e-9)


def reduce(samples, k, seed):
    mu, sd = samples.mean(0), samples.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    _, labels = kmeans2((samples - mu) / sd, k, minit="++", seed=seed)
    keep = [c for c in range(k) if (labels == c).any()]
    cen = np.array([samples[labels == c].mean(0) for c in keep])
    pr = np.array([(labels == c).mean() for c in keep])
    return cen, pr / pr.sum()


def to_scenarios(inp, centroids, probs):
    ids = inp.stochastic_ids()
    return [(float(p), dict(zip(ids, map(float, row)))) for p, row in zip(probs, centroids)]


def choose_k(cost_fn, inp, samples, seed, tol=1e-3, kmax=20):
    """Smallest K whose optimal cost differs from K-1 by less than tol (relative)."""
    hist, prev = [], None
    for k in range(2, kmax + 1):
        cost = cost_fn(to_scenarios(inp, *reduce(samples, k, seed)))
        hist.append((k, cost))
        if prev is not None and abs(cost - prev) <= tol * abs(prev):
            return k, hist
        prev = cost
    return kmax, hist
