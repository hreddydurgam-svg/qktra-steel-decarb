"""Independent cross-checks of the study's key numbers.

Each check_* function recomputes a number by a different route from the code under test (own formulas,
own loops) and returns dict(name, value_ours, value_check, tol, ok). "ours" is what the repository code or
the stored results file says; "check" is the independent recomputation. Extra keys carry detail.

Run:  python colab/crosscheck.py --results results_v2/quick
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

A12_MIN = 0.64
COST_METRICS = ("cost", "gap_pct", "evals_to_best")
N_SAMPLES_QUICK, N_SAMPLES_FULL = 300, 5000


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _close(a, b, tol):
    """Equal within tol (relative for large values, absolute below 1); nan == nan."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= tol * max(1.0, abs(b))


def _result(name, ours, check, tol, ok, **extra):
    return {"name": name, "value_ours": ours, "value_check": check, "tol": tol, "ok": bool(ok), **extra}


# ---------------------------------------------------------------- 1. inputs
def check_inputs(root=ROOT):
    """Every id in inputs.csv loads; triangular rows satisfy low <= mode <= high; required ids present."""
    root = Path(root)
    csv_path, struct_path = root / "data" / "inputs.csv", root / "data" / "structure.json"
    rows = [r for r in _rows(csv_path) if (r.get("id") or "").strip()]
    ids = [r["id"].strip() for r in rows]
    problems = []
    if len(set(ids)) != len(ids):
        problems.append("duplicate ids")
    table = []
    for r in rows:
        table.append((r["id"].strip(), r["value"], r["unit"], r["source_type"]))
        kind = (r["distribution"] or "fixed").strip().lower()
        try:
            val, low, high = (float(r[k]) if r[k].strip() else 0.0 for k in ("value", "low", "high"))
        except ValueError:
            problems.append(f"{r['id']}: non-numeric")
            continue
        if kind == "triangular" and not (low <= val <= high and low < high):
            problems.append(f"{r['id']}: triangular needs low <= mode <= high")
        if kind in ("normal", "lognormal") and low <= 0:
            problems.append(f"{r['id']}: {kind} needs sd > 0")
    loaded = 0
    try:
        from steel.data import load_inputs, required_ids
        inp = load_inputs(csv_path, struct_path)
        loaded = len(inp.v)
        missing = [i for i in required_ids(inp.struct) if i not in inp.v]
        if missing:
            problems.append(f"missing required ids: {missing}")
    except Exception as exc:  # noqa: BLE001  any load failure is a check failure
        problems.append(f"load_inputs failed: {str(exc)[:200]}")
    return _result("inputs", loaded, len(set(ids)), 0, loaded == len(set(ids)) and not problems,
                   table=table, problems=problems)


def print_inputs_table(table):
    print(f"{'id':32s} {'value':>12s}  {'unit':26s} source_type")
    for i, v, u, s in table:
        print(f"{i:32s} {v:>12s}  {u[:26]:26s} {s}")


# ---------------------------------------------------------------- scenarios and solving
def scenarios_for(root=ROOT, results=None, n_samples=None):
    """Rebuild the price scenarios the study used: Monte Carlo sample (seed 0), k-means reduction to the k
    stored in <results>/scenario_k.csv (or the choose_k rule when that file is absent)."""
    from steel.data import load_inputs
    from steel.model import build, solve
    from steel.scenarios import choose_k, reduce, sample, to_scenarios
    root = Path(root)
    inp = load_inputs(root / "data" / "inputs.csv", root / "data" / "structure.json")
    if n_samples is None:
        n_samples = N_SAMPLES_QUICK if (results is None or Path(results).name == "quick") else N_SAMPLES_FULL
    corr_file = root / "data" / "correlation.csv"
    from steel.scenarios import load_correlation
    corr = load_correlation(corr_file, inp.stochastic_ids()) if corr_file.exists() else None
    samples = sample(inp, n_samples, seed=0, corr=corr)
    kfile = Path(results) / "scenario_k.csv" if results is not None else None
    if kfile is not None and kfile.exists():
        k = int(next(r["k"] for r in _rows(kfile) if r["chosen"] == "True"))
    else:
        k, _ = choose_k(lambda sc: solve(build(inp, sc)).cost, inp, samples, seed=0)
    return to_scenarios(inp, *reduce(samples, k, seed=0))


