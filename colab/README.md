# Colab cross-check

Re-run the study by hand and confirm its numbers by an independent route.

## Files
- `crosscheck.py`: nine checks (inputs, objective, pareto, moran, kernel, gap, evals, stats, hypotheses). Each prints PASS/FAIL with its tolerance.
- `steel_decarb_colab.ipynb`: the notebook.

## Local
    python colab/crosscheck.py --results results_v2/quick    # exit code 1 if any check fails
    python colab/crosscheck.py --results results --only gap,stats

## Colab
1. Zip the repo folder contents (not `.git`) as `steel_decarb.zip`. Zip the `results_v2/` folder as `results.zip` for the last cell.
2. Open `steel_decarb_colab.ipynb` in Colab (File > Upload notebook).
3. Run cells 1 to 8 in order. Cell 1 asks for `steel_decarb.zip` (or use the commented Drive option).
4. Expected runtime: cells 1-6 about 1-3 min; cell 7 (`run_all.py --quick`) about 2-5 min; cell 8 about 2-6 min (Pareto re-solve and 999 permutations).

The full run (`--runs 15`, budget 10000, 14 processes; about 20 h) is for the local 16-thread PC, not free Colab.
Cell 8 only checks its saved files. The kernel is classically simulated; the plant is hypothetical.
