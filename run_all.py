"""Regenerate every table and figure. `--quick` is a smoke run (results/quick/); the paper uses the full run (results/)."""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"   # forced, before the numpy import; multithreaded BLAS is 90x slower on small solves

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from dataclasses import asdict  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import scipy  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "src"))

from steel import figures  # noqa: E402
from steel.data import load_inputs  # noqa: E402
from steel.experiments import (add_reference, benchmark, compare, friedman, holm, make_instances,  # noqa: E402
                               mcnemar, sensitivity, stage_a, tune, vss_evpi)
from steel.heuristics import Config  # noqa: E402
from steel.model import build, emission_range, pareto, solve, y_names  # noqa: E402
from steel.scenarios import choose_k, load_correlation, reduce, sample, to_scenarios  # noqa: E402
from steel.spatial import (band_weights, delivered_intensity, knn_weights, load_nodes, local_moran,  # noqa: E402
                           perm_test, project, purchase_shares, purchase_weighted)

ROOT = Path(__file__).parent
A12_MIN = 0.64
MAIN = ["B1", "B2", "B3", "Q", "Q-K", "Q-R", "Q-RBF", "Q-RND"]
ABLATE = [f"Q-R{i}" for i in range(1, 9)] + ["Q-NOLP"]
SENS_FACTORS = (0.8, 1.2)
# Absolute sensitivity values. opt.*.fix: six-tenths rule C_ref x (S/S_ref)^0.6 x CRF(9.08 %, life) on the UNDP
# reference units (main run scales linearly); mat.dri_bellary.ef: CEEW imported coal + pellets case 1.53.
SENS_VALUES = {"lim.p": [0.040], "opt.whr.fix": [411859.0], "opt.hot.fix": [2694336.0], "opt.pre.fix": [842094.0],
               "opt.gas.fix": [1334255.0], "mat.dri_bellary.ef": [1.53]}
TUNE_INST = dict(sizes=(1,), demand=(0.9,), cap_frac=(0.5,), seed=1)
TUNE_SEEDS = (100, 101, 102)
TUNE_SEED = 7
SENS_IDS = ["mat.scrap_dom.p", "mat.scrap_imp.p", "lim.p", "mat.scrap_dom.cap", "scrap.cap0", "freight.tariff",
            "mat.scrap_imp.cap", "mat.dri_bellary.cap", "con.scrap_imp.min", "con.dri_bellary.min", "ppa.minfrac",
            "opt.whr.fix", "opt.hot.fix", "opt.pre.fix", "opt.gas.fix", "mat.dri_bellary.ef"]


def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--runs", type=int, default=None, help="override runs per method and instance")
    ap.add_argument("--budget", type=int, default=None, help="override evaluation budget")
    ap.add_argument("--fresh", action="store_true", help="delete cached stages, tuning and raw benchmark rows; start over")
    ap.add_argument("--workers", type=int, default=None, help="processes (default: cpu_count-2 full, 1 quick)")
    ap.add_argument("--out", default=None, help="output folder, relative to the repo root; default results/ or results/quick/")
    a = ap.parse_args(argv)
    if a.workers is None:
        a.workers = 1 if a.quick else max(1, (os.cpu_count() or 1) - 2)
    return a


def out_dir(out, quick):
    """Output folder: `out` resolved against the repo root (absolute paths kept), else results/ or results/quick/."""
    if out:
        return ROOT / out
    return ROOT / "results" / ("quick" if quick else "")


def pareto_n(quick):
    return 5 if quick else 9


def moran_perm(quick):
    return 199 if quick else 9999


def replace_file(src, dst):
    """os.replace with a short retry: OneDrive or antivirus can hold a file for a moment (PermissionError)."""
    for attempt in range(5):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.2)


