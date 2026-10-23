"""Instances, equal-budget tuning, benchmark runs, reference scoring and statistics.

The exact optimum is computed in add_reference(), after every heuristic run is on disk.
"""
import csv
import io
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.optimize import minimize

from steel.data import Dist, Inputs
from steel.heuristics import METHODS, run
from steel.model import build, emission_range, solve, y_names

FIELDS = ["instance", "n_bin", "method", "seed", "cost", "viol", "feasible", "evals", "seconds", "evals_to_best",
          "trace", "budget", "synthetic"]
TARGETS = {"evals_to_1pct": 1.0, "evals_to_01pct": 0.1}   # gap thresholds in %, scored after all runs


def scale_inputs(inp, f, seed):
    """Synthetic larger instance. Clones are labelled synthetic in the paper."""
    if f == 1:
        return inp
    rng = np.random.default_rng(seed)
    v, dist = dict(inp.v), dict(inp.dist)
    st = {"materials": [], "solar_tiers": [], "ppa_tiers": []}

    def copy(src, dst, mult=None):
        mult = mult or {}
        for key in [k for k in inp.v if k.startswith(src + ".")]:
            new = dst + key[len(src):]
            v[new] = inp.v[key] * mult.get(key.rsplit(".", 1)[1], 1.0)
            d = inp.dist[key]
            dist[new] = d if key.endswith(".price") else Dist("fixed", 0.0, 0.0)

    for m in inp.struct["materials"]:
        base = m["name"]
        con_src = base if m["contract"] else inp.contract_mats()[0]
        for j in range(f):
            name = f"{base}_{j}"
            copy(f"mat.{base}", f"mat.{name}", {"cap": 1.0 / f, "price": 1.0 + 0.05 * rng.uniform(-1, 1)})
            copy(f"con.{con_src}", f"con.{name}", {"min": 0.25 / f * v[f"mat.{base}.cap"] / v[f"con.{con_src}.min"],
                                                 "fee": 1.0 / f})
            dist[f"mat.{name}.price"] = inp.dist[f"mat.{base}.price"]
            if inp.dist[f"mat.{base}.price"].kind == "triangular":   # keep mode inside its range
                v[f"mat.{name}.price"] = inp.v[f"mat.{base}.price"]
            st["materials"].append({"name": name, "kind": m["kind"], "contract": True})
    for fam, key in (("sol", "solar_tiers"), ("ppa", "ppa_tiers")):
        for t in inp.struct[key]:
            for j in range(f):
                copy(f"{fam}.{t}", f"{fam}.{t}_{j}", {"kwh": 1.0 + 0.15 * j, "fix": 1.0 + 0.15 * j})
                st[key].append(f"{t}_{j}")
    return Inputs(v, dist, st)


def make_instances(inp, scens, sizes=(1, 2, 3, 5), demand=(0.8, 1.0, 1.2), cap_frac=(None, 0.6, 0.3), seed=0):
    out = []
    for f in sizes:
        big = scale_inputs(inp, f, seed)
        sc = []
        for p, over in scens:          # clones follow their parent's price scenario
            o = dict(over)
            for m in big.mats() if f > 1 else []:
                key = f"mat.{m.rsplit('_', 1)[0]}.price"
                if key in over:
                    o[f"mat.{m}.price"] = over[key] * big.v[f"mat.{m}.price"] / inp.v[key]
            sc.append((p, o))
        for dm in demand:
            cur = big.with_values({"plant.demand": inp.v["plant.demand"] * dm})
            for frac in cap_frac:
                name = f"n{len(y_names(cur))}_d{dm}_c{frac}"
                eps = None
                if not solve(build(cur, sc), relax=True).ok:
                    print(f"skipped {name}: demand cannot be met")
                    continue
                if frac is not None:
                    lo, hi = emission_range(cur, sc)
                    eps = lo + frac * (hi - lo)
                prob = build(cur, sc, eps=eps)
                if not solve(prob, relax=True).ok:
                    print(f"skipped {name}: emission cap infeasible")
                    continue
                out.append({"name": name, "inp": cur, "prob": prob, "n_bin": prob.ny})
    return out


def _evals_to_best(history):
    costs = np.array([c for _, c in history])
    if np.isnan(costs).all():
        return ""
    return int(history[int(np.nanargmin(costs))][0])


