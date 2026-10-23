"""Topological Projection Operator (TPO): a domain repair operator. Each block enforces one named engineering rule with a minimal change.

Order as applied in the code: R7-tier, R8, R7-clip, R1, R2, R3, R8-sv, R5, R4, R6.
R7-tier keeps at most one solar and one PPA tier; then, per scenario: R8 sets contract tonnage within
[minimum offtake, cap] or 0; R7-clip clips spot tonnage to supplier caps and the scrap ceiling; R1 yield;
R2, R3 chemistry (copper, phosphorus); R8-sv sizes the preheating saving; R5 renewable limits; R4 power
balance; R6 reheating balance. Chemistry comes before energy because swapping charge materials changes the
kWh needed.
"""
import numpy as np

from steel.model import derived

ALL = frozenset(f"R{i}" for i in range(1, 9))


def _room(q, qc, m, v, scrap, scrap_lim):
    room = max(0.0, v[f"mat.{m}.cap"] - q[m] - qc[m])
    if m in scrap:
        room = min(room, max(0.0, scrap_lim - sum(q[k] + qc[k] for k in scrap)))
    return room


def _fix_yield(q, qc, v, mats, scrap, scrap_lim, target):
    yld = {m: v[f"mat.{m}.yield"] for m in mats}
    cur = sum(yld[m] * (q[m] + qc[m]) for m in mats)
    if cur > target:
        spot = sum(yld[m] * q[m] for m in mats)
        if spot > 0:
            f = max(0.0, (target - (cur - spot)) / spot)
            for m in mats:
                q[m] *= f
        return
    for m in mats:  # fill in the order materials are listed, respecting caps
        need = target - sum(yld[k] * (q[k] + qc[k]) for k in mats)
        if need <= 1e-9 * target:
            return
        q[m] += min(_room(q, qc, m, v, scrap, scrap_lim), need / yld[m])


def _substitute(q, qc, v, mats, scrap, scrap_lim, key, cm):
    """Swap tonnage from high-`key` to low-`key` materials, keeping liquid steel constant.

    Spot tonnage is swapped first; contract tonnage above its minimum offtake may be swapped too.
    """
    lim = v[f"lim.{key}"]
    k = {m: v[f"mat.{m}.{key}"] - lim for m in mats}
    yld = {m: v[f"mat.{m}.yield"] for m in mats}
    for a in sorted(mats, key=lambda m: -k[m]):
        for b in sorted(mats, key=lambda m: k[m]):
            excess = sum(k[m] * (q[m] + qc[m]) for m in mats)
            if excess <= 0:
                return
            gain = k[a] - k[b] * yld[a] / yld[b]   # excess removed per tonne of a swapped out
            slack = max(0.0, qc[a] - v[f"con.{a}.min"]) if a in cm else 0.0
            if a == b or gain <= 0 or q[a] + slack <= 0:
                continue
            take = min(excess / gain, q[a] + slack)
            from_spot = min(take, q[a])
            q[a] -= from_spot                       # free a's tonnage first so shared caps see it
            qc[a] -= take - from_spot
            add = min(take * yld[a] / yld[b], _room(q, qc, b, v, scrap, scrap_lim))
            q[b] += add
            q[a] += take - add * yld[b] / yld[a]    # give back what b could not absorb


def repair(inp, prob, z, rules=ALL):
    z = np.clip(np.asarray(z, float), prob.zlb, prob.zub)
    v, d, ny, yn = inp.v, derived(inp), prob.ny, prob.y_names
    st = inp.struct
    mats, cm, scrap = inp.mats(), inp.contract_mats(), inp.scrap()
    y = np.round(z[:ny])
    if "R7" in rules:  # at most one tier per family: keep the first one switched on
        for pref in ("sol.", "ppa."):
            on = [i for i, a in enumerate(yn) if a.startswith(pref) and y[i] > 0.5]
            y[on[1:]] = 0.0
    z[:ny] = y
    on = {a: y[i] > 0.5 for i, a in enumerate(yn)}
    scrap_lim = v["scrap.cap0"] + (v["opt.shred.extra"] if on["shred"] else 0.0)
    sol_cap = sum(v[f"sol.{t}.kwh"] for t in st["solar_tiers"] if on[f"sol.{t}"])
    ppa_cap = sum(v[f"ppa.{u}.kwh"] for u in st["ppa_tiers"] if on[f"ppa.{u}"])
    # clamp: when hot charging + heat recovery save more than the reheating need, no fuel is needed (never < 0)
    heat = max(0.0, d["H"] - d["D"] * ((v["opt.hot.save"] if on["hot"] else 0.0)
                                       + (v["opt.whr.save"] if on["whr"] else 0.0)))

    for s in range(prob.K):
        q = {m: z[prob.ix(s, f"q.{m}")] for m in mats}
        qc = {m: (z[prob.ix(s, f"qc.{m}")] if m in cm else 0.0) for m in mats}
        if "R8" in rules:
            for m in cm:
                qc[m] = min(max(qc[m], v[f"con.{m}.min"]), v[f"mat.{m}.cap"]) if on[f"con.{m}"] else 0.0
        if "R7" in rules:
            for m in mats:
                q[m] = min(q[m], max(0.0, v[f"mat.{m}.cap"] - qc[m]))
            spot = sum(q[m] for m in scrap)
            over = spot + sum(qc[m] for m in scrap) - scrap_lim
            if over > 0 and spot > 0:
                f = max(0.0, 1.0 - over / spot)
                for m in scrap:
                    q[m] *= f
        if "R1" in rules:
            _fix_yield(q, qc, v, mats, scrap, scrap_lim, d["L"])
        if "R2" in rules:
            _substitute(q, qc, v, mats, scrap, scrap_lim, "cu", cm)
        if "R3" in rules:
            _substitute(q, qc, v, mats, scrap, scrap_lim, "p", cm)
        for m in mats:
            z[prob.ix(s, f"q.{m}")] = q[m]
        for m in cm:
            z[prob.ix(s, f"qc.{m}")] = qc[m]

        jg, jsol, jppa, jsv, jfo, jng = (prob.ix(s, a) for a in ("g", "sol", "ppa", "sv", "fo", "ng"))
        scrap_t = sum(q[m] + qc[m] for m in scrap)
        if "R8" in rules:
            z[jsv] = v["opt.pre.save"] * scrap_t if on["pre"] else 0.0
        if "R5" in rules:
            z[jppa] = min(max(z[jppa], v["ppa.minfrac"] * ppa_cap), ppa_cap)
            z[jsol] = min(z[jsol], sol_cap)
        if "R4" in rules:
            need = sum(v[f"mat.{m}.kwh"] * (q[m] + qc[m]) for m in mats) + d["Eaux"] - z[jsv]
            if on["hot"]:
                need += v["opt.hot.kwh"] * d["D"]
            z[jsol] = min(z[jsol], max(0.0, need - z[jppa]))
            z[jg] = max(0.0, need - z[jsol] - z[jppa])
        if "R6" in rules:
            z[jng] = max(0.0, min(z[jng], heat)) if on["gas"] else 0.0
            z[jfo] = max(0.0, heat - z[jng])
    return z