def write(res, name, rows):
    tmp = res / (name + ".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    replace_file(tmp, res / name)


def say(msg):
    print(msg, flush=True)


CACHE_FILES = ["stage_a.csv", "pareto.csv", "fig_pareto.png", "sensitivity.csv", "tuned.json", "bench_raw.csv"]


def _sha(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()


def manifest(quick, **cfg):
    """Everything the cached results depend on. JSON round trip so tuples compare equal to what is on disk."""
    data = ROOT / "data"
    corr = data / "correlation.csv"
    consts = {"SENS_IDS": SENS_IDS, "SENS_FACTORS": SENS_FACTORS, "SENS_VALUES": SENS_VALUES, "TUNE_INST": TUNE_INST,
              "TUNE_SEEDS": TUNE_SEEDS, "TUNE_SEED": TUNE_SEED, "pareto_n": pareto_n(quick), "MAIN": MAIN,
              "ABLATE": ABLATE, "moran_perm": moran_perm(quick)}
    meta = {**cfg, "quick": quick,
            "inputs_sha256": _sha([data / "inputs.csv", data / "structure.json", data / "nodes.csv"]),
            "correlation_sha256": _sha([corr]) if corr.exists() else "none",
            "constants_sha256": hashlib.sha256(json.dumps(consts, sort_keys=True).encode()).hexdigest(),
            "src_sha256": _sha(sorted((ROOT / "src" / "steel").glob("*.py"), key=lambda p: p.name)),
            "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}
    return json.loads(json.dumps(meta))


def _keep_seeds(path, runs):
    if not path.exists():
        return
    with open(path, newline="") as f:
        rd = csv.DictReader(f)
        fields, rows = rd.fieldnames, [r for r in rd if r.get("seed", "").isdigit() and int(r["seed"]) < runs]
    if not fields:
        return
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    replace_file(tmp, path)


def shrink_runs(res, runs):
    """Fewer runs than the cached ones: seeds are 0..runs-1 in stage A and the benchmark, so the first `runs` seeds
    of the cached work are exactly what a fresh run would produce. Tuning does not depend on runs. Stages after
    the benchmark are recomputed."""
    from steel.experiments import _repair_raw
    raw = res / "bench_raw.csv"
    if raw.exists():
        _repair_raw(raw)                      # drop a torn last line first
    for n in ("stage_a.csv", "bench_raw.csv"):
        _keep_seeds(res / n, runs)
    for n in ("pareto.csv", "fig_pareto.png", "sensitivity.csv"):
        (res / n).unlink(missing_ok=True)
    say(f"runs reduced to {runs}: kept seeds 0..{runs - 1} of cached stage A and benchmark rows")


def check_manifest(res, meta, fresh):
    f = res / "run_meta.json"
    if fresh:
        for n in CACHE_FILES:
            (res / n).unlink(missing_ok=True)
        f.unlink(missing_ok=True)
    elif f.exists():
        old = json.loads(f.read_text())
        diff = sorted(k for k in set(old) | set(meta) if old.get(k) != meta.get(k))
        if diff == ["runs"] and meta["runs"] < old["runs"]:
            shrink_runs(res, meta["runs"])
        elif diff:
            raise SystemExit(f"{f} differs from this run in: {', '.join(diff)}. Re-run with the same settings or use --fresh.")
    elif any((res / n).exists() for n in CACHE_FILES):
        raise SystemExit(f"{res} has cached results but no run_meta.json; use --fresh to start over.")
    tmp = res / "run_meta.json.tmp"
    tmp.write_text(json.dumps(meta, indent=1))
    replace_file(tmp, f)


def load_tuned(res):
    f = res / "tuned.json"
    if not f.exists():
        return {}
    return {m: Config(**{**c, "rules": frozenset(c["rules"])}) for m, c in json.loads(f.read_text()).items()}


def save_tuned(res, tuned, methods):
    tmp = res / "tuned.json.tmp"
    tmp.write_text(json.dumps({m: {**asdict(tuned[m]), "rules": sorted(tuned[m].rules)} for m in methods if m in tuned},
                              indent=1))
    replace_file(tmp, res / "tuned.json")


def _count_raw(raw):
    from steel.experiments import _repair_raw
    return len(_repair_raw(raw)) if raw.exists() else 0


def canonical_sort(raw, inst, inst1, runs):
    """Rewrite raw in the order an uninterrupted run writes it: main block, then ablation block."""
    order = {}
    for insts, ms in ((inst, MAIN), (inst1, ABLATE)):
        for i in insts:
            for m in ms:
                for s in range(runs):
                    order[(i["name"], m, str(s))] = len(order)
    with open(raw, newline="") as f:
        rd = csv.DictReader(f)
        fields, rows = rd.fieldnames, list(rd)
    kept = [r for r in rows if (r["instance"], r["method"], r["seed"]) in order]
    if len(kept) < len(rows):
        say(f"warning: dropped {len(rows) - len(kept)} bench_raw rows not in the current job list")
    rows = kept
    rows.sort(key=lambda r: order[(r["instance"], r["method"], r["seed"])])
    tmp = Path(str(raw) + ".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    replace_file(tmp, raw)
    return len(rows)


H1_MAX_GAP = 1e-4   # %


def stat_tests():
    """(hyp, family, a, b, metric). Primary: one Holm family. Secondary: evals_to_01pct on the same pairs that use
    evals_to_1pct, Holm-adjusted within their own family and not used by any hypothesis rule."""
    prim = [("H2", "Q-K", "B3", "evals_to_1pct"), ("H2", "Q-K", "B3", "feasible"),
            ("H3", "Q", "Q-K", "evals_to_1pct"), ("H4", "Q", "Q-RBF", "evals_to_1pct")]
    prim += [("H5", "Q", f"Q-R{i}", m) for i in range(1, 9) for m in ("viol", "evals_to_1pct")]
    prim += [("H7", "Q", "B3", "evals_to_1pct"), ("H7", "Q", "B3", "feasible"), ("H8", "Q", "Q-NOLP", "gap_pct")]
    sec = [(h, a, b, "evals_to_01pct") for h, a, b, m in prim if m == "evals_to_1pct"]
    return [(h, "primary", a, b, m) for h, a, b, m in prim] + [(h, "secondary", a, b, m) for h, a, b, m in sec]


def _yes(flag):
    return "yes" if flag else "no"


def hit_and_feasible(row, feas_row):
    """H2 and H7: a hit favouring a on `row` AND feasibility not significantly worse (fails only if b's feasible
    share is higher and McNemar p_holm < 0.05)."""
    hit_ok = row["p_holm"] < 0.05 and row["a12"] >= A12_MIN
    feas_ok = not (feas_row["median_b"] > feas_row["median_a"] and feas_row["p_holm"] < 0.05)
    return bool(hit_ok and feas_ok)


h2_supported = hit_and_feasible


def stats_and_hypotheses(rows, a_rows, m_rows):
    """stats_pairs rows and H1-H8 verdicts by the rules in README "Hypothesis rules"."""
    tests = stat_tests()
    out = [mcnemar(rows, a, b) if m == "feasible" else compare(rows, a, b, m) for _, _, a, b, m in tests]
    padj = [0.0] * len(tests)
    for fam in ("primary", "secondary"):
        idx = [i for i, t in enumerate(tests) if t[1] == fam]
        for i, q in zip(idx, holm([out[i]["p"] for i in idx])):
            padj[i] = q
    pairs = [{"hyp": h, "family": f, "a": a, "b": b, "metric": m, "n": o["n"], "median_a": o["median_a"],
              "median_b": o["median_b"], "p": o["p"], "p_holm": q, "a12": o["a12"]}
             for (h, f, a, b, m), o, q in zip(tests, out, padj)]
    prim = {(r["hyp"], r["b"], r["metric"]): r for r in pairs if r["family"] == "primary"}

    def hit(r):   # one-sided: a better than b
        return r["p_holm"] < 0.05 and r["a12"] >= A12_MIN

    scaled = [abs(float(r["gap_pct"])) for r in a_rows if r["encoding"] == "scaled" and r["gap_pct"] != ""]
    n_scaled = sum(1 for r in a_rows if r["encoding"] == "scaled")
    med = float(np.median(scaled)) if scaled else float("nan")
    hyp = [{"id": "H1", "detail": f"median |scaled gap| {med:.3e} % (n feasible={len(scaled)} of {n_scaled})",
            "supported": _yes(bool(scaled) and med < H1_MAX_GAP)}]
    def with_feasibility(h):
        g, f = prim[(h, "B3", "evals_to_1pct")], prim[(h, "B3", "feasible")]
        return {"id": h, "detail": f"evals_to_1pct n={g['n']} p_holm={g['p_holm']:.3g} A12={g['a12']:.3f}; feasible "
                                   f"share {f['median_a']:.3f} vs {f['median_b']:.3f} McNemar p_holm={f['p_holm']:.3g}",
                "supported": _yes(hit_and_feasible(g, f))}

    hyp.append(with_feasibility("H2"))
    r = prim[("H3", "Q-K", "evals_to_1pct")]
    hyp.append({"id": "H3", "detail": f"evals_to_1pct n={r['n']} p_holm={r['p_holm']:.3g} A12={r['a12']:.3f}",
                "supported": _yes(hit(r))})
    r = prim[("H4", "Q-RBF", "evals_to_1pct")]
    hyp.append({"id": "H4", "detail": f"evals_to_1pct n={r['n']} p_holm={r['p_holm']:.3g} A12={r['a12']:.3f} (two-sided)",
                "supported": _yes(r["p_holm"] < 0.05 and (r["a12"] >= A12_MIN or r["a12"] <= 1.0 - A12_MIN))})
    worse, rank = [], []
    for i in range(1, 9):
        rr = [prim[("H5", f"Q-R{i}", m)] for m in ("viol", "evals_to_1pct")]
        if any(hit(x) for x in rr):
            worse.append(f"R{i}")
        rank.append((max(x["a12"] if x["a12"] == x["a12"] else 0.0 for x in rr), f"R{i}"))
    ranking = ">".join(n for _, n in sorted(rank, key=lambda t: (-t[0], t[1])))
    hyp.append({"id": "H5", "detail": "rules whose removal hurts: " + (", ".join(worse) or "none")
                + f"; ranking by max A12: {ranking}", "supported": _yes(bool(worse))})
    sig = sum(1 for x in m_rows if float(x["p"]) < 0.05)
    hyp.append({"id": "H6", "detail": f"significant under {sig} of {len(m_rows)} weight choices",
                "supported": _yes(sig >= 3)})
    hyp.append(with_feasibility("H7"))
    r = prim[("H8", "Q-NOLP", "gap_pct")]
    hyp.append({"id": "H8", "detail": f"gap_pct n={r['n']} p_holm={r['p_holm']:.3g} A12={r['a12']:.3f}",
                "supported": _yes(hit(r))})
    return pairs, hyp


def cap_cases(inp, scens, cap_frac):
    """(case, eps) for the base case and each emission cap of the size-1 instance (same eps rule as make_instances)."""
    lo, hi = emission_range(inp, scens)
    return [("base" if f is None else f"cap{f}", None if f is None else lo + f * (hi - lo)) for f in cap_frac]


def write_rows(res, name, rows, fields):
    tmp = res / (name + ".tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    replace_file(tmp, res / name)


def main(quick, runs=None, budget=None, workers=1, res_dir=None, fresh=False):
    res = out_dir(res_dir, quick)
    res.mkdir(parents=True, exist_ok=True)
    d_runs, d_budget, n_cfg, n_samples = (3, 400, 2, 300) if quick else (30, 10000, 20, 5000)
    runs, budget = runs or d_runs, budget or d_budget
    sizes = (1,) if quick else (1, 2, 3, 5)
    demand = (1.0,) if quick else (0.8, 1.0, 1.2)
    cap_frac = (None, 0.5) if quick else (None, 0.6, 0.3)
    methods = MAIN + ABLATE
    check_manifest(res, manifest(quick, runs=runs, budget=budget, n_cfg=n_cfg, n_samples=n_samples, sizes=sizes,
                                 demand=demand, cap_frac=cap_frac), fresh)

    inp = load_inputs(ROOT / "data" / "inputs.csv", ROOT / "data" / "structure.json")
    corr_file = ROOT / "data" / "correlation.csv"
    corr = load_correlation(corr_file, inp.stochastic_ids()) if corr_file.exists() else None   # Spearman
    samples = sample(inp, n_samples, seed=0, corr=corr)
    k, hist = choose_k(lambda sc: solve(build(inp, sc)).cost, inp, samples, seed=0)
    write(res, "scenario_k.csv", [{"k": a, "cost": b, "chosen": a == k} for a, b in hist])
    scens = to_scenarios(inp, *reduce(samples, k, seed=0))

    if (res / "stage_a.csv").exists():
        a_rows = list(csv.DictReader(open(res / "stage_a.csv", newline="")))
        say("stage_a cached")
    else:
        a_rows = stage_a(inp, scens, runs, budget)
        write(res, "stage_a.csv", a_rows)
        say("stage_a done")

    tune_inst = make_instances(inp, scens, **TUNE_INST)[0]
    tuned = load_tuned(res)
    for m in methods:
        if m in tuned:
            say(f"tuned {m} cached")
            continue
        tuned[m] = tune(tune_inst["inp"], tune_inst["prob"], m, n_cfg, budget, seeds=TUNE_SEEDS, seed=TUNE_SEED, workers=workers)
        save_tuned(res, tuned, methods)
        say(f"tuned {m} ({len(tuned)}/{len(methods)})")
    save_tuned(res, tuned, methods)   # settle key order = methods order

    base_bin = len(y_names(inp))
    inst = make_instances(inp, scens, sizes=sizes, demand=demand, cap_frac=cap_frac)
    inst1 = [i for i in inst if i["n_bin"] == base_bin]
    raw = res / "bench_raw.csv"
    total = (len(inst) * len(MAIN) + len(inst1) * len(ABLATE)) * runs
    count = [_count_raw(raw)]

    def tick():
        count[0] += 1
        if count[0] % 100 == 0:
            say(f"bench {count[0]}/{total}")

    benchmark(inst, {m: tuned[m] for m in MAIN}, runs, budget, raw, base_n_bin=base_bin, workers=workers,
              resume=True, on_row=tick)
    benchmark(inst1, {m: tuned[m] for m in ABLATE}, runs, budget, raw, base_n_bin=base_bin, workers=workers,
              resume=True, on_row=tick)
    n = canonical_sort(raw, inst, inst1, runs)
    say(f"bench {n}/{total} done")
    add_reference(inst, raw, res / "bench.csv")
    rows = list(csv.DictReader(open(res / "bench.csv")))

    if (res / "pareto.csv").exists() and (res / "fig_pareto.png").exists():
        say("pareto cached")
    else:
        front = pareto(inp, scens, n=pareto_n(quick))
        figures.pareto_figure([(e, c) for e, c, _ in front], res / "fig_pareto.png")
        write(res, "pareto.csv", [{"eps": e, "cost": c} for e, c, _ in front])   # csv last: its presence means both done
        say("pareto done")

    if (res / "sensitivity.csv").exists():
        say("sensitivity cached")
    else:
        write(res, "sensitivity.csv", sensitivity(inp, scens, SENS_IDS, SENS_FACTORS, values=SENS_VALUES))
        say("sensitivity done")

    figures.gap_boxplot(rows, MAIN, res / "fig_gap.png")
    figures.scaling_figure(rows, res / "fig_scaling.png")

    write(res, "friedman.csv", [{"metric": m, **friedman(rows, MAIN, m)} for m in ("gap_pct", "evals_to_1pct")])

    cases = cap_cases(inp, scens, cap_frac)
    write(res, "vss.csv", [{"case": c, "eps": "" if e is None else e, **vss_evpi(inp, scens, eps=e)} for c, e in cases])

    nodes = load_nodes(ROOT / "data" / "nodes.csv")
    xy = project([n["lat"] for n in nodes], [n["lon"] for n in nodes])
    z = delivered_intensity(nodes)
    d = np.linalg.norm(xy[:, None] - xy[None], axis=-1)
    weights = {"knn4": knn_weights(xy, 4), "knn6": knn_weights(xy, 6), "knn8": knn_weights(xy, 8),
               "band_median": band_weights(xy, float(np.median(d[d > 0])))}
    m_rows = []
    for name, W in weights.items():
        i, p = perm_test(z, W, n_perm=moran_perm(quick), seed=0)
        m_rows.append({"weights": name, "n": len(z), "moran_i": i, "p": p})
    write(res, "moran.csv", m_rows)
    figures.moran_figure(z, weights["knn4"], res / "fig_moran.png")

    # second variable: delivered intensity x optimal purchase share (base case and each emission cap, size 1)
    variables, mp_rows = [("intensity", "all", z, m_rows)], []
    for case, eps in cases:
        prob = build(inp, scens, eps=eps)
        zc = purchase_weighted(nodes, purchase_shares(inp, prob, solve(prob).z))
        rows_c = []
        for name, W in weights.items():
            i, p = perm_test(zc, W, n_perm=moran_perm(quick), seed=0)
            rows_c.append({"case": case, "weights": name, "n": len(zc), "n_nonzero": int((zc != 0).sum()),
                           "moran_i": i, "p": p})
        mp_rows += rows_c
        variables.append(("purchase_weighted", case, zc, rows_c))
    write(res, "moran_purchase.csv", mp_rows)

    # local Moran clusters, knn6, only where the global test is significant under knn6
    lisa, any_sig = [], False
    for var, case, zz, rr in variables:
        if not any(x["weights"] == "knn6" and x["p"] < 0.05 for x in rr):
            continue
        any_sig = True
        li, lp, quad = local_moran(zz, weights["knn6"], n_perm=moran_perm(quick), seed=0)
        lisa += [{"variable": var, "case": case, "node": nd["id"], "name": nd["name"], "z": zz[j], "local_i": li[j],
                  "p": lp[j], "cluster": quad[j]} for j, nd in enumerate(nodes) if lp[j] < 0.05]
    if any_sig:
        write_rows(res, "lisa.csv", lisa, ["variable", "case", "node", "name", "z", "local_i", "p", "cluster"])
    else:
        (res / "lisa.csv").unlink(missing_ok=True)
        say("lisa skipped: no global Moran test significant under knn6")

    pairs, hyp = stats_and_hypotheses(rows, a_rows, m_rows)
    write(res, "stats_pairs.csv", pairs)
    write(res, "hypotheses.csv", hyp)
    print("\n".join(f"{h['id']}: {h['supported']} ({h['detail']})" for h in hyp))


if __name__ == "__main__":
    a = parse_args(sys.argv[1:])
    main(a.quick, a.runs, a.budget, a.workers, res_dir=a.out, fresh=a.fresh)
