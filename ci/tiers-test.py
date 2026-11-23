#!/usr/bin/env python3
# Adapted from wolffe-lang/scent ea1b5b19 ci/tiers-test.py; own code.
"""ci/tiers-test.py: the planner's own proof. python3 only, no network.

  T1  the tiers by event: a trunk push, the nightly, a dispatch with no
      jobs and the `full-matrix` label are full; another label's `labeled`
      event is a noop; a dispatch naming jobs is partial, and one naming a
      job the workflow lacks is refused.
  T2  the pull-request tiers by path: code, tests and tools are pr
      (plan-test, linux); prose alone is a noop; prose beside code is pr.
  T3  full wins: the workflow, the planner and the pin are full, so are a
      path no rule names, changed paths that cannot be read, and none.
  T4  the wiring of .github/workflows/ci.yml: every job but `plan` needs it
      and runs only when the plan names it; `tier` needs every job, runs
      unless cancelled and calls the verdict; pull-request runs alone cancel
      in progress; the trunk push, the nightly, the label and the dispatch
      input are there; macos is no pull-request job; Linux runners are
      ubuntu-24.04 and none is ubuntu-latest.
  T5  the gauntlet: the linux job's commands are exactly
      tools/gate.manifest's steps but plan-test, in order; the plan-test
      job runs the manifest's plan-test command; macos runs a subset of the
      linux commands, in the same order.
  T6  the verdict: green for a full, a pr, a noop and a partial run; red for
      a chosen job failed or skipped, a job that ran unasked, a failed plan,
      a plan with no tier, and a full run that chose less.
  T7  the plan's log carries the `tiers: event=... action=... label=...
      labels=...` line, which is how a run's event and labels are read later.
  T8  ci/nightly-red.sh against a stand-in `gh`: no open issue opens one; an
      open one is commented on; a label that exists is no failure; the script
      refuses without its environment; the nightly-red job runs after the
      verdict, on a failed schedule only.

Prints `tiers-test: PASS what` or `tiers-test: FAIL what` for each check.
Exit 0 when every check passes, 1 otherwise.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "ci", "tiers.py")
WF_PATH = os.path.join(ROOT, ".github", "workflows", "ci.yml")
KEYS = ("EVENT", "ACTION", "LABEL", "LABELS", "HEAD_SHA", "IN_JOBS", "NEEDS")
ALL = ["plan-test", "linux", "macos"]
PR = ["plan-test", "linux"]
fails = 0


def say(ok, what):
    global fails
    print("tiers-test: %s %s" % ("PASS" if ok else "FAIL", what))
    fails += not ok


def env(**more):
    e = {k: v for k, v in os.environ.items() if k not in KEYS}
    e.update(more)
    return e


def run_plan(paths=None, **kw):
    args = [sys.executable, "-I", PLAN, "plan", "--json"]
    for k, v in kw.items():
        args += ["--" + k.replace("_", "-"), v]
    if paths is not None:
        args += ["--paths-from", "-"]
    try:
        r = subprocess.run(args, input="\n".join(paths or []) + "\n", capture_output=True, text=True, env=env())
    except OSError as e:
        return {"tier": "ERROR %s" % e, "jobs": [], "log": ""}
    if r.returncode != 0:
        return {"tier": "ERROR %d" % r.returncode, "jobs": [], "log": r.stderr}
    out = json.loads(r.stdout)
    out["log"] = r.stderr
    return out


def expect(what, got, tier, jobs):
    say(got["tier"] == tier and got["jobs"] == jobs,
        "%s: tier %s %s (got %s %s)" % (what, tier, " ".join(jobs) or "-", got["tier"], " ".join(got["jobs"]) or "-"))


def verdict(needs):
    r = subprocess.run([sys.executable, "-I", PLAN, "verdict"], capture_output=True, text=True,
                       env=env(NEEDS=json.dumps(needs)))
    return r.returncode


def needs_for(tier, chosen, results=None, plan_result="success"):
    results = results or {}
    n = {"plan": {"result": plan_result, "outputs": {"tier": tier, "jobs": json.dumps(chosen)}}}
    for j in ALL:
        n[j] = {"result": results.get(j, "success" if j in chosen else "skipped")}
    return n


def workflow():
    try:
        return open(WF_PATH, encoding="utf-8").read()
    except OSError:
        return ""


def job_blocks(text):
    """{job id: its lines}, from the workflow's `jobs:` mapping."""
    jobs, cur, inside = {}, None, False
    for line in text.splitlines():
        if re.match(r"^jobs:\s*$", line):
            inside = True
            continue
        if inside and re.match(r"^\S", line):
            inside = False
        if not inside:
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if m:
            cur = m.group(1)
            jobs[cur] = []
        elif cur:
            jobs[cur].append(line)
    return jobs