def _inputs(root):
    from steel.data import load_inputs
    root = Path(root)
    return load_inputs(root / "data" / "inputs.csv", root / "data" / "structure.json")


def hand_objective(inp, scens, prob, z):
    """Expected cost from the solution vector by a plain loop over the cost terms (no prob.c @ z)."""
    st = inp.struct
    ny, nx = len(prob.y_names), len(prob.x_names)
    y = {n: z[i] for i, n in enumerate(prob.y_names)}
    total = 0.0
    for t in st["solar_tiers"]:
        total += inp.v[f"sol.{t}.fix"] * y[f"sol.{t}"]
    for u in st["ppa_tiers"]:
        total += inp.v[f"ppa.{u}.fix"] * y[f"ppa.{u}"]
    for o in ("whr", "pre", "hot", "gas", "shred"):
        total += inp.v[f"opt.{o}.fix"] * y[o]
    contract = [m["name"] for m in st["materials"] if m["contract"]]
    for m in contract:
        total += inp.v[f"con.{m}.fee"] * y[f"con.{m}"]
    for s, (p, over) in enumerate(scens):
        w = {**inp.v, **over}
        x = {n: z[ny + s * nx + j] for j, n in enumerate(prob.x_names)}
        sc = 0.0
        for m in st["materials"]:
            n = m["name"]
            freight = w["freight.tariff"] * w[f"mat.{n}.dist"]
            sc += (w[f"mat.{n}.price"] + freight) * x[f"q.{n}"]
            if m["contract"]:
                sc += ((1.0 - w[f"con.{n}.disc"]) * w[f"mat.{n}.price"] + freight) * x[f"qc.{n}"]
        sc += w["grid.price"] * x["g"] + w["sol.var"] * x["sol"] + w["ppa.price"] * x["ppa"]
        sc += w["fo.price"] * w["opt.pre.fuel"] * x["sv"] + w["fo.price"] * x["fo"] + w["ng.price"] * x["ng"]
        sc += w["plant.demand"] * sum(val for key, val in w.items() if key.startswith("const."))
        total += p * sc
    return total


def check_objective(root=ROOT, scens=None, results=None):
    """Base stochastic MILP: hand-recomputed objective equals solver cost; encoding.evaluate agrees and is feasible."""
    from steel.encoding import TOL, evaluate
    from steel.model import build, solve
    inp = _inputs(root)
    scens = scens if scens is not None else scenarios_for(root, results)
    prob = build(inp, scens)
    sol = solve(prob)
    hand = hand_objective(inp, scens, prob, sol.z) if sol.ok else float("nan")
    cost_e, _, viol = evaluate(prob, sol.z) if sol.ok else (float("nan"), 0.0, float("inf"))
    tol = 1e-9
    ok = (sol.ok and _close(hand, sol.cost, tol) and viol <= TOL and abs(cost_e - hand) <= 1e-6 * abs(hand)
          and abs(sum(p for p, _ in scens) - 1.0) <= 1e-9)
    chosen = [n for n in prob.y_names if sol.ok and sol.z[prob.y_names.index(n)] > 0.5]
    return _result("objective", float(sol.cost), float(hand), tol, ok, viol=float(viol),
                   cost_evaluate=float(cost_e), emissions=float(sol.emis), chosen=chosen, k=len(scens))


