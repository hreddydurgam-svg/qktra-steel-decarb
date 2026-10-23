"""Global and local Moran's I with permutation tests. A diagnostic only: no model is tuned to its sign."""
import csv

import numpy as np

R_EARTH_KM = 6371.0


def project(lat, lon):
    lat, lon = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    return np.column_stack([R_EARTH_KM * lon * np.cos(lat.mean()), R_EARTH_KM * lat])


def _dist(xy):
    d = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=-1)
    np.fill_diagonal(d, np.inf)
    return d


def knn_weights(xy, k):
    d = _dist(np.asarray(xy, float))
    W = np.zeros_like(d)
    for i in range(len(d)):
        W[i, np.argsort(d[i], kind="stable")[:k]] = 1.0 / k
    return W


def band_weights(xy, radius_km):
    W = (_dist(np.asarray(xy, float)) <= radius_km).astype(float)
    rows = W.sum(1, keepdims=True)
    return np.divide(W, rows, out=np.zeros_like(W), where=rows > 0)


def morans_i(z, W):
    raw = np.asarray(z, float)
    if np.ptp(raw) == 0:
        return float("nan")
    z = raw - np.mean(raw)
    den = float(z @ z)
    if den <= 0 or W.sum() <= 0:
        return float("nan")
    return float(len(z) / W.sum() * (z @ W @ z) / den)


def perm_test(z, W, n_perm=9999, seed=0):
    obs = morans_i(z, W)
    if np.isnan(obs):
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    z = np.asarray(z, float)
    sims = np.array([morans_i(rng.permutation(z), W) for _ in range(n_perm)])
    centre = -1.0 / (len(z) - 1)
    p = (1 + (np.abs(sims - centre) >= abs(obs - centre)).sum()) / (n_perm + 1)
    return obs, float(p)


def load_nodes(path):
    need = ("id", "name", "kind", "lat", "lon", "ef_prod", "dist_km", "ef_transport", "source", "url_or_ref", "retrieved_on")
    rows, bad = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for line, r in enumerate(csv.DictReader(f), start=2):
            if not (r.get("id") or "").strip():
                continue
            miss = [c for c in need if not (r.get(c) or "").strip()]
            if miss:
                bad.append(f"line {line} {r['id']}: empty {', '.join(miss)}")
                continue
            nums, ok = {}, True
            for c in ("lat", "lon", "ef_prod", "dist_km", "ef_transport"):
                try:
                    nums[c] = float(r[c])
                except ValueError:
                    bad.append(f"line {line} {r['id']}: non-numeric {c}")
                    ok = False
                    break
            if ok:
                rows.append({**r, **nums, "material": (r.get("material") or "").strip()})
    if bad:
        raise ValueError("nodes.csv problems:\n  " + "\n  ".join(bad))
    return rows


def delivered_intensity(nodes):
    return np.array([n["ef_prod"] + n["ef_transport"] * n["dist_km"] for n in nodes])


def local_moran(z, W, n_perm=9999, seed=0):
    """Local Moran's I (LISA, Anselin 1995) with a conditional permutation pseudo p-value.

    I_i = (z_i - mean) / m2 * sum_j w_ij (z_j - mean), m2 = sum (z - mean)^2 / n. For each i, z_i is held fixed
    and the other n-1 values are permuted over its neighbours; p is folded (the tail on the side of I_i):
    p = (1 + min(#sims >= I_i, #sims < I_i)) / (n_perm + 1). Quadrant: HH, LL, HL, LH from the signs of
    z_i - mean and its spatial lag. Returns (I, p, quadrant) arrays; a constant z gives nan."""
    z = np.asarray(z, float)
    n = len(z)
    zc = z - z.mean()
    m2 = float(zc @ zc) / n
    if m2 <= 0:
        return np.full(n, np.nan), np.full(n, np.nan), np.array([""] * n)
    lag = W @ zc
    Ii = zc / m2 * lag
    rng = np.random.default_rng(seed)
    p = np.ones(n)
    for i in range(n):
        others, w = np.delete(zc, i), np.delete(W[i], i)
        nb = np.nonzero(w)[0]
        if nb.size == 0:
            continue
        idx = rng.random((n_perm, n - 1)).argsort(axis=1)[:, : nb.size]
        sims = zc[i] / m2 * (others[idx] @ w[nb])
        larger = int((sims >= Ii[i]).sum())
        p[i] = (1 + min(larger, n_perm - larger)) / (n_perm + 1)
    quad = np.array([("H" if a >= 0 else "L") + ("H" if b >= 0 else "L") for a, b in zip(zc, lag)])
    return Ii, p, quad


def purchase_shares(inp, prob, z):
    """Expected share of each charge material in purchased tonnes (spot + contract), from a solution z."""
    cm = inp.contract_mats()
    tot = {m: sum(prob.probs[s] * (z[prob.ix(s, f"q.{m}")] + (z[prob.ix(s, f"qc.{m}")] if m in cm else 0.0))
                  for s in range(prob.K)) for m in inp.mats()}
    t = sum(tot.values())
    return {m: v / t for m, v in tot.items()}


def purchase_weighted(nodes, shares):
    """Delivered intensity x purchase share of the node's material. A material's share is split equally among
    the nodes mapped to it (nodes.csv `material` column); nodes with no material mapping get 0."""
    count = {}
    for n in nodes:
        if n.get("material"):
            count[n["material"]] = count.get(n["material"], 0) + 1
    di = delivered_intensity(nodes)
    return np.array([d * shares.get(n["material"], 0.0) / count[n["material"]] if n.get("material") else 0.0
                     for d, n in zip(di, nodes)])
