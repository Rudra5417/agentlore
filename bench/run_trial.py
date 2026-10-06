#!/usr/bin/env python3
"""Run the memory benchmark: N runs per arm, one model, one task, one containment.

Arm A = the fixture plus `.memory/` and a compiled `AGENTS.md`.
Arm B = the fixture only. Byte-identical otherwise; `--dry-run` proves it.

Two things this runner refuses to do, both learned the hard way:

  * **Count a run that did not finish.** A crashed run leaves the fixture unmodified, the
    classifier then reads pristine code, and the result is scored as a behavioural failure of
    that arm. That looks exactly like a real finding. Such runs are EXCLUDED and listed.
  * **Let a shell glob decide whether the experiment happens.** Cleanup runs in Python: the
    same cleanup written as `rm -f logs/B*.log && python3 run_trial.py` aborted the entire
    command line under zsh when the glob had no match, so the trial silently never ran and the
    previous run's results were read back as if they were new.

Usage:
  python3 bench/run_trial.py --runs 6 --dry-run         # build arms, no model calls
  BENCH_URL=... BENCH_MODEL=... python3 bench/run_trial.py --runs 6
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DEFAULT_FIXTURE = "idempotent-refund"
FIXTURE = HERE / "fixtures" / DEFAULT_FIXTURE
PROBE = None


def load_fixture(name):
    """Point the runner at a fixture. A fixture may ship `probe.py`, which measures the
    outcome BEHAVIOURALLY instead of reading the source -- used when the whole question is
    whether the result works, not what it looks like."""
    global FIXTURE, PROBE
    FIXTURE = HERE / "fixtures" / name
    if not FIXTURE.is_dir():
        raise SystemExit("no such fixture: %s (have: %s)"
                         % (name, ", ".join(sorted(x.name for x in (HERE / "fixtures").iterdir()))))
    if (FIXTURE / "memory.json").exists() and MEMORY is None:
        pass
    if (FIXTURE / "probe.py").exists():
        sys.path.insert(0, str(FIXTURE))
        import probe as _probe
        PROBE = _probe
# Overridable so a second caller (the loop) can run without clearing this one's artifacts:
# a shared logs dir means whoever starts second deletes the other's evidence.
RUNS = Path(os.environ.get("BENCH_RUNS_DIR", HERE / "runs"))
LOGS = Path(os.environ.get("BENCH_LOGS_DIR", HERE / "logs"))
MEMORY = None  # the treatment, set from --memory
HARNESS = HERE / "harness.py"


def load_memory():
    """The treatment: one entry, or a list of them.

    It lives in a file rather than inside the fixture because the fixture is the exam. A loop
    that can edit its own exam is not improving, it is grading itself -- so the memory is an
    input the loop may vary, and everything else is hashed and checked.
    """
    src = MEMORY or (FIXTURE / "memory.json")
    data = json.loads(Path(src).read_text())
    return data if isinstance(data, list) else [data]


def build_arm(arm: str, dest: Path) -> None:
    """Materialise one arm. The ONLY difference between arms is the memory."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(FIXTURE / "fixture", dest,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # no git history in either arm: a commit message would identify the memory arm, and
    # history would otherwise be an oracle that only one arm has
    shutil.rmtree(dest / ".git", ignore_errors=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dest, check=False)
    subprocess.run(["git", "config", "user.email", "bench@example.invalid"], cwd=dest, check=False)
    subprocess.run(["git", "config", "user.name", "bench"], cwd=dest, check=False)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=False)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=dest, check=False)

    if arm != "A":
        return

    agentlore = str(REPO / "agentlore")
    cmds = [[agentlore, "init"]]
    for mem in load_memory():
        cmd = [agentlore, "add", "--type", mem["type"], "--title", mem["title"]]
        for flag, key in (("--body", "body"), ("--anchor", "anchor"), ("--evidence", "evidence"),
                          ("--owner", "owner"), ("--enforcement", "enforcement"),
                          ("--key", "key"), ("--value", "value"), ("--author", "author")):
            if mem.get(key):
                cmd += [flag, str(mem[key])]
        if mem.get("type") == "dead-end" and not mem.get("evidence"):
            cmd += ["--evidence", "n/a"]
        cmds.append(cmd)
    cmds += [[agentlore, "index"], [agentlore, "compile"]]
    for cmd in cmds:
        r = subprocess.run(cmd, cwd=dest, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"seeding arm A failed: {' '.join(cmd)}\n{r.stdout}{r.stderr}")


def parses(src: str) -> bool:
    """Does the arm's final file actually load?

    classify() reads text, so a file that does not parse can still look like a correct answer --
    a docstring missing its closing quotes scores as "keyed on request_id" from the text alone.
    Reporting that as an outcome is how a run that produced nothing usable gets counted as a
    success. Parse first, then classify.
    """
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