def check_pareto(root=ROOT, results=None, scens=None):
    """Cost-minimising end of the Pareto front equals the base MILP cost; costs rise as eps tightens; file matches."""
    from steel.model import build, pareto, solve
    results = Path(results)
    inp = _inputs(root)
    scens = scens if scens is not None else scenarios_for(root, results)
    file_rows = _rows(results / "pareto.csv")
    front = pareto(inp, scens, n=len(file_rows))
    base = solve(build(inp, scens)).cost
    costs = [c for _, c, _ in front]
    end_tol, file_tol = 2e-6, 1e-6   # two separate MILPs, each stopped at mip_rel_gap 1e-6
    end_ok = bool(costs) and _close(costs[0], base, end_tol)
    mono = all(b >= a * (1 - 1e-6) for a, b in zip(costs, costs[1:]))
    same_n = len(front) == len(file_rows)
    file_ok = same_n and all(_close(c, float(r["cost"]), file_tol) and _close(e, float(r["eps"]), file_tol)
                             for (e, c, _), r in zip(front, file_rows))
    worst = max((abs(c - float(r["cost"])) / abs(float(r["cost"])) for (_, c, _), r in zip(front, file_rows)), default=0.0)
    return _result("pareto", float(costs[0]) if costs else float("nan"), float(base), end_tol,
                   end_ok and mono and file_ok, monotone=mono, file_match=file_ok, n_points=len(front),
                   max_rel_diff_vs_file=float(worst))


# ---------------------------------------------------------------- 2. Moran's I
def _project(lat, lon):
    """Equirectangular projection to km (own copy of the formula): x = R lon cos(mean lat), y = R lat."""
    la, lo = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    return np.column_stack([6371.0 * lo * math.cos(la.mean()), 6371.0 * la])


def _pair_dist(xy):
    n = len(xy)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            d[i, j] = math.hypot(xy[i, 0] - xy[j, 0], xy[i, 1] - xy[j, 1])
    return d


def _knn_row_standardised(xy, k):
    d = _pair_dist(np.asarray(xy, float))
    n = len(d)
    W = np.zeros((n, n))
    for i in range(n):
        nearest = sorted((j for j in range(n) if j != i), key=lambda j: (d[i, j], j))[:k]
        for j in nearest:
            W[i, j] = 1.0 / k
    return W


def _band_row_standardised(xy, radius):
    d = _pair_dist(np.asarray(xy, float))
    n = len(d)
    W = np.zeros((n, n))
    for i in range(n):
        near = [j for j in range(n) if j != i and d[i, j] <= radius]
        for j in near:
            W[i, j] = 1.0 / len(near)
    return W


def _moran(z, W):
    """Textbook I = (n / S0) * (z' W z) / (z' z), z centred, S0 = sum of all weights."""
    z = np.asarray(z, float)
    zc = z - z.mean()
    return float(len(z) / W.sum() * (zc @ W @ zc) / (zc @ zc))


def check_moran(root=ROOT, results=None, n_perm=999, seed=12345):
    """Moran's I from nodes.csv delivered intensity with own kNN/band weights equals moran.csv (1e-9).
    The 999-permutation p-value is informational (compared to the file at +-0.02, reported in perm_p_ok)."""
    results, root = Path(results), Path(root)
    nodes = _rows(root / "data" / "nodes.csv")
    nodes = [r for r in nodes if (r.get("id") or "").strip()]
    lat = [float(r["lat"]) for r in nodes]
    lon = [float(r["lon"]) for r in nodes]
    z = np.array([float(r["ef_prod"]) + float(r["ef_transport"]) * float(r["dist_km"]) for r in nodes])
    xy = _project(lat, lon)
    d = _pair_dist(xy)
    radius = float(np.median(d[d > 0]))
    weights = {f"knn{k}": _knn_row_standardised(xy, k) for k in (4, 6, 8)}
    weights["band_median"] = _band_row_standardised(xy, radius)
    file_rows = {r["weights"]: r for r in _rows(results / "moran.csv")}
    rng = np.random.default_rng(seed)
    tol, perm_p, perm_ok, diffs, ok = 1e-9, {}, {}, {}, set(weights) == set(file_rows)
    ours = check = float("nan")
    for name, W in weights.items():
        mine = _moran(z, W)
        theirs = float(file_rows[name]["moran_i"]) if name in file_rows else float("nan")
        diffs[name] = abs(mine - theirs)
        ok &= name in file_rows and _close(mine, theirs, tol)
        centre = -1.0 / (len(z) - 1)
        sims = np.array([_moran(rng.permutation(z), W) for _ in range(n_perm)])
        perm_p[name] = float((1 + (np.abs(sims - centre) >= abs(mine - centre)).sum()) / (n_perm + 1))
        perm_ok[name] = name in file_rows and abs(perm_p[name] - float(file_rows[name]["p"])) <= 0.02
        if name == "knn4":
            ours, check = theirs, mine
    return _result("moran", ours, check, tol, ok, perm_p=perm_p, perm_p_ok=perm_ok,
                   max_abs_diff=max(diffs.values()), n=len(z), band_radius_km=radius)


