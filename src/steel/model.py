"""Two-stage stochastic model. y: first-stage binaries. x_s: flows per price scenario.

Rules (names shared with repair.py):
R1 yield balance, R2 copper limit, R3 phosphorus limit, R4 power balance,
R5 renewable limits, R6 reheating balance, R7 capacities and exclusivity, R8 option linking.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

INF = np.inf


def y_names(inp):
    s = inp.struct
    return ([f"sol.{t}" for t in s["solar_tiers"]] + [f"ppa.{u}" for u in s["ppa_tiers"]]
            + ["whr", "pre", "hot", "gas", "shred"] + [f"con.{m}" for m in inp.contract_mats()])


def x_names(inp):
    return ([f"q.{m}" for m in inp.mats()] + [f"qc.{m}" for m in inp.contract_mats()]
            + ["g", "sol", "ppa", "sv", "fo", "ng"])


def derived(inp):
    v = inp.v
    demand = v["plant.demand"]
    scrap_max = v["scrap.cap0"] + v["opt.shred.extra"]
    charge_max = sum(v[f"mat.{m}.cap"] for m in inp.mats())
    return {
        "D": demand,
        "L": demand / v["plant.roll_yield"],
        "Eaux": v["plant.kwh_aux"] * demand,
        "H": v["plant.reheat"] * demand,
        "scrap_max": scrap_max,
        "e_max": max(v[f"mat.{m}.kwh"] for m in inp.mats()) * charge_max + v["plant.kwh_aux"] * demand,
        "sv_max": v["opt.pre.save"] * scrap_max,
    }


@dataclass
class Problem:
    c: np.ndarray
    const: float
    e: np.ndarray
    econst: float
    A: np.ndarray
    lb: np.ndarray
    ub: np.ndarray
    zlb: np.ndarray
    zub: np.ndarray
    integrality: np.ndarray
    scale: np.ndarray
    y_names: list
    x_names: list
    K: int
    probs: np.ndarray

    @property
    def ny(self):
        return len(self.y_names)

    @property
    def nx(self):
        return len(self.x_names)

    def iy(self, name):
        return self.y_names.index(name)

    def ix(self, s, name):
        return self.ny + s * self.nx + self.x_names.index(name)


def build(inp, scens, eps=None):
    yn, xn = y_names(inp), x_names(inp)
    ny, nx, K = len(yn), len(xn), len(scens)
    n = ny + K * nx
    v, d = inp.v, derived(inp)
    st = inp.struct
    mats, cm, scrap = inp.mats(), inp.contract_mats(), inp.scrap()
    iy = {a: i for i, a in enumerate(yn)}
    c, e, zub = np.zeros(n), np.zeros(n), np.ones(n)
    const = econst = 0.0
    rows, lo, hi = [], [], []

    def ix(s, a):
        return ny + s * nx + xn.index(a)

    def add(coefs, lb, ub):
        r = np.zeros(n)
        for j, a in coefs.items():
            r[j] += a
        rows.append(r), lo.append(lb), hi.append(ub)

    for t in st["solar_tiers"]:
        c[iy[f"sol.{t}"]] = v[f"sol.{t}.fix"]
    for u in st["ppa_tiers"]:
        c[iy[f"ppa.{u}"]] = v[f"ppa.{u}.fix"]
    for o in ("whr", "pre", "hot", "gas", "shred"):
        c[iy[o]] = v[f"opt.{o}.fix"]
    for m in cm:
        c[iy[f"con.{m}"]] = v[f"con.{m}.fee"]
    add({iy[f"sol.{t}"]: 1.0 for t in st["solar_tiers"]}, -INF, 1.0)   # R7 one solar tier
    add({iy[f"ppa.{u}"]: 1.0 for u in st["ppa_tiers"]}, -INF, 1.0)     # R7 one contract tier

    for s, (p, over) in enumerate(scens):
        w = inp.with_values(over).v
        tot = {m: {ix(s, f"q.{m}"): 1.0} for m in mats}
        for m in cm:
            tot[m][ix(s, f"qc.{m}")] = 1.0

        def lin(fn):
            return {j: fn(m) * a for m in mats for j, a in tot[m].items()}

        for m in mats:
            j = ix(s, f"q.{m}")
            fr_c, fr_e = w["freight.tariff"] * w[f"mat.{m}.dist"], w["freight.ef"] * w[f"mat.{m}.dist"]
            c[j] = p * (w[f"mat.{m}.price"] + fr_c)
            e[j], zub[j] = p * (w[f"mat.{m}.ef"] + fr_e), w[f"mat.{m}.cap"]
            add(tot[m], -INF, w[f"mat.{m}.cap"])                                   # R7 supplier cap
        for m in cm:
            j, k = ix(s, f"qc.{m}"), iy[f"con.{m}"]
            fr_c, fr_e = w["freight.tariff"] * w[f"mat.{m}.dist"], w["freight.ef"] * w[f"mat.{m}.dist"]
            c[j] = p * ((1.0 - w[f"con.{m}.disc"]) * w[f"mat.{m}.price"] + fr_c)   # discount: price only
            e[j], zub[j] = p * (w[f"mat.{m}.ef"] + fr_e), w[f"mat.{m}.cap"]
            add({j: 1.0, k: -w[f"mat.{m}.cap"]}, -INF, 0.0)                        # R8 contract on/off
            add({j: 1.0, k: -w[f"con.{m}.min"]}, 0.0, INF)                         # R8 minimum offtake
        add(lin(lambda m: w[f"mat.{m}.yield"]), d["L"], INF)                       # R1
        add(lin(lambda m: w[f"mat.{m}.cu"] - w["lim.cu"]), -INF, 0.0)              # R2
        add(lin(lambda m: w[f"mat.{m}.p"] - w["lim.p"]), -INF, 0.0)                # R3
        sc = {j: a for m in scrap for j, a in tot[m].items()}
        add({**sc, iy["shred"]: -w["opt.shred.extra"]}, -INF, w["scrap.cap0"])     # R7 scrap ceiling
        jg, jsol, jppa, jsv, jfo, jng = (ix(s, a) for a in ("g", "sol", "ppa", "sv", "fo", "ng"))
        add({jsv: 1.0, **{j: -w["opt.pre.save"] * a for j, a in sc.items()}}, -INF, 0.0)   # R8 saving size
        add({jsv: 1.0, iy["pre"]: -d["sv_max"]}, -INF, 0.0)                        # R8 saving on/off
        bal = {jg: 1.0, jsol: 1.0, jppa: 1.0, jsv: 1.0}
        for j, a in lin(lambda m: w[f"mat.{m}.kwh"]).items():
            bal[j] = bal.get(j, 0.0) - a
        bal[iy["hot"]] = -w["opt.hot.kwh"] * d["D"]                                # extra rolling power
        add(bal, d["Eaux"], INF)                                                   # R4
        add({jsol: 1.0, **{iy[f"sol.{t}"]: -w[f"sol.{t}.kwh"] for t in st["solar_tiers"]}}, -INF, 0.0)  # R5
        add({jppa: 1.0, **{iy[f"ppa.{u}"]: -w[f"ppa.{u}.kwh"] for u in st["ppa_tiers"]}}, -INF, 0.0)    # R5
        add({jppa: 1.0, **{iy[f"ppa.{u}"]: -w["ppa.minfrac"] * w[f"ppa.{u}.kwh"]
                           for u in st["ppa_tiers"]}}, 0.0, INF)                   # R5 take-or-pay
        add({jfo: 1.0, jng: 1.0, iy["hot"]: w["opt.hot.save"] * d["D"],
             iy["whr"]: w["opt.whr.save"] * d["D"]}, d["H"], INF)                  # R6
        add({jng: 1.0, iy["gas"]: -d["H"]}, -INF, 0.0)                             # R8 gas on/off
        c[jg], e[jg], zub[jg] = p * w["grid.price"], p * w["grid.ef"], d["e_max"]
        c[jsol], zub[jsol] = p * w["sol.var"], max(w[f"sol.{t}.kwh"] for t in st["solar_tiers"])
        c[jppa], zub[jppa] = p * w["ppa.price"], max(w[f"ppa.{u}.kwh"] for u in st["ppa_tiers"])
        c[jsv], e[jsv] = p * w["fo.price"] * w["opt.pre.fuel"], p * w["fo.ef"] * w["opt.pre.fuel"]
        zub[jsv] = d["sv_max"]
        c[jfo], e[jfo], zub[jfo] = p * w["fo.price"], p * w["fo.ef"], d["H"]
        c[jng], e[jng], zub[jng] = p * w["ng.price"], p * w["ng.ef"], d["H"]
        const += p * d["D"] * sum(val for k, val in w.items() if k.startswith("const."))
        econst += p * d["D"] * sum(val for k, val in w.items() if k.startswith("constef."))

    if eps is not None:
        add({j: e[j] for j in np.nonzero(e)[0]}, -INF, eps - econst)
    A = np.array(rows)
    integ = np.zeros(n)
    integ[:ny] = 1
    return Problem(c, const, e, econst, A, np.array(lo), np.array(hi), np.zeros(n), zub, integ,
                   np.maximum(1.0, np.abs(A) @ zub), yn, xn, K, np.array([p for p, _ in scens]))


@dataclass
class Solution:
    ok: bool
    cost: float
    emis: float
    z: np.ndarray | None


def solve(prob, objective="cost", fixed_y=None, relax=False, mip_rel_gap=1e-6):
    lb, ub = prob.zlb.copy(), prob.zub.copy()
    integ = prob.integrality
    if fixed_y is not None:
        lb[: prob.ny] = ub[: prob.ny] = np.asarray(fixed_y, float)
    if relax or fixed_y is not None:
        integ = np.zeros_like(integ)
    res = milp(prob.c if objective == "cost" else prob.e,
               constraints=LinearConstraint(prob.A, prob.lb, prob.ub),
               integrality=integ, bounds=Bounds(lb, ub), options={"mip_rel_gap": mip_rel_gap})
    if res.status != 0 or res.x is None:
        return Solution(False, INF, INF, None)
    z = res.x
    return Solution(True, float(prob.c @ z + prob.const), float(prob.e @ z + prob.econst), z)


def emission_range(inp, scens):
    prob = build(inp, scens)
    return solve(prob, objective="emis").emis, solve(prob).emis


def pareto(inp, scens, n=9):
    lo, hi = emission_range(inp, scens)
    out = []
    for eps in np.linspace(hi, lo, n):
        s = solve(build(inp, scens, eps=eps * (1 + 1e-9)))
        if s.ok:
            out.append((float(eps), s.cost, s.z))
    return out
