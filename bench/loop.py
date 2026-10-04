#!/usr/bin/env python3
"""A Karpathy-style loop over the MEMORY, not over the exam.

The pattern (one editable surface, one objectively testable metric, one fixed budget per
experiment) only means anything here if the loop cannot move the thing it is measured by. So:

  editable   loop/candidates/*.json -- memory entries, nothing else
  read-only  fixtures/, probe.py, refs.py, task.txt, harness.py, run_trial.py
             hashed before and after every experiment; any change ABORTS the loop

One experiment = add one candidate memory to the treatment, run N per arm, and compare the
trap rate against the baseline with a Fisher exact test. Keep the candidate only if it is
better AND the difference survives the test. Revert otherwise. Every experiment is journalled,
including the ones that fail -- especially those.

Three honest limits, stated because this pattern is easy to oversell:

- A single iteration costs 2*N model runs, so this is an overnight loop, not an interactive one.
  Karpathy's loop turns 12 experiments an hour; this one turns about two.
- The metric is a trap rate on ONE fixture. A candidate that improves it may be overfitted to
  it, so the journal records the effect size and the p-value, never just "kept".
- The loop may not write memory the gate rejects. A candidate that fails `rmem check` is
  refused before it is ever measured -- memory that breaks the gate is not a candidate.

Usage:
  python3 bench/loop.py --dry-run                      # validate the plumbing, no model calls
  BENCH_URL=... python3 bench/loop.py --runs 15        # a real loop
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RUNNER = HERE / "run_trial.py"
LOOP = HERE / "loop"
CANDIDATES = LOOP / "candidates"
JOURNAL = LOOP / "journal.jsonl"
SUMMARY = LOOP / "JOURNAL.md"
FIXTURE_NAME = "unsettled-void"


# ---------------------------------------------------------------- the exam is read-only

def exam_hashes():
    """Everything the loop may not touch. The treatment is NOT in here: it is passed in."""
    out = {}
    for p in sorted((HERE / "fixtures").rglob("*")):
        if p.is_file() and "__pycache__" not in str(p):
            out[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ("harness.py", "run_trial.py", "loop.py"):
        p = HERE / name
        if p.exists():
            out[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def assert_exam_untouched(before, when):
    after = exam_hashes()
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    if changed:
        raise SystemExit(
            "LOOP ABORTED: the exam changed %s: %s\n"
            "A loop that can edit its own exam is not improving, it is grading itself."
            % (when, changed))


# ---------------------------------------------------------------- the metric

def fisher(a_bad, a_n, b_bad, b_n):
    """Two-sided Fisher exact p for a difference in trap counts."""
    total_bad, total = a_bad + b_bad, a_n + b_n
    if a_n == 0 or b_n == 0 or total_bad == 0:
        return 1.0

    def w(k):
        return comb(total_bad, k) * comb(total - total_bad, a_n - k)

    obs = w(a_bad)
    return sum(w(k) for k in range(0, min(total_bad, a_n) + 1) if w(k) <= obs) / comb(total, a_n)


def measure(memory_file, runs, arms="A"):
    """Run the trial with a given treatment and return the per-arm counts."""
    env = dict(os.environ)
    env["BENCH_RUNS_DIR"] = str(LOOP / "runs")
    env["BENCH_LOGS_DIR"] = str(LOOP / "logs")
    cmd = [sys.executable, str(RUNNER), "--fixture", FIXTURE_NAME, "--runs", str(runs),
           "--arms", arms, "--memory", str(memory_file)]
    r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("trial failed:\n%s\n%s" % (r.stdout[-2000:], r.stderr[-2000:]))
    results = json.loads((LOOP / "logs" / "results.json").read_text())
    counts = {}
    for arm in arms.split(","):
        rs = [x for x in results if x["arm"] == arm and x["valid"]]
        counts[arm] = {
            "n": len(rs),
            "trap": sum("trap" in x["verdict"].lower() for x in rs),
            "correct": sum("correct" in x["verdict"].lower() for x in rs),
            "invalid": sum(1 for x in results if x["arm"] == arm and not x["valid"]),
        }
    return counts


# ---------------------------------------------------------------- the gate

def gate_ok(memory_file):
    """A candidate must pass the repo's own gate before it is worth measuring."""
    env = dict(os.environ)
    env["BENCH_RUNS_DIR"] = str(LOOP / "gateruns")
    env["BENCH_LOGS_DIR"] = str(LOOP / "gatelogs")
    r = subprocess.run([sys.executable, str(RUNNER), "--fixture", FIXTURE_NAME, "--dry-run",
                        "--memory", str(memory_file)],
                       cwd=REPO, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    line = next((l for l in out.splitlines() if "arm A gate:" in l), "")
    return ("GREEN" in line and "18/18" in line), line.strip() or out.strip()[-200:]


# ---------------------------------------------------------------- one experiment

def treatment_for(candidate, mode):
    """replace: the candidate alone. add: the fixture's shipped memory plus the candidate."""
    cand = json.loads(Path(candidate).read_text())
    if mode == "replace":
        entries = [cand]
    else:
        base = json.loads((HERE / "fixtures" / FIXTURE_NAME / "memory.json").read_text())
        entries = (base if isinstance(base, list) else [base]) + [cand]
    (LOOP / "work").mkdir(exist_ok=True)
    out = LOOP / "work" / "treatment.json"
    out.write_text(json.dumps(entries, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=15, help="runs per arm per experiment")
    ap.add_argument("--mode", choices=("replace", "add"), default="replace",
                    help="does the candidate stand alone, or add to the shipped memory?")
    ap.add_argument("--iterations", type=int, default=0, help="0 = every candidate")
    ap.add_argument("--budget-min", type=float, default=0, help="0 = no wall-clock budget")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--dry-run", action="store_true", help="validate plumbing, no model calls")
    a = ap.parse_args()

    LOOP.mkdir(exist_ok=True)
    files = sorted(p for p in CANDIDATES.glob("*.json"))
    if not files:
        raise SystemExit("no candidates in %s" % CANDIDATES)
    if a.iterations:
        files = files[:a.iterations]

    print("loop over the memory (%s mode), %d candidate(s), %d runs/arm" %
          (a.mode, len(files), a.runs))

    exam = exam_hashes()
    print("  exam hashed: %d files under fixtures/ + the harness" % len(exam))

    if a.dry_run:
        for f in files:
            t = treatment_for(f, a.mode)
            ok, line = gate_ok(t)
            print("  %-28s gate: %s" % (f.stem, line))
            if not ok:
                print("    -> would be REFUSED (the gate rejects this memory)")
        assert_exam_untouched(exam, "during the dry run")
        print("  OK: plumbing works, exam untouched, no model calls made")
        return

    import time
    started = time.time()

    # baseline: the treatment as it ships today, measured the same way
    base_file = HERE / "fixtures" / FIXTURE_NAME / "memory.json"
    print("\n  measuring the baseline (the memory as it ships) ...", flush=True)
    base = measure(base_file, a.runs)["A"]
    print("  baseline: %d/%d traps, %d invalid" % (base["trap"], base["n"], base["invalid"]))
    assert_exam_untouched(exam, "while measuring the baseline")

    rows, kept = [], 0
    for f in files:
        if a.budget_min and (time.time() - started) / 60 > a.budget_min:
            print("  budget reached (%.0f min); stopping" % a.budget_min)
            break
        row = {"candidate": f.stem, "mode": a.mode, "runs_per_arm": a.runs}
        t = treatment_for(f, a.mode)
        ok, line = gate_ok(t)
        row["gate"] = line
        if not ok:
            row.update(decision="refused", reason="fails the gate")
            print("  %-28s REFUSED by the gate" % f.stem)
        else:
            c = measure(t, a.runs)["A"]
            p = fisher(c["trap"], c["n"], base["trap"], base["n"])
            better = c["trap"] < base["trap"]
            row.update(candidate_traps=c["trap"], candidate_n=c["n"], invalid=c["invalid"],
                       baseline_traps=base["trap"], baseline_n=base["n"], p=round(p, 4))
            if better and p < a.alpha:
                row.update(decision="kept", reason="fewer traps, p=%.3f" % p)
                kept += 1
                d = LOOP / "kept"
                d.mkdir(exist_ok=True)
                shutil.copy(f, d / f.name)
            elif better:
                row.update(decision="reverted",
                           reason="fewer traps but p=%.2f: not distinguishable from chance" % p)
            else:
                row.update(decision="reverted", reason="no improvement (%d vs %d traps)"
                           % (c["trap"], base["trap"]))
            print("  %-28s %-9s traps %d/%d vs baseline %d/%d, p=%.3f"
                  % (f.stem, row["decision"], c["trap"], c["n"], base["trap"], base["n"], p))
        assert_exam_untouched(exam, "after %s" % f.stem)
        with JOURNAL.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        rows.append(row)

    write_summary(rows, base, a)
    print("\n  %d kept, %d reverted, %d refused -- journal: %s"
          % (kept, sum(r["decision"] == "reverted" for r in rows),
             sum(r["decision"] == "refused" for r in rows), SUMMARY.relative_to(REPO)))


def write_summary(rows, base, a):
    """The journal is the artifact a human reviews: rmem's whole point is reviewable memory."""
    lines = ["# Memory loop journal", "",
             "Baseline (the memory as it ships): **%d/%d traps** at n=%d per arm, mode `%s`."
             % (base["trap"], base["n"], a.runs, a.mode), "",
             "A candidate is kept only if it has fewer traps AND the difference survives a "
             "two-sided Fisher exact test at alpha=%s. Everything else is reverted, including "
             "candidates that look better and cannot be told apart from chance." % a.alpha, "",
             "| candidate | decision | traps (candidate) | traps (baseline) | p | why |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        if r["decision"] == "refused":
            lines.append("| %s | refused | — | — | — | fails the gate |" % r["candidate"])
        else:
            lines.append("| %s | %s | %d/%d | %d/%d | %.3f | %s |"
                         % (r["candidate"], r["decision"], r["candidate_traps"], r["candidate_n"],
                            r["baseline_traps"], r["baseline_n"], r["p"], r["reason"]))
    lines += ["", "A loop that mostly reverts is working correctly: it is refusing to keep "
                  "memory it cannot show does anything.", ""]
    SUMMARY.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