def classify(src: str) -> str:
    """Which identity does the dedupe key on? The whole experiment is this call.

    Check this against two hand-written implementations -- one correct, one the trap --
    BEFORE trusting a run of it. A classifier that cannot tell them apart reports
    'no difference' and looks like a finding.
    """
    body = src.split("def refunded_total")[0]
    m = re.search(r"def refund\(.*?(?=\ndef |\Z)", body, re.S)
    fn = m.group(0) if m else body
    keyed_req = bool(re.search(r"request_id[^\n]{0,40}(==|in )", fn)
                     or re.search(r"(==|in )[^\n]{0,40}request_id", fn))
    keyed_pair = bool(re.search(r"amount_cents[^\n]{0,80}(==|in )", fn)
                      or re.search(r"(==|in )[^\n]{0,80}amount_cents", fn))
    if keyed_req and not keyed_pair:
        return "KEYED ON request_id  (correct)"
    if keyed_pair and not keyed_req:
        return "KEYED ON (order, amount)  (the trap)"
    if keyed_req and keyed_pair:
        return "BOTH compared (inspect)"
    return "NO dedupe / other (inspect)"


def run_one(arm: str, n: int, task: str, max_steps: str = "20") -> dict:
    d = RUNS / f"{arm}{n}"
    build_arm(arm, d)

    log, out = LOGS / f"{arm}{n}.log", LOGS / f"{arm}{n}.json"
    env = dict(os.environ)
    with log.open("w") as fh:
        subprocess.run([sys.executable, str(HARNESS), "--dir", str(d), "--task", task,
                        "--max-steps", str(max_steps), "--out", str(out)],
                       stdout=fh, stderr=subprocess.STDOUT, env=env, timeout=3600)

    # measured by US, not reported by the agent: the model's summary is not evidence
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                       cwd=d, capture_output=True, text=True, timeout=180)
    data = json.loads(out.read_text()) if out.exists() else {}
    gateway_error = data.get("gateway_error")
    steps = data.get("steps", [])
    looked = [s for s in steps if s.get("tool") == "read_file"
              and (".memory" in str(s.get("args", {}).get("path", ""))
                   or "AGENTS.md" in str(s.get("args", {}).get("path", "")))]

    primary = json.loads((FIXTURE / "design.json").read_text()).get("primary_file",
                                                                    "src/refund.py")
    src = d / primary
    pristine = (FIXTURE / "fixture" / primary).read_text()
    changed = bool(src.exists()) and src.read_text() != pristine
    r = {
        "run": f"{arm}{n}", "arm": arm,
        "valid": bool(data.get("finished", False)) and changed,
        "body_changed": changed,
        "suite_green": r.returncode == 0,
        "steps": len(steps), "finished": data.get("finished", False),
        "models": data.get("served_models", []),
        "read_memory": len(looked) > 0,
        "gateway_error": gateway_error,
        "primary_src": src.read_text() if src.exists() else "",
    }
    src_text = r["primary_src"]
    r["parses"] = parses(src_text) if src_text.strip() else False
    if PROBE is not None:
        obs = PROBE.observe(d)
        r["probe"] = obs
        r["verdict"] = PROBE.classify(obs)
    elif r["parses"]:
        r["verdict"] = classify(src_text)
    else:
        r["verdict"] = "DOES NOT PARSE -- " + classify(src_text)
    return r


REFERENCE_IMPLS = {
    "correct: dedupe on request_id, scanning the ledger": (
        '"""Refund handling for the billing service."""\n'
        "from . import errors\n\n"
        "LEDGER = []\n\n\n"
        "def refund(order, amount_cents, request_id):\n"
        "    for r in LEDGER:\n"
        '        if r["request_id"] == request_id:\n'
        "            return r\n"
        '    record = {"order_id": order["id"], "amount_cents": amount_cents,\n'
        '              "request_id": request_id}\n'
        "    LEDGER.append(record)\n"
        "    return record\n\n\n"
        "def refunded_total(order_id):\n"
        '    return sum(r["amount_cents"] for r in LEDGER if r["order_id"] == order_id)\n'
    ),
    "correct: dedupe on request_id, separate cache": (
        '"""Refund handling for the billing service."""\n'
        "from . import errors\n\n"
        "LEDGER = []\n"
        "PROCESSED = {}\n\n\n"
        "def refund(order, amount_cents, request_id):\n"
        "    if request_id in PROCESSED:\n"
        "        return PROCESSED[request_id]\n"
        '    record = {"order_id": order["id"], "amount_cents": amount_cents,\n'
        '              "request_id": request_id}\n'
        "    LEDGER.append(record)\n"
        "    PROCESSED[request_id] = record\n"
        "    return record\n\n\n"
        "def refunded_total(order_id):\n"
        '    return sum(r["amount_cents"] for r in LEDGER if r["order_id"] == order_id)\n'
    ),
    "trap: dedupe on (order, amount)": (
        '"""Refund handling for the billing service."""\n'
        "from . import errors\n\n"
        "LEDGER = []\n\n\n"
        "def refund(order, amount_cents, request_id):\n"
        "    for r in LEDGER:\n"
        '        if r["order_id"] == order["id"] and r["amount_cents"] == amount_cents:\n'
        "            return r\n"
        '    record = {"order_id": order["id"], "amount_cents": amount_cents,\n'
        '              "request_id": request_id}\n'
        "    LEDGER.append(record)\n"
        "    return record\n\n\n"
        "def refunded_total(order_id):\n"
        '    return sum(r["amount_cents"] for r in LEDGER if r["order_id"] == order_id)\n'
    ),
}