def runs(lines):
    return [m.group(1).strip() for m in (re.match(r"^\s+(?:- )?run: (.+)$", l) for l in lines) if m]


def manifest_steps():
    steps = []
    try:
        text = open(os.path.join(ROOT, "tools", "gate.manifest"), encoding="utf-8").read()
    except OSError:
        return steps
    for raw in text.splitlines():
        words = shlex.split(raw, comments=True)
        if words and words[0] == "step" and "--" in words:
            steps.append((words[1], " ".join(words[words.index("--") + 1:])))
    return steps


def t1():
    expect("T1 trunk push", run_plan(event="push"), "full", ALL)
    expect("T1 nightly", run_plan(event="schedule"), "full", ALL)
    expect("T1 dispatch with no jobs", run_plan(event="workflow_dispatch"), "full", ALL)
    expect("T1 full-matrix label", run_plan(["src/alpha.lu"], event="pull_request", action="labeled",
                                            label="full-matrix", labels="full-matrix"), "full", ALL)
    expect("T1 full-matrix on a later push", run_plan(["src/alpha.lu"], event="pull_request", action="synchronize",
                                                      labels="full-matrix"), "full", ALL)
    expect("T1 another label", run_plan(["src/alpha.lu"], event="pull_request", action="labeled",
                                        label="documentation", labels="documentation"), "noop", [])
    expect("T1 dispatch naming linux", run_plan(event="workflow_dispatch", jobs="linux"), "partial", ["linux"])
    expect("T1 dispatch naming two", run_plan(event="workflow_dispatch", jobs="macos plan-test"), "partial",
           ["plan-test", "macos"])
    got = run_plan(event="workflow_dispatch", jobs="windows")
    say(got["tier"].startswith("ERROR 2") and "windows" in got.get("log", ""),
        "T1 dispatch naming a job the workflow lacks is refused by name (got %s)" % got["tier"])


def t2():
    pr = dict(event="pull_request", action="opened")
    expect("T2 a source file", run_plan(["src/alpha.lu"], **pr), "pr", PR)
    expect("T2 a golden case", run_plan(["tests/unit/cli/version/stdout"], **pr), "pr", PR)
    expect("T2 a tool", run_plan(["tools/check-units"], **pr), "pr", PR)
    expect("T2 the README alone", run_plan(["README.md"], **pr), "noop", [])
    expect("T2 docs and the CHANGELOG", run_plan(["docs/UNIT-1.md", "CHANGELOG.md"], **pr), "noop", [])
    expect("T2 prose beside code", run_plan(["README.md", "src/cli/cli.lu"], **pr), "pr", PR)


def t3():
    pr = dict(event="pull_request", action="synchronize")
    expect("T3 the workflow", run_plan(["src/alpha.lu", ".github/workflows/ci.yml"], **pr), "full", ALL)
    expect("T3 the planner", run_plan(["ci/tiers.py"], **pr), "full", ALL)
    expect("T3 the pin", run_plan(["wolf-toolchain.toml"], **pr), "full", ALL)
    expect("T3 a path no rule names", run_plan(["src/alpha.lu", "Makefile"], **pr), "full", ALL)
    expect("T3 paths that cannot be read", run_plan(**pr), "full", ALL)
    expect("T3 no changed path", run_plan([], **pr), "full", ALL)


