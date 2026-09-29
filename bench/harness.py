#!/usr/bin/env python3
"""A minimal coding agent, used to measure whether repo memory changes agent behaviour.

Deliberately contained, and deliberately dumb. Two properties make the measurement valid,
and both are easy to get wrong:

1. **Containment is the contamination defence.** The only tools are
   `list_dir` / `read_file` / `write_file` / `run_tests`, every path resolved under the arm
   directory, so the agent cannot read anything outside the repo under test. This is why it
   is not a subagent of some larger assistant: a subagent inherits the assistant's skills and
   can find the answer in them.

2. **`AGENTS.md` is injected, not requested.** Real hosts (Claude Code, Copilot, Codex,
   Cursor, Hermes) load the project context file themselves; the model never has to choose to
   open it. Measured: given only a system-prompt line saying "read AGENTS.md first", a model
   skipped it in 3 of 3 runs. A harness that merely asks is not a stand-in for a real host, so
   this one injects the file exactly as a host does. An arm with no `AGENTS.md` injects
   nothing, which is the control.

One JSON object per turn, no native tool-calling, so any chat model can drive it.

Environment:
  BENCH_URL    OpenAI-compatible chat-completions endpoint (Ollama, a gateway, a hosted API)
  BENCH_MODEL  model name to request
  BENCH_PACE   seconds to sleep between calls (rate-limit safety); 0 disables
  BENCH_RETRIES  attempts per call before giving up
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GATEWAY = os.environ.get("BENCH_URL", "http://localhost:11434/v1/chat/completions")
MODEL = os.environ.get("BENCH_MODEL", "llama3:latest")
PACE_S = float(os.environ.get("BENCH_PACE", "0"))
RETRIES = int(os.environ.get("BENCH_RETRIES", "9"))

SYSTEM = """You are a careful software engineer working in a small Python repository.

Respond with EXACTLY ONE JSON object per turn, and nothing else:

{"thought": "<one or two sentences>", "tool": "<tool name>", "args": {...}}

Tools:
- list_dir  {"path": "."}                      recursive listing of a directory
- read_file {"path": "src/refund.py"}          read a file
- write_file {"path": "src/refund.py", "content": "..."}   write a whole file
- run_tests {}                                 run the test suite
- done      {"summary": "..."}                 finish

Rules:
- Exactly one tool per turn. No prose outside the JSON object.
- Read the code before changing it.
- Keep the existing tests passing.
- When the tests pass and the task is complete, call done."""


def extract_json(text):
    """Pull the first JSON object with a 'tool' key out of a model reply."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        obj = json.loads(t)
        if isinstance(obj, dict) and "tool" in obj:
            return obj
    except Exception:
        pass
    for start in (i for i, ch in enumerate(text) if ch == "{"):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict) and "tool" in obj:
                            return obj
                    except Exception:
                        pass
                    break
    return None


def call_model(messages, timeout=180):
    """One model call, paced and retried.

    A 429 or a truncated reply mistaken for a model decision would be scored as the agent's
    behaviour, which is exactly the measurement error that produces a confident wrong answer.
    4096 tokens because a write_file call carries a whole file inside its JSON: at 1600 the
    reply was cut mid-object and the run ended unparseable.
    """
    body = json.dumps({
        "model": MODEL, "messages": messages, "temperature": 0, "max_tokens": 4096,
    }).encode()
    last = "?"
    for attempt in range(1, RETRIES + 1):
        if PACE_S:
            time.sleep(PACE_S)
        req = urllib.request.Request(GATEWAY, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                served = r.headers.get("x-warden-model", "?")
                raw = r.read().decode()
            data = json.loads(raw)
            if "choices" in data:
                return data["choices"][0]["message"]["content"], served
            last = raw[:300]
        except urllib.error.HTTPError as e:
            last = e.read().decode()[:300]
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:
            last = str(e)[:300]
        if attempt < RETRIES:
            time.sleep(min(20 * attempt, 90))
    return json.dumps({"thought": "gateway error", "tool": "_error",
                       "args": {"detail": last}}), "?"


def safe(root: Path, rel: str):
    """Resolve `rel` under `root`, refusing to escape it."""
    p = (root / rel).resolve()
    if root.resolve() != p and root.resolve() not in p.parents:
        raise ValueError(f"path escapes the repository: {rel}")
    return p


def do_tool(root: Path, tool: str, args: dict):
    if tool == "list_dir":
        base = safe(root, args.get("path", "."))
        out = []
        for p in sorted(base.rglob("*")):
            if "__pycache__" in p.parts or p.name.endswith(".pyc"):
                continue
            out.append(f"{p.relative_to(root)}" + ("/" if p.is_dir() else ""))
        return "\n".join(out[:400]) or "(empty)"

    if tool == "read_file":
        p = safe(root, args["path"])
        if not p.is_file():
            return f"(no such file: {args['path']})"
        return p.read_text()[:20000]

    if tool == "write_file":
        p = safe(root, args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args.get("content", ""))
        return f"wrote {args['path']} ({len(args.get('content', ''))} bytes)"

    if tool == "run_tests":
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                           cwd=root, capture_output=True, text=True, timeout=120)
        return f"exit={r.returncode}\n{(r.stderr or r.stdout).strip()[-2500:]}"

    return f"(unknown tool: {tool})"


def build_system_prompt(root: Path) -> str:
    """SYSTEM plus the project's AGENTS.md, the way a real host loads it."""
    agents = root / "AGENTS.md"
    if agents.is_file():
        return SYSTEM + "\n\n# Project instructions (from AGENTS.md)\n\n" + agents.read_text()[:8000]
    return SYSTEM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--max-steps", type=int, default=14)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    root = Path(a.dir).resolve()
    messages = [{"role": "system", "content": build_system_prompt(root)},
                {"role": "user", "content": a.task}]
    steps, parse_fails, served_models, done = [], 0, set(), False

    for n in range(1, a.max_steps + 1):
        content, served = call_model(messages)
        served_models.add(served)
        act = extract_json(content)

        if act is None or act.get("tool") == "_error":
            parse_fails += 1
            detail = (act or {}).get("args", {}).get("detail", content[:200])
            print(f"[{n}] unparsed/error: {detail[:200]}", flush=True)
            messages.append({"role": "assistant", "content": content[:2000]})
            messages.append({"role": "user", "content":
                             "That was not a single JSON object with a 'tool' key. "
                             "Reply with exactly one JSON object."})
            if parse_fails >= 3:
                break
            continue

        tool = str(act.get("tool") or "")
        args = act.get("args") or {}
        thought = str(act.get("thought", ""))[:300]
        print(f"[{n}] {tool} {json.dumps(args)[:160]}", flush=True)

        if tool == "done":
            steps.append({"n": n, "tool": "done", "thought": thought, "args": args})
            done = True
            break

        try:
            obs = do_tool(root, tool, args)
        except Exception as e:
            obs = f"ERROR: {e}"

        steps.append({"n": n, "tool": tool, "thought": thought, "args": args,
                      "observation": obs[:1500]})
        messages.append({"role": "assistant", "content": content[:4000]})
        messages.append({"role": "user", "content": f"Result:\n{obs[:6000]}"})

    Path(a.out).write_text(json.dumps({
        "dir": str(root), "task": a.task, "steps": steps,
        "finished": done, "served_models": sorted(served_models),
    }, indent=2))
    print(f"--- finished={done} steps={len(steps)} model={sorted(served_models)}")


if __name__ == "__main__":
    main()