def _trace(history):
    """Compact record of every improvement of the best FEASIBLE cost: "e1:c1;e2:c2;..." (eval index : cost)."""
    out, last = [], None
    for e, c in history:
        if c == c and (last is None or c < last):     # c == c drops nan (no feasible point yet)
            out.append(f"{int(e)}:{float(c)!r}")
            last = c
    return ";".join(out)


def evals_to_target(trace, ref, pct, budget):
    """First eval whose best feasible cost is within pct % of ref; budget + 1 if never reached."""
    for step in filter(None, trace.split(";")):
        e, c = step.split(":")
        if (float(c) - ref) / abs(ref) * 100.0 <= pct:
            return int(e)
    return int(budget) + 1


def _run_one(args):
    inp, prob, cfg, budget, seed = args
    return run(inp, prob, cfg, budget, seed)


def _map_runs(tasks, workers):
    """Results in task order, whatever the number of workers."""
    if workers <= 1:
        for t in tasks:
            yield _run_one(t)
        return
    with ProcessPoolExecutor(max_workers=workers) as ex:
        yield from ex.map(_run_one, tasks, chunksize=1)


def _repair_raw(path):
    """Drop a torn last line (hard kill) and return the (instance, method, seed) keys already on disk."""
    data = Path(path).read_bytes()
    if data and not data.endswith(b"\n"):
        data = data[:data.rfind(b"\n") + 1]     # no newline at all -> empty file, header rewritten by the caller
        Path(path).write_bytes(data)
    done = set()
    for r in csv.DictReader(io.StringIO(data.decode(), newline="")):
        if r.get("synthetic") in (None, "") or None in r:
            continue
        done.add((r["instance"], r["method"], str(r["seed"])))
    return done