# ---------------------------------------------------------------- 3. quantum kernel
def _apply_1q(psi, gate, qubit, n):
    axis = n - 1 - qubit                      # qubit i is bit i of the basis index (LSB first)
    out = np.tensordot(gate, psi, axes=([1], [axis]))
    return np.moveaxis(out, 0, axis)


def _apply_cnot(psi, control, target, n):
    ca, ta = n - 1 - control, n - 1 - target
    out = psi.copy()
    sl = [slice(None)] * n
    sl[ca] = 1
    out[tuple(sl)] = np.flip(psi[tuple(sl)], axis=ta - (1 if ta > ca else 0))
    return out


def _zz_state_by_gates(x, reps=2):
    """Explicit gate-by-gate ZZ feature map: reps x [H on all qubits, then phase layer], from |0...0>.
    Convention matched to src/steel/qkernel.py: single-qubit phase exp(+i x_i Z_i), pair phase
    exp(+i (pi-x_i)(pi-x_j) Z_i Z_j), Z eigenvalue +1 for |0>. In Rz(t) = exp(-i t Z / 2) language that is
    Rz(-2 x_i); the brief's Rz(2 x_i) flips every phase sign, giving the complex-conjugate state and the
    same |<psi|phi>|^2. Pair phase is built as CNOT(i,j) . Rz-like(j) . CNOT(i,j)."""
    x = np.asarray(x, float)
    n = x.size
    psi = np.zeros((2,) * n, complex)
    psi[(0,) * n] = 1.0
    had = np.array([[1, 1], [1, -1]]) / math.sqrt(2.0)
    for _ in range(reps):
        for q in range(n):
            psi = _apply_1q(psi, had, q, n)
        for q in range(n):
            psi = _apply_1q(psi, np.diag([np.exp(1j * x[q]), np.exp(-1j * x[q])]), q, n)
        for i in range(n):
            for j in range(i + 1, n):
                theta = (math.pi - x[i]) * (math.pi - x[j])
                psi = _apply_cnot(psi, i, j, n)
                psi = _apply_1q(psi, np.diag([np.exp(1j * theta), np.exp(-1j * theta)]), j, n)
                psi = _apply_cnot(psi, i, j, n)
    return psi.reshape(-1)


def check_kernel(n_points=4, n_features=4, seed=2024, kernel_fn=None, reps=2):
    """|<psi(x)|psi(y)>|^2 from the gate-by-gate states equals qkernel.zz_kernel (1e-10); K symmetric, diag 1, PSD."""
    if kernel_fn is None:
        from steel.qkernel import zz_kernel
        kernel_fn = lambda X: zz_kernel(X, reps=reps)  # noqa: E731
    X = np.random.default_rng(seed).uniform(0.0, math.pi, size=(n_points, n_features))
    S = np.array([_zz_state_by_gates(x, reps) for x in X])
    mine = np.array([[abs(np.vdot(a, b)) ** 2 for b in S] for a in S])
    theirs = np.asarray(kernel_fn(X), float)
    diff = float(np.abs(mine - theirs).max())
    tol = 1e-10
    sym = float(np.abs(theirs - theirs.T).max())
    diag = float(np.abs(np.diag(theirs) - 1.0).max())
    min_eig = float(np.linalg.eigvalsh((theirs + theirs.T) / 2).min())
    ok = diff <= tol and sym <= tol and diag <= tol and min_eig >= -tol
    return _result("kernel", float(theirs[0, 1]), float(mine[0, 1]), tol, ok, max_abs_diff=diff,
                   asym=sym, diag_err=diag, min_eig=min_eig)