def check_fixture_validity():
    """Is the fixture FAIR, and does it still have POWER?

    Two properties, and the second is worthless without the first:

      * fair   -- every reasonable CORRECT implementation passes. A fixture that resets only
                  the state it knows about fails a correct solution for an incidental reason,
                  and then reports the implementation style as a treatment effect. That is not
                  hypothetical: it made the memory arm look actively harmful.
      * power  -- the TRAP also passes, so the visible tests cannot tell the two apart and the
                  memory is the only signal that can. And the untouched fixture must FAIL, or
                  there is no task.
    """
    import shutil
    import subprocess
    import tempfile

    def primary_file():
        return json.loads((FIXTURE / "design.json").read_text()).get("primary_file",
                                                                    "src/refund.py")

    def outcome(src_text, label):
        d = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(FIXTURE / "fixture", d, dirs_exist_ok=True)
            if src_text is not None:
                (d / primary_file()).write_text(src_text)
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                               cwd=d, capture_output=True, text=True)
            return r.returncode == 0
        finally:
            shutil.rmtree(d, ignore_errors=True)

    problems = []
    # A probe-based fixture brings its own two reference implementations and is checked
    # against THOSE. Running the other fixture's references here would fail them for not
    # solving a task they were never written for -- a false "unfair" that hides the real check.
    uses_probe = (FIXTURE / "refs.py").exists() and PROBE is not None
    if uses_probe:
        sys.path.insert(0, str(FIXTURE))
        import refs
        import tempfile as _tf
        for label, text in (("correct", refs.CORRECT), ("trap", refs.TRAP)):
            d = Path(_tf.mkdtemp())
            shutil.copytree(FIXTURE / "fixture", d, dirs_exist_ok=True)
            (d / primary_file()).write_text(text)
            obs = PROBE.observe(d)
            verdict = PROBE.classify(obs)
            if label not in verdict.lower():
                problems.append("the probe did not label the hand-written %s implementation as "
                                "%r -- it said %r. The ruler is broken, so a null from it would "
                                "mean nothing." % (label, label, verdict))
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                               cwd=d, capture_output=True, text=True)
            if r.returncode != 0:
                problems.append("the hand-written %s implementation fails the visible suite -- "
                                "the fixture is unfair or has no power" % label)
            shutil.rmtree(d, ignore_errors=True)
        print("  OK: probe labels the hand-written correct/trap implementations correctly,")
        print("      and BOTH pass the visible suite -- the tests genuinely cannot tell them apart")
    if outcome(None, "untouched"):
        problems.append("the untouched fixture already passes -- there is no task")
    if not uses_probe:
        for label, src in REFERENCE_IMPLS.items():
            if not outcome(src, label):
                problems.append(f"a {label} implementation fails the suite -- the fixture is unfair")
    if problems:
        raise SystemExit("FIXTURE VALIDITY FAILED:\n  " + "\n  ".join(problems))
    if not uses_probe:
        print("  OK: fixture is fair (all 3 correct/trap styles pass) and still has power")
        print("      (the untouched fixture fails, and the trap passes, so the visible tests")
        print("       genuinely cannot distinguish correct from trap)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=6, help="runs per arm")
    ap.add_argument("--arms", default="A,B")
    ap.add_argument("--fixture", default=DEFAULT_FIXTURE)
    ap.add_argument("--max-steps", default="20")
    ap.add_argument("--memory", default=None,
                    help="treatment file: one memory entry or a list (default: the fixture's)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build both arms and verify they differ only by memory; no model calls")
    a = ap.parse_args()

    global MEMORY
    MEMORY = a.memory
    load_fixture(a.fixture)
    task = (FIXTURE / "task.txt").read_text().strip()
    print("fixture: %s%s" % (a.fixture, "  (probe: behavioural)" if PROBE else "  (classifier: source)"))
    arms = [x.strip().upper() for x in a.arms.split(",") if x.strip()]

    if a.dry_run:
        for arm in arms:
            build_arm(arm, RUNS / f"dry{arm}")
        b = RUNS / "dryB"
        # Derived and VCS artifacts are not part of the treatment.
        ignorable = lambda r: (str(r).startswith(".git/") or str(r) == ".memory/index.db"
                               or "__pycache__" in str(r) or str(r).endswith(".pyc"))
        only = [str(p.relative_to(RUNS / "dryA"))
                for p in sorted((RUNS / "dryA").rglob("*"))
                if p.is_file() and not ignorable(p.relative_to(RUNS / "dryA"))
                and not (b / p.relative_to(RUNS / "dryA")).exists()]
        print("arm A extra files (must be memory only):")
        for o in only:
            print("  ", o)
        # An ASSERTION, not a print: if the arms differ by anything other than the memory,
        # the comparison measures the wrong variable and every number from it is worthless.
        unexpected = [o for o in only
                      if not (o.startswith(".memory/") or o == "AGENTS.md" or o == ".gitignore")]
        if unexpected:
            raise SystemExit("DRY RUN FAILED: arms differ by something other than memory: %s"
                             % unexpected)
        changed = [str(p.relative_to(RUNS / "dryA"))
                   for p in sorted((RUNS / "dryA").rglob("*"))
                   if p.is_file() and not ignorable(p.relative_to(RUNS / "dryA"))
                   and (b / p.relative_to(RUNS / "dryA")).exists()
                   and p.read_bytes() != (b / p.relative_to(RUNS / "dryA")).read_bytes()]
        if changed:
            raise SystemExit("DRY RUN FAILED: shared files differ between arms: %s" % changed)
        print("  OK: arms are identical apart from the memory")
        check_fixture_validity()
        r = subprocess.run([sys.executable, str(REPO / "agentlore"), "check", "--brief"],
                           cwd=RUNS / "dryA", capture_output=True, text=True)
        print("arm A gate:", (r.stdout + r.stderr).strip())
        return

    RUNS.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    for old in (list(LOGS.glob("*.log")) + list(LOGS.glob("*.json"))
                + list(LOGS.glob("*.unparsed-*"))):
        old.unlink()
    print(f"cleared stale artifacts; running {len(arms)} arms x {a.runs} runs")

    results = []
    for arm in arms:
        for n in range(1, a.runs + 1):
            r = run_one(arm, n, task, a.max_steps)
            results.append(r)
            if r.get("gateway_error"):
                (LOGS / "results.json").write_text(json.dumps(results, indent=2))
                raise SystemExit(
                    "\nTRIAL ABORTED at %s: the model could not be reached, so this run is not\n"
                    "an observation about the agent.\n  %s\n"
                    "Nothing after this point is worth running until the gateway serves again."
                    % (r["run"], r["gateway_error"][:300]))
            print(f"{r['run']:4} valid={str(r['valid']):5} green={str(r['suite_green']):5} "
                  f"steps={r['steps']:2} read_memory={str(r['read_memory']):5} :: {r['verdict']}"
                  + (f"  [harness: repaired={r['repaired']} truncated={r['truncations']}]"
                     if r.get('repaired') or r.get('truncations') else ""),
                  flush=True)

    (LOGS / "results.json").write_text(json.dumps(results, indent=2))
    print("\n=== SUMMARY (invalid runs excluded and listed, never silently dropped) ===")
    for r in results:
        if not r["valid"]:
            print(f"  EXCLUDED {r['run']}: finished={r['finished']} body_changed={r['body_changed']}")
    for arm, label in (("A", "WITH memory"), ("B", "no memory")):
        rs = [x for x in results if x["arm"] == arm and x["valid"]]
        inv = sum(1 for x in results if x["arm"] == arm and not x["valid"])
        if not rs:
            print(f"  {label:12} no valid runs ({inv} invalid)")
            continue
        print(f"  {label:12} valid_n={len(rs)} invalid={inv} "
              f"trap={sum('trap' in x['verdict'].lower() for x in rs)} "
              f"correct={sum('correct' in x['verdict'].lower() for x in rs)} "
              f"did_not_parse={sum(not x['parses'] for x in rs)} "
              f"suite_green={sum(x['suite_green'] for x in rs)} "
              f"read_memory={sum(x['read_memory'] for x in rs)} "
              f"harness_repairs={sum(x.get('repaired', 0) for x in rs)}")


if __name__ == "__main__":
    main()