def benchmark(instances, configs, runs, budget, out_csv, append=False, base_n_bin=None, workers=1,
              resume=False, on_row=None):
    """synthetic=True when an instance has more binaries than the base (size-1) instance.
    resume=True: keep rows already in out_csv (a torn last line is dropped), run and append only the missing
    (instance, method, seed) jobs, one flushed row at a time. on_row() is called after each new row."""
    if base_n_bin is None:
        base_n_bin = min(i["n_bin"] for i in instances)
    done = set()
    if resume and Path(out_csv).exists() and Path(out_csv).stat().st_size > 0:
        done = _repair_raw(out_csv)
        append = Path(out_csv).stat().st_size > 0
    elif resume:
        append = False
    with open(out_csv, "a" if append else "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if not append:
            w.writeheader()
        jobs = [(inst, name, seed) for inst in instances for name in configs for seed in range(runs)
                if (inst["name"], name, str(seed)) not in done]
        tasks = [(inst["inp"], inst["prob"], configs[name], budget, seed) for inst, name, seed in jobs]
        for (inst, name, seed), r in zip(jobs, _map_runs(tasks, workers)):
            w.writerow({"instance": inst["name"], "n_bin": inst["n_bin"], "method": name, "seed": seed,
                        "cost": r["cost"], "viol": r["viol"], "feasible": r["feasible"],
                        "evals": r["evals"], "seconds": r["seconds"],
                        "evals_to_best": _evals_to_best(r["history"]),
                        "trace": _trace(r["history"]), "budget": budget,
                        "synthetic": inst["n_bin"] > base_n_bin})
            fh.flush()
            if on_row:
                on_row()


def add_reference(instances, in_csv, out_csv):
    ref = {}
    for inst in instances:
        t0 = time.perf_counter()
        ref[inst["name"]] = (solve(inst["prob"]).cost, time.perf_counter() - t0)
    with open(in_csv, newline="") as fi, open(out_csv, "w", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=FIELDS + ["ref_cost", "ref_seconds", "gap_pct"] + list(TARGETS))
        w.writeheader()
        for row in csv.DictReader(fi):
            cost, secs = ref[row["instance"]]
            gap = ""
            if row["feasible"] == "True":
                gap = (float(row["cost"]) - cost) / abs(cost) * 100.0
            hits = {k: evals_to_target(row["trace"], cost, pct, row["budget"]) for k, pct in TARGETS.items()}
            w.writerow({**row, "ref_cost": cost, "ref_seconds": secs, "gap_pct": gap, **hits})


def tune(inp, prob, method, n_cfg, budget, seeds, seed, workers=1):
    """Random search; every method gets the same n_cfg, budget and seeds."""
    rng = np.random.default_rng(seed)
    base = METHODS[method]
    cscale = float(np.abs(prob.c) @ prob.zub + abs(prob.const))
    cfgs = [base if i == 0 else replace(base, pop=int(rng.choice([20, 40, 80])),
                                        pm=float(rng.choice([0.05, 0.1, 0.2])),
                                        sigma=float(rng.choice([0.02, 0.05, 0.1, 0.2])),
                                        ls_steps=int(rng.choice([2, 5, 10])),
                                        keep=float(rng.choice([0.25, 0.5, 0.75]))) for i in range(n_cfg)]
    results = iter(list(_map_runs([(inp, prob, c, budget, s) for c in cfgs for s in seeds], workers)))
    best, best_score = base, None
    for cfg in cfgs:
        rs = [next(results) for _ in seeds]
        ok = [r["cost"] / cscale for r in rs if r["feasible"] and np.isfinite(r["cost"])]
        # Deb-style rank: higher feasible share, then lower median feasible cost, then lower median violation
        score = (-len(ok) / len(rs), float(np.median(ok)) if ok else np.inf, float(np.median([r["viol"] for r in rs])))
        if best_score is None or score < best_score:
            best, best_score = cfg, score
    return best


def a12(x, y):
    """Probability that a value from x is smaller (better) than one from y; 0.5 = no difference."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(((x[:, None] < y[None, :]).sum() + 0.5 * (x[:, None] == y[None, :]).sum()) / (x.size * y.size))


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj, running = np.empty_like(p), 0.0
    for rank, i in enumerate(order):
        running = max(running, (p.size - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


COST_METRICS = ("cost", "gap_pct", "evals_to_best")


def _value(row, metric):
    """Float value of a metric, or None if the row does not count.
    Cost-type metrics (cost, gap_pct, evals_to_best) count only for feasible rows with a value; viol counts always."""
    if metric in COST_METRICS and row["feasible"] != "True":
        return None
    if row[metric] == "":
        return None
    return float(row[metric])


def mcnemar(rows, a, b):
    """Paired (instance, seed) feasible flags. Exact McNemar: two-sided binomial test on the discordant pairs.
    median_a / median_b hold the feasible shares; a12 is A12 on the infeasible flag (lower is better)."""
    def table(m):
        return {(r["instance"], r["seed"]): r["feasible"] == "True" for r in rows if r["method"] == m}

    ta, tb = table(a), table(b)
    keys = [k for k in ta if k in tb]
    fa, fb = np.array([ta[k] for k in keys], bool), np.array([tb[k] for k in keys], bool)
    n01, n10 = int((fa & ~fb).sum()), int((~fa & fb).sum())
    p = 1.0 if n01 + n10 == 0 else float(stats.binomtest(n01, n01 + n10, 0.5).pvalue)
    n = len(keys)
    return {"n": n, "median_a": float(fa.mean()) if n else np.nan, "median_b": float(fb.mean()) if n else np.nan,
            "p": p, "a12": a12((~fa).astype(float), (~fb).astype(float)) if n else np.nan}


def compare(rows, a, b, metric):
    """Paired by (instance, seed), Wilcoxon signed-rank. For cost, gap_pct and evals_to_best only feasible runs
    with a value count; a pair is dropped if either side is missing. For viol all runs count."""
    def table(m):
        return {(r["instance"], r["seed"]): _value(r, metric) for r in rows if r["method"] == m}

    ta, tb = table(a), table(b)
    keys = [k for k in ta if k in tb and ta[k] is not None and tb[k] is not None]
    xa, xb = np.array([ta[k] for k in keys]), np.array([tb[k] for k in keys])
    p = 1.0 if len(keys) == 0 or np.allclose(xa, xb) else float(stats.wilcoxon(xa, xb).pvalue)
    return {"n": len(keys), "median_a": float(np.median(xa)) if len(keys) else np.nan,
            "median_b": float(np.median(xb)) if len(keys) else np.nan, "p": p,
            "a12": a12(xa, xb) if len(keys) else np.nan}


def friedman(rows, methods, metric):
    """Friedman test across methods; blocks are instances (median of the metric over seeds, same row rule as compare).
    Methods with no value at all (e.g. never feasible, for gap_pct) are dropped and the methods used are reported;
    blocks are the instances where every remaining method has a value. evals_to_* count every run."""
    per = {}
    for r in rows:
        if r["method"] in methods:
            v = _value(r, metric)
            if v is not None:
                per.setdefault((r["instance"], r["method"]), []).append(v)
    methods = [m for m in methods if any(k[1] == m for k in per)]
    insts = sorted({i for i, _ in per})
    blocks = [i for i in insts if all((i, m) in per for m in methods)]
    used = ";".join(methods)
    if len(blocks) < 2 or len(methods) < 3:
        return {"n_blocks": len(blocks), "methods": used, "stat": float("nan"), "p": float("nan")}
    cols = [[float(np.median(per[(i, m)])) for i in blocks] for m in methods]
    res = stats.friedmanchisquare(*cols)
    return {"n_blocks": len(blocks), "methods": used, "stat": float(res.statistic), "p": float(res.pvalue)}


STAGE_A_POP = 40   # same population size as the Stage C heuristics (Config.pop)


class _BudgetSpent(Exception):
    pass


def _memetic_lp(g, G, h, ulo, uhi, budget, seed, pop=STAGE_A_POP, pm=0.1, sigma=0.1, ls_iter=20, tol=1e-6):
    """Real-coded memetic algorithm for min g @ u s.t. G u >= h, ulo <= u <= uhi.

    Steady state: two Deb-tournament parents, blend crossover, Gaussian mutation, SLSQP local search on the
    offspring, offspring replaces the worst member if better under Deb's rules (feasible beats infeasible;
    among feasible lower objective; among infeasible lower violation). Violation is measured in the units of
    the form being solved, so the raw and scaled forms differ only in variable/objective/row scaling.
    Every objective and gradient evaluation counts against the budget, including those inside SLSQP."""
    rng = np.random.default_rng(seed)
    n, span = g.size, uhi - ulo
    count, last = [0], [None]

    def tick(u):
        if count[0] >= budget:
            raise _BudgetSpent
        count[0] += 1
        last[0] = np.array(u, float)

    def fun(u):
        tick(u)
        return float(g @ u)

    def jac(u):
        tick(u)
        return g

    def score(u):
        u = np.clip(u, ulo, uhi)
        tick(u)
        return (float(g @ u), float(np.maximum(0.0, h - G @ u).sum()), u)

    def key(ind):
        return (0, ind[0]) if ind[1] <= tol else (1, ind[1])

    cons = [{"type": "ineq", "fun": lambda u: G @ u - h, "jac": lambda u: G}]
    bounds = list(zip(ulo, uhi))

    def local(u):
        last[0] = None
        try:
            res = minimize(fun, u, jac=jac, method="SLSQP", bounds=bounds, constraints=cons,
                           options={"maxiter": ls_iter, "ftol": 1e-12})
            return res.x
        except _BudgetSpent:
            return last[0] if last[0] is not None else u

    P = []
    try:
        for _ in range(min(pop, budget)):
            P.append(score(ulo + rng.random(n) * span))
        while count[0] < budget:
            i, j, k, m = rng.integers(len(P), size=4)
            a = P[i] if key(P[i]) < key(P[j]) else P[j]
            b = P[k] if key(P[k]) < key(P[m]) else P[m]
            w = rng.uniform(-0.25, 1.25, n)                       # blend crossover (BLX-0.25 per gene)
            child = w * a[2] + (1.0 - w) * b[2]
            child = child + (rng.random(n) < pm) * rng.normal(0.0, sigma, n) * span
            child = local(np.clip(child, ulo, uhi))
            kid = score(child)
            worst = max(range(len(P)), key=lambda q: key(P[q]))
            if key(kid) < key(P[worst]):
                P[worst] = kid
    except _BudgetSpent:
        pass
    best = min(P, key=key)
    return best[2], count[0]


def stage_a(inp, scens, runs, budget):
    """Base LP (no investments) solved by one memetic algorithm in raw units and in scaled units.

    Scaled form: u = x / hi (variable bounds), objective / (|c| @ hi), constraint rows / row scale; no
    information from the exact optimum. The exact LP optimum is computed after all runs, for scoring only."""
    prob = build(inp, scens)
    ny = prob.ny
    lo, hi = prob.zlb[ny:], prob.zub[ny:]
    A, c = prob.A[:, ny:], prob.c[ny:]
    runs_out = []
    for enc in ("raw", "scaled"):
        s = np.where(hi > 0, hi, 1.0) if enc == "scaled" else np.ones_like(hi)
        f = float(np.abs(c) @ hi) if enc == "scaled" else 1.0
        rs = prob.scale if enc == "scaled" else np.ones(A.shape[0])
        As, lb, ub = A * s / rs[:, None], prob.lb / rs, prob.ub / rs
        fl, fu = np.isfinite(lb), np.isfinite(ub)
        G, h = np.vstack([As[fl], -As[fu]]), np.concatenate([lb[fl], -ub[fu]])
        for seed in range(runs):
            u, evals = _memetic_lp(c * s / f, G, h, lo / s, hi / s, budget, seed)
            runs_out.append((enc, seed, u * s, evals))
    ref = solve(prob, fixed_y=np.zeros(ny)).cost      # referee, after every run
    rows = []
    for enc, seed, x, evals in runs_out:
        r = A @ x
        viol = float((np.maximum(0, prob.lb - r) / prob.scale).sum() + (np.maximum(0, r - prob.ub) / prob.scale).sum())
        cost = float(c @ x + prob.const)
        ok = viol <= 1e-6
        rows.append({"encoding": enc, "seed": seed, "cost": cost, "feasible": ok,
                     "gap_pct": (cost - ref) / abs(ref) * 100.0 if ok else "", "evals": evals, "pop": STAGE_A_POP})
    return rows


def vss_evpi(inp, scens, eps=None):
    """Value of the stochastic solution and expected value of perfect information (Birge and Louveaux).
    RP: stochastic optimum. EV: one scenario at the probability-weighted mean prices; its first stage y is fixed
    and the second stage re-solved over all scenarios: EEV. WS: sum_s p_s * (scenario s solved alone).
    VSS = EEV - RP, EVPI = RP - WS. An infeasible EEV (mean-value y cannot serve some scenario) is inf.
    With an emission cap eps (a bound on expected emissions, coupling the scenarios) WS and EVPI are left empty:
    solving each scenario alone under the same bound is not a relaxation of RP, so RP - WS has no meaning."""
    rp = solve(build(inp, scens, eps=eps)).cost
    keys = sorted({k for _, o in scens for k in o})
    mean = {k: sum(p * o.get(k, inp.v[k]) for p, o in scens) for k in keys}
    ev = solve(build(inp, [(1.0, mean)], eps=eps))
    eev = solve(build(inp, scens, eps=eps), fixed_y=np.round(ev.z[: len(y_names(inp))])).cost if ev.ok else np.inf
    out = {"rp": rp, "eev": eev, "ws": "", "vss": eev - rp, "evpi": "", "vss_pct": (eev - rp) / abs(rp) * 100.0,
           "evpi_pct": ""}
    if eps is None:   # under a cap on EXPECTED emissions scenario-alone solves are no relaxation: WS undefined
        ws = sum(p * solve(build(inp, [(1.0, o)])).cost for p, o in scens)
        out.update(ws=ws, evpi=rp - ws, evpi_pct=(rp - ws) / abs(rp) * 100.0)
    return out


def sensitivity(inp, scens, ids, factors, values=None):
    """One-at-a-time sensitivity of the exact MILP. Each id is set to factor x base, or to an absolute value from
    `values` {id: [v, ...]}. Infeasible settings are kept with ok=False and empty numbers."""
    out = []
    for k in ids:
        for f in factors:
            out.append((k, f, "", f * inp.v[k]))
        for x in (values or {}).get(k, []):
            out.append((k, "", x, x))
    ysets = y_names(inp)
    rows = []
    for k, fac, absval, x in out:
        sc = [(p, {a: b for a, b in over.items() if a != k}) for p, over in scens]   # the tested value must win
        cur = inp.with_values({k: x})
        prob = build(cur, sc)
        sol = solve(prob)
        row = {"id": k, "factor": fac, "abs_value": absval, "ok": bool(sol.ok), "cost": "", "emissions": "",
               "chosen_options": "", "dri_share": "", "value": x}
        if sol.ok:
            z, probs = sol.z, prob.probs
            chosen = [n for n in ysets if z[prob.iy(n)] > 0.5]
            flow = lambda m, s: z[prob.ix(s, f"q.{m}")] + (z[prob.ix(s, f"qc.{m}")] if m in cur.contract_mats() else 0.0)
            tot = sum(probs[s] * flow(m, s) for s in range(prob.K) for m in cur.mats())
            dri = sum(probs[s] * flow(m, s) for s in range(prob.K) for m in cur.dri())
            row.update(cost=sol.cost, emissions=sol.emis, chosen_options=";".join(chosen), dri_share=dri / tot)
        rows.append(row)
    return rows