def t4():
    text = workflow()
    say(bool(text), "T4 the workflow exists")
    if not text:
        return
    jobs = job_blocks(text)
    say(set(jobs) == {"plan", "plan-test", "linux", "macos", "tier", "nightly-red"},
        "T4 the jobs are plan, plan-test, linux, macos, tier, nightly-red (got %s)" % " ".join(jobs))
    for j in ALL:
        body = "\n".join(jobs.get(j, []))
        say("    needs: plan" in body, "T4 %s needs plan" % j)
        say("    if: contains(fromJSON(needs.plan.outputs.jobs || '[]'), '%s')" % j in body,
            "T4 %s runs only when the plan names it" % j)
    tier = "\n".join(jobs.get("tier", []))
    say("    needs: [plan, plan-test, linux, macos]" in tier, "T4 tier needs every job")
    say("    if: ${{ !cancelled() }}" in tier, "T4 tier runs unless cancelled")
    say("ci/tiers.py verdict" in tier and "NEEDS: ${{ toJSON(needs) }}" in tier, "T4 tier calls the verdict")
    say("    name: tier ${{ needs.plan.outputs.tier || 'unplanned' }}" in tier, "T4 tier is named for its tier")
    say("  cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text,
        "T4 only pull-request runs cancel in progress")
    say(re.search(r"^  push:\n    branches: \[trunk\]\n", text, re.M) is not None, "T4 trunk pushes run")
    say(re.search(r"^  push:\n    branches: \[trunk\]\n    paths", text, re.M) is None, "T4 no path filter on trunk pushes")
    say(re.search(r"^    - cron: '\d+ \d+ \* \* \*'$", text, re.M) is not None, "T4 a nightly")
    say("types: [opened, synchronize, reopened, labeled]" in text, "T4 pull requests, labels included")
    say(re.search(r"^  workflow_dispatch:\n    inputs:\n      jobs:", text, re.M) is not None, "T4 the dispatch input")
    plan = "\n".join(jobs.get("plan", []))
    say("python3 -I ci/tiers.py plan --merge --github-output" in plan, "T4 the plan reads the merge's paths")
    say("fetch-depth: 2" in plan, "T4 the plan's checkout holds the merge's parents")
    say("ubuntu-latest" not in text, "T4 no job runs on ubuntu-latest")
    for j in ("plan", "plan-test", "linux", "tier", "nightly-red"):
        say("    runs-on: ubuntu-24.04" in "\n".join(jobs.get(j, [])), "T4 %s runs on ubuntu-24.04" % j)
    say("    runs-on: macos-15" in "\n".join(jobs.get("macos", [])), "T4 macos runs on macos-15")
    for j in jobs:
        say(re.search(r"^    timeout-minutes: \d+$", "\n".join(jobs[j]), re.M) is not None, "T4 %s has a time limit" % j)
    src = open(PLAN, encoding="utf-8").read() if os.path.exists(PLAN) else ""
    say('PR_JOBS = ("plan-test", "linux")' in src, "T4 macos is no pull-request job")


def t5():
    text = workflow()
    jobs = job_blocks(text)
    steps = manifest_steps()
    say(bool(steps) and steps[0][0] == "plan-test", "T5 the manifest's first step is plan-test")
    want = [cmd for name, cmd in steps if name != "plan-test"]
    got = runs(jobs.get("linux", []))
    say(got == want, "T5 the linux job runs the manifest's steps in order (got %s)" % got)
    pt = [cmd for name, cmd in steps if name == "plan-test"]
    say(runs(jobs.get("plan-test", [])) == pt, "T5 the plan-test job runs the manifest's plan-test")
    mac = runs(jobs.get("macos", []))
    it = iter(want)
    say(bool(mac) and all(c in it for c in mac), "T5 macos runs linux's commands, a subset in order (got %s)" % mac)


def t6():
    # The verdict's own red is exit 1; a planner that cannot run exits 2 and
    # proves nothing.
    say(verdict(needs_for("full", ALL)) == 0, "T6 a green full run")
    say(verdict(needs_for("pr", PR)) == 0, "T6 a green pr run")
    say(verdict(needs_for("noop", [])) == 0, "T6 a noop run")
    say(verdict(needs_for("partial", ["linux"])) == 0, "T6 a green partial run")
    say(verdict(needs_for("full", ALL, {"macos": "failure"})) == 1, "T6 red: a chosen job failed")
    say(verdict(needs_for("pr", PR, {"linux": "skipped"})) == 1, "T6 red: a chosen job skipped")
    say(verdict(needs_for("pr", PR, {"macos": "success"})) == 1, "T6 red: a job ran unasked")
    say(verdict(needs_for("full", ALL, plan_result="failure")) == 1, "T6 red: the plan failed")
    say(verdict(needs_for("", ALL)) == 1, "T6 red: the plan named no tier")
    say(verdict(needs_for("full", PR)) == 1, "T6 red: a full run that chose less")
    say(verdict(needs_for("partial", [])) == 1, "T6 red: a partial run that chose nothing")


