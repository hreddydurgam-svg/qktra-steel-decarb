"""Load and validate model inputs. One CSV row per parameter, every row sourced."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass

REQUIRED_META = ("source", "url_or_ref", "retrieved_on")
DISTS = ("fixed", "normal", "lognormal", "triangular")


@dataclass(frozen=True)
class Dist:
    kind: str
    low: float   # normal / lognormal: standard deviation; triangular: minimum
    high: float  # triangular: maximum; unused otherwise


@dataclass
class Inputs:
    v: dict
    dist: dict
    struct: dict

    def mats(self):
        return [m["name"] for m in self.struct["materials"]]

    def scrap(self):
        return [m["name"] for m in self.struct["materials"] if m["kind"] == "scrap"]

    def dri(self):
        return [m["name"] for m in self.struct["materials"] if m["kind"] == "dri"]

    def contract_mats(self):
        return [m["name"] for m in self.struct["materials"] if m["contract"]]

    def stochastic_ids(self):
        return sorted(k for k, d in self.dist.items() if d.kind != "fixed")

    def with_values(self, over):
        return Inputs({**self.v, **over}, self.dist, self.struct)


def required_ids(struct):
    ids = ["plant.demand", "plant.roll_yield", "plant.kwh_aux", "plant.reheat", "lim.cu", "lim.p",
           "scrap.cap0", "grid.price", "grid.ef", "sol.var", "ppa.price", "ppa.minfrac",
           "fo.price", "fo.ef", "ng.price", "ng.ef", "opt.whr.fix", "opt.whr.save", "opt.hot.fix",
           "opt.hot.save", "opt.pre.fix", "opt.pre.save", "opt.gas.fix", "opt.shred.fix",
           "opt.shred.extra", "fx.inr_per_usd", "freight.tariff", "freight.ef",
           "opt.pre.fuel", "opt.hot.kwh"]
    for m in struct["materials"]:
        ids += [f"mat.{m['name']}.{k}" for k in ("price", "yield", "cu", "p", "ef", "cap", "kwh", "dist")]
        if m["contract"]:
            ids += [f"con.{m['name']}.{k}" for k in ("disc", "min", "fee")]
    for t in struct["solar_tiers"]:
        ids += [f"sol.{t}.kwh", f"sol.{t}.fix"]
    for u in struct["ppa_tiers"]:
        ids += [f"ppa.{u}.kwh", f"ppa.{u}.fix"]
    return ids


def _num(text):
    text = (text or "").strip()
    return float(text) if text else 0.0


def load_inputs(csv_path, struct_path):
    with open(struct_path, encoding="utf-8") as f:
        struct = json.load(f)
    v, dist, problems, seen = {}, {}, [], set()
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            key = (row.get("id") or "").strip()
            if not key:
                continue
            if key in seen:
                problems.append(f"line {line} {key}: duplicate id")
                continue
            seen.add(key)
            if not (row.get("value") or "").strip():
                problems.append(f"line {line} {key}: empty value")
                continue
            for col in REQUIRED_META:
                if not (row.get(col) or "").strip():
                    problems.append(f"line {line} {key}: empty {col}")
            kind = (row.get("distribution") or "").strip().lower() or "fixed"
            if kind not in DISTS:
                problems.append(f"line {line} {key}: unknown distribution '{kind}'")
                continue
            try:
                val, low, high = _num(row["value"]), _num(row["low"]), _num(row["high"])
            except ValueError:
                problems.append(f"line {line} {key}: non-numeric value/low/high")
                continue
            if kind in ("normal", "lognormal") and low <= 0:
                problems.append(f"line {line} {key}: {kind} needs standard deviation > 0 in 'low'")
            if kind == "triangular" and not (low <= val <= high and low < high):
                problems.append(f"line {line} {key}: triangular needs low <= value <= high")
            v[key], dist[key] = val, Dist(kind, low, high)
    for key in required_ids(struct):
        if key not in v:
            problems.append(f"{key}: missing required id")
    if problems:
        raise ValueError("inputs.csv problems:\n  " + "\n  ".join(problems))
    return Inputs(v, dist, struct)