# ---------------------------------------------------------------- 4. benchmark gap and statistics
def check_gap(results):
    """gap_pct = 100 (cost - ref_cost) / |ref_cost| for feasible rows; infeasible rows carry no gap. Tolerance 1e-9."""
    rows = _rows(Path(results) / "bench.csv")
    tol, worst, ok, n = 1e-9, 0.0, True, 0
    ours = check = 0.0
    for r in rows:
        if r["feasible"] == "True":
            mine = 100.0 * (float(r["cost"]) - float(r["ref_cost"])) / abs(float(r["ref_cost"]))
            if r["gap_pct"] == "":
                ok = False
                continue
            theirs = float(r["gap_pct"])
            n += 1
            err = abs(mine - theirs) / max(1.0, abs(theirs))
            if err > worst:
                worst, ours, check = err, theirs, mine
            ok &= err <= tol
        else:
            ok &= r["gap_pct"] == ""
    return _result("gap", ours, check, tol, ok and n > 0, n_feasible_rows=n, worst_err=worst)


def _a12(x, y):
    """P(x < y) + 0.5 P(x = y), by explicit double loop."""
    if not len(x) or not len(y):
        return float("nan")
    s = 0.0
    for a in x:
        for b in y:
            s += 1.0 if a < b else (0.5 if a == b else 0.0)
    return s / (len(x) * len(y))