def t7():
    got = run_plan(["src/alpha.lu"], event="pull_request", action="opened")
    say("tiers: event=pull_request action=opened label=- labels=-" in got.get("log", ""),
        "T7 the plan logs the event, action and labels")
    got = run_plan(["src/alpha.lu"], event="pull_request", action="labeled", label="full-matrix", labels="full-matrix")
    say("tiers: event=pull_request action=labeled label=full-matrix labels=full-matrix" in got.get("log", ""),
        "T7 the plan logs a label event")


def t8():
    script = os.path.join(ROOT, "ci", "nightly-red.sh")
    say(os.access(script, os.X_OK), "T8 ci/nightly-red.sh is executable")
    if not os.access(script, os.X_OK):
        return
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, "gh.log")
        stub = os.path.join(d, "gh")
        with open(stub, "w") as f:
            f.write("#!/bin/sh\necho \"$*\" >>\"%s\"\n"
                    "case \"$1 $2\" in\n"
                    "\"label create\") [ -n \"$GH_LABEL_EXISTS\" ] && exit 1; exit 0 ;;\n"
                    "\"issue list\") printf '%%s' \"$GH_OPEN\" ;;\n"
                    "esac\nexit 0\n" % log)
        os.chmod(stub, 0o755)
        base = env(PATH=d + os.pathsep + os.environ.get("PATH", ""), REPO="o/r", WORKFLOW="ci", RUN_URL="https://x/runs/1")

        def go(**more):
            if os.path.exists(log):
                os.remove(log)
            e = dict(base)
            e.update(more)
            r = subprocess.run([script], capture_output=True, text=True, env=e)
            calls = open(log).read() if os.path.exists(log) else ""
            return r.returncode, calls

        rc, calls = go(GH_OPEN="")
        say(rc == 0 and "issue create" in calls and "nightly-red" in calls, "T8 no open issue: one is opened")
        rc, calls = go(GH_OPEN="7")
        say(rc == 0 and "issue comment 7" in calls and "issue create" not in calls, "T8 an open issue: commented on")
        rc, calls = go(GH_OPEN="", GH_LABEL_EXISTS="1")
        say(rc == 0 and "issue create" in calls, "T8 a label that exists is no failure")
        e = dict(base)
        del e["REPO"]
        r = subprocess.run([script], capture_output=True, text=True, env=e)
        say(r.returncode != 0, "T8 the script refuses without REPO")
        # T8, what the reporter writes is public: the issue's title and body, a comment,
        # the label's description. The plain rule holds in every run: no lane, ruling,
        # crawl or sprint word and no internal tag (two letters and two or three digits). A
        # local record also passes PUBLIC_TEXT_REFUSE, a file of further words kept outside
        # this repository; a word from that file is reported by its line number, never spelt.
        PLAIN = re.compile(r"\b(?:lanes?|rulings?|crawls?|sprints?)\b|\b[a-z]{2}\d{2,3}[a-z]?\b", re.I)
        LISTED = []
        if os.environ.get("PUBLIC_TEXT_REFUSE"):
            with open(os.environ["PUBLIC_TEXT_REFUSE"], encoding="utf-8") as fh:
                LISTED = [(n, re.compile(r"(?<![A-Za-z0-9_-])%s(?![A-Za-z0-9_-])" % re.escape(w.strip()), re.I))
                          for n, w in enumerate(fh, 1) if w.strip() and not w.startswith("#")]


        def _log_lines(x):
            return x.splitlines() if isinstance(x, str) else list(x)


        written = "\n".join(c for e in ("", "41") for c in _log_lines(go(GH_OPEN=e)[1]) if not c.startswith("issue list"))
        said = sorted({m.group(0) for m in PLAIN.finditer(written)}) + ["listed word %d" % n for n, rx in LISTED if rx.search(written)]
        say(bool(written) and not said, "T8 nothing the reporter writes in public carries an internal word (%s)%s" % (
            "the plain rule and %d listed words" % len(LISTED) if LISTED else "the plain rule", ": " + ", ".join(said) if said else ""))
    jobs = job_blocks(workflow())
    nr = "\n".join(jobs.get("nightly-red", []))
    say("    needs: tier" in nr and "    if: ${{ failure() && github.event_name == 'schedule' }}" in nr
        and "ci/nightly-red.sh" in nr and "issues: write" in nr,
        "T8 nightly-red runs after the verdict on a failed schedule, with issues: write")


def main():
    say(os.path.exists(PLAN), "the planner ci/tiers.py exists")
    for t in (t1, t2, t3, t4, t5, t6, t7, t8):
        t()
    print("tiers-test: %d check(s) failed" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
