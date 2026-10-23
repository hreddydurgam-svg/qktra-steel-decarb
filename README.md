# QKTRA steel decarbonisation study: code, data and results

Code, input data, results and supplementary material for the manuscript

> **Reducing Heuristic Fragmentation in a Decarbonised Steel Supply Network: Repair Operator, Exact LP Completion,
> Epsilon-Constraint Trade-offs and a Quantum-Kernel Test**.

The study plans investments and suppliers for a **hypothetical** 120,000 t/year rebar plant in Ranipet, India, as a
two-stage stochastic mixed-integer linear program (MILP). It compares heuristic search methods, including QKTRA
(Quantum-Kernel Topological Rerouting Algorithm), against the exact MILP optimum. The quantum kernel is simulated on
an ordinary computer; no quantum hardware is used and no speed-up is claimed.

## Contents

| Path | What it is |
|---|---|
| `run_all.py` | The one script that runs the whole study and writes every table and figure file. |
| `src/steel/` | The model, heuristics, repair rules, kernel, statistics and spatial analysis (13 modules). |
| `data/inputs.csv` | All 70 model inputs, each with its value, range, source number and retrieval date. |
| `data/SOURCES.md` | The numbered source list (sources 1 to 35). |
| `data/structure.json`, `data/nodes.csv` | Model structure and the 32 places of the spatial analysis. |
| `data/correlation.csv`, `data/series/` | Price correlation and the monthly price series it is computed from. |
| `colab/crosscheck.py` | The second check program: nine independent checks of the results (see below). |
| `colab/steel_decarb_colab.ipynb` | Notebook that runs the quick test and the checks in Google Colab (see `colab/README.md`). |
| `results_v2/` | Results of the full run used in the paper, with SHA-256 checksums (`SHA256SUMS.txt`). |
| `results_v2/quick/` | Results of the short test run, kept for comparison. |
| `logs/` | Log of the full run (17 to 18 October 2026, 20.31 hours, exit 0; UTF-16 text). |
| `supplementary/Supplementary_Information.docx` | Supplementary Information: Table S1 (sensitivity), Table S2 (all inputs) and the data-source list. |

## Requirements

Python 3.13 with numpy 2.4.4, scipy 1.17.1 and matplotlib. The exact solver is HiGHS, called through
`scipy.optimize.milp`; no other solver is needed.

    conda env create -f environment.yml
    conda activate steel-decarb

or

    pip install -r requirements.txt

The full run used Python 3.13.14, numpy 2.4.4 and scipy 1.17.1 (`results_v2/run_meta.json`).

## Run

Short test (a few minutes, one process):

    python run_all.py --quick --out results_quick

Full run as in the paper (15 runs per method and instance, budget 10,000 evaluations):

    python run_all.py --runs 15 --workers 14 --out results_rerun

On a 16-core computer with 14 worker processes the full run took 20.31 hours. Results do not depend on the number
of workers. The run can be stopped at any time; the same command continues from the saved files.

**Write to a new folder.** Do not use `--out results_v2`: that folder holds the published results, and the script
would reuse its saved files instead of running the study again, and then overwrite them. If the settings, data or
code differ from those of a saved run, the script stops and names the difference; `--fresh` deletes the saved
files of that folder and starts over.

## Check the results

Checksums of the published results (the checksums file was written on Windows, so `sha256sum -c` cannot read it;
this command works on any system):

    python -c "import hashlib,pathlib as p;L=[l.split(None,1) for l in open('results_v2/SHA256SUMS.txt',encoding='utf-8-sig') if l.strip()];b=[f for h,f in L if hashlib.sha256(p.Path('results_v2',f.strip().replace(chr(92),'/')).read_bytes()).hexdigest()!=h.lower()];print(len(L)-len(b),'of',len(L),'match',b)"

Second check program (nine checks: inputs, objective, Pareto front, Moran's I, kernel, gaps, evaluations to
target, statistics, hypothesis verdicts; each prints PASS or FAIL, exit code 1 if any fails):

    python colab/crosscheck.py --results results_v2

It was written separately from the main code by the same authors. It re-derives the statistics and every verdict
with its own code, but it reuses the main code to load the inputs, build the price scenarios, build and solve the
model and compute the front. It checks the Moran permutation p-values only roughly (999 permutations). On the
published results it passes all nine checks (`results_v2/PACKAGE_INFO.txt`).

## Where the paper's results come from

| Paper | File in `results_v2/` |
|---|---|
| Hypotheses H1 to H8 and their verdicts | `hypotheses.csv`, `stats_pairs.csv` |
| Benchmark tables, gaps, evaluations to 1% | `bench.csv` (one row per run; `bench_raw.csv` before the exact optimum is added) |
| Stage A (scaling test on the LP) | `stage_a.csv` |
| Cost and emission front | `pareto.csv`, `fig_pareto.png` |
| Value of the stochastic solution | `vss.csv` |
| Moran's I and local clusters | `moran.csv`, `moran_purchase.csv`, `lisa.csv`, `fig_moran.png` |
| Gap and time figures | `fig_gap.png`, `fig_scaling.png` |
| Tuned settings of each method | `tuned.json` |
| Supplementary Table S1 | `sensitivity.csv` |

## Limits of the data

The plant is hypothetical. Prices, tariffs, emission factors and locations are based on the sources in
`data/SOURCES.md`; 24 of the 70 inputs are assumptions chosen by the authors, marked in `data/inputs.csv` and in
Supplementary Table S2. Web sources can change after the stated retrieval dates. Section 9 of the paper lists all
limitations.

## Licence and citation

MIT Licence (see `LICENSE`). The data in `data/` are compiled from the public sources listed in `data/SOURCES.md`;
those sources keep their own terms. Citation and DOI: [AUTHOR: add after acceptance.]