def _holm(pvals):
    """Holm step-down: sort ascending, multiply by (m - rank), take the running maximum, cap at 1."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


def _pair_values(bench, method, metric):
    """{(instance, seed): value}. gap/cost/evals_to_best: feasible rows only; viol and evals_to_* targets: every
    row (a miss is stored as budget + 1); feasible: 1.0 / 0.0 flag."""
    out = {}
    for r in bench:
        if r["method"] != method:
            continue
        if metric == "feasible":
            out[(r["instance"], r["seed"])] = 1.0 if r["feasible"] == "True" else 0.0
            continue
        if r[metric] == "" or (metric in COST_METRICS and r["feasible"] != "True"):
            continue
        out[(r["instance"], r["seed"])] = float(r[metric])
    return out


def _binom_two_sided(k, n):
    """Exact two-sided binomial test p for k successes in n trials at 0.5 (symmetric: double the smaller tail)."""
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2.0 ** n
    return min(1.0, 2.0 * tail)


def recompute_stats(bench, pairs):
    """Own recomputation of every stats_pairs row: paired Wilcoxon (scipy) or exact McNemar (own binomial sum),
    own A12, own Holm within each `family` column value."""
    out = []
    for pr in pairs:
        ta, tb = _pair_values(bench, pr["a"], pr["metric"]), _pair_values(bench, pr["b"], pr["metric"])
        keys = [k for k in ta if k in tb]
        xa, xb = [ta[k] for k in keys], [tb[k] for k in keys]
        if pr["metric"] == "feasible":
            n01 = sum(1 for a, b in zip(xa, xb) if a == 1.0 and b == 0.0)
            n10 = sum(1 for a, b in zip(xa, xb) if a == 0.0 and b == 1.0)
            p = _binom_two_sided(n01, n01 + n10)
            a12 = _a12([1.0 - a for a in xa], [1.0 - b for b in xb])      # infeasible flag, lower is better
        else:
            same = len(keys) == 0 or all(abs(a - b) <= 1e-8 * max(1.0, abs(b)) for a, b in zip(xa, xb))
            p = 1.0 if same else float(stats.wilcoxon(xa, xb).pvalue)
            a12 = _a12(xa, xb)
        out.append({"n": len(keys), "p": p, "a12": a12, "share_a": sum(xa) / len(xa) if xa else float("nan"),
                    "share_b": sum(xb) / len(xb) if xb else float("nan")})
    for fam in sorted({pr.get("family", "primary") for pr in pairs}):
        idx = [i for i, pr in enumerate(pairs) if pr.get("family", "primary") == fam]
        for i, h in zip(idx, _holm([out[i]["p"] for i in idx])):
            out[i]["p_holm"] = h
    return out


def check_stats(results):
    """Every row of stats_pairs.csv (n, p, p_holm, A12) recomputed from bench.csv. Tolerance 1e-9."""
    results = Path(results)
    bench, pairs = _rows(results / "bench.csv"), _rows(results / "stats_pairs.csv")
    mine = recompute_stats(bench, pairs)
    tol, worst, ok = 1e-9, 0.0, len(mine) == len(pairs) and len(pairs) > 0
    ours = check = 0.0
    for pr, m in zip(pairs, mine):
        ok &= int(pr["n"]) == m["n"]
        for key in ("p", "p_holm", "a12"):
            theirs = float(pr[key])
            ok &= _close(m[key], theirs, tol)
            if not (math.isnan(theirs) and math.isnan(m[key])):
                err = abs(m[key] - theirs)
                if err >= worst:
                    worst, ours, check = err, theirs, m[key]
    return _result("stats", ours, check, tol, ok, n_rows=len(pairs), worst_abs_err=worst, recomputed=mine)


def check_evals(results):
    """evals_to_1pct / evals_to_01pct re-derived from each row's improvement trace and ref_cost: first eval with
    100 (c - ref) / |ref| <= 1 (0.1); budget + 1 if never. The trace ends at the run's cost for feasible rows and
    is empty for infeasible rows."""
    rows = _rows(Path(results) / "bench.csv")
    bad, n = [], 0
    for r in rows:
        ref, steps = float(r["ref_cost"]), [t.split(":") for t in r["trace"].split(";") if t]
        if r["feasible"] == "True":
            if not steps or float(steps[-1][1]) != float(r["cost"]):
                bad.append((r["instance"], r["method"], r["seed"], "trace end"))
        elif steps:
            bad.append((r["instance"], r["method"], r["seed"], "trace on infeasible run"))
        for col, pct in (("evals_to_1pct", 1.0), ("evals_to_01pct", 0.1)):
            first = next((int(e) for e, c in steps if 100.0 * (float(c) - ref) / abs(ref) <= pct), int(r["budget"]) + 1)
            n += 1
            if int(r[col]) != first:
                bad.append((r["instance"], r["method"], r["seed"], col))
    return _result("evals", len(bad), 0, 0, not bad and n > 0, n_checked=n, mismatches=bad[:10])


def _feasibility_ok(share_a, share_b, p_holm):
    """H2/H7: a's feasibility not significantly worse than b's (B3): only a higher b share with p_holm < 0.05 fails."""
    return not (share_b > share_a and p_holm < 0.05)


def check_hypotheses(results):
    """H1..H8 yes/no re-derived from recomputed stats and the stored stage_a / moran files; must equal hypotheses.csv.
    Rules (README "Hypothesis rules"): H1 median |scaled gap| < 1e-4 %; H2 Q-K vs B3 evals_to_1pct hit AND feasible
    share not significantly worse (fails only if B3's share is higher with McNemar p_holm < 0.05); H3 Q vs Q-K
    evals_to_1pct hit; H4 Q vs Q-RBF evals_to_1pct p_holm < 0.05 and A12 >= 0.64 or <= 0.36; H5 any Q-Ri with a hit
    on viol or evals_to_1pct; H6 >= 3 of 4 weight choices p < 0.05; H7 as H2 for Q vs B3; H8 Q vs Q-NOLP gap_pct hit.
    hit = p_holm < 0.05 and A12 >= 0.64 (primary family)."""
    results = Path(results)
    bench, pairs = _rows(results / "bench.csv"), _rows(results / "stats_pairs.csv")
    mine = recompute_stats(bench, pairs)
    by = {(p["a"], p["b"], p["metric"]): m for p, m in zip(pairs, mine) if p["family"] == "primary"}

    def hit(m):
        return m["p_holm"] < 0.05 and m["a12"] >= A12_MIN

    scaled = [abs(float(r["gap_pct"])) for r in _rows(results / "stage_a.csv")
              if r["encoding"] == "scaled" and r["gap_pct"] != ""]
    pvals = [float(r["p"]) for r in _rows(results / "moran.csv")]
    def hit_and_feasible(a):
        f = by[(a, "B3", "feasible")]
        return hit(by[(a, "B3", "evals_to_1pct")]) and _feasibility_ok(f["share_a"], f["share_b"], f["p_holm"])

    h4 = by[("Q", "Q-RBF", "evals_to_1pct")]
    h = {"H1": bool(scaled) and float(np.median(scaled)) < 1e-4,
         "H2": hit_and_feasible("Q-K"),
         "H3": hit(by[("Q", "Q-K", "evals_to_1pct")]),
         "H4": h4["p_holm"] < 0.05 and abs(h4["a12"] - 0.5) >= A12_MIN - 0.5,
         "H5": any(hit(m) for (a, b, met), m in by.items() if a == "Q" and b.startswith("Q-R") and b[3:].isdigit()
                   and met in ("viol", "evals_to_1pct")),
         "H6": sum(1 for p in pvals if p < 0.05) >= 3,
         "H7": hit_and_feasible("Q"),
         "H8": hit(by[("Q", "Q-NOLP", "gap_pct")])}
    mine_s = {k: ("yes" if v else "no") for k, v in h.items()}
    file_s = {r["id"]: r["supported"] for r in _rows(results / "hypotheses.csv")}
    ok = mine_s == file_s
    fmt = lambda d: ",".join(f"{k}={d.get(k, '?')}" for k in sorted(set(mine_s) | set(file_s)))  # noqa: E731
    return _result("hypotheses", fmt(file_s), fmt(mine_s), "exact", ok)


# ---------------------------------------------------------------- driver
CHECKS = ["inputs", "objective", "pareto", "moran", "kernel", "gap", "evals", "stats", "hypotheses"]


def run_all(root=ROOT, results=None, only=None):
    root, results = Path(root), Path(results) if results is not None else root / "results_v2" / "quick"
    only = only or CHECKS
    scens = scenarios_for(root, results) if {"objective", "pareto"} & set(only) else None
    fns = {"inputs": lambda: check_inputs(root),
           "objective": lambda: check_objective(root, scens),
           "pareto": lambda: check_pareto(root, results, scens),
           "moran": lambda: check_moran(root, results),
           "kernel": lambda: check_kernel(),
           "gap": lambda: check_gap(results),
           "evals": lambda: check_evals(results),
           "stats": lambda: check_stats(results),
           "hypotheses": lambda: check_hypotheses(results)}
    out = []
    for name in CHECKS:
        if name in only:
            try:
                out.append(fns[name]())
            except Exception as exc:  # noqa: BLE001  a crashed check is a failed check
                out.append(_result(name, "error", str(exc)[:80], "n/a", False))
    return out


def _fmt(v):
    return f"{v:.10g}" if isinstance(v, float) else str(v)[:34]


def summary_table(results):
    lines = [f"{'check':12s} {'status':6s} {'ours':>24s} {'independent':>24s}  tol"]
    for r in results:
        lines.append(f"{r['name']:12s} {'PASS' if r['ok'] else 'FAIL':6s} {_fmt(r['value_ours']):>24s} "
                     f"{_fmt(r['value_check']):>24s}  {r['tol']}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=str(ROOT / "results_v2" / "quick"))
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--only", default=None, help="comma list of: " + ",".join(CHECKS))
    a = ap.parse_args(argv)
    res = run_all(a.root, a.results, a.only.split(",") if a.only else None)
    print(summary_table(res))
    for r in res:
        if not r["ok"]:
            detail = {k: v for k, v in r.items() if k not in ("table", "recomputed")}
            print(f"FAILED {r['name']}: {detail}")
    return 0 if all(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
