# alpha

alpha is the service manager for PAX: it starts, supervises, restarts and stops the system's services.

It is at the start of its development. This version checks unit files and runs them: `alpha manager` starts
the units enabled at boot, supervises and restarts them, answers on its control socket, and stops them on TERM;
`alpha status`, `start`, `stop` and the rest ask it. A unit file says what to run and when, in a strict subset of
TOML; `docs/UNIT-1.md` is the format's specification, from its syntax to the words of every message `alpha
check` prints.

```sh
alpha check                         # every unit under /usr/lib/alpha/units, /var/lib/alpha/imported and /etc/alpha/units
alpha check --root /mnt/new         # the same under another root
alpha check pkg/lobo.unit           # a package's unit, checked in its place among the installed ones
```

A unit file looks like this, here `/etc/alpha/units/lobo.unit` with a mistake on its last line:

```toml
alpha = 1
description = "lobo, the web server"
wants = ["network"]

[run]
exec = ["/bin/lobo", "-c", "/etc/lobo/lobo.conf"]
reload_signal = "HUP"
stop_signal = "QUIT"
Restart = "always"
```

`alpha check` prints each finding with its file and line, and a count:

```
alpha: /etc/alpha/units/lobo.unit:9: [run] has no key 'Restart' (keys are lowercase: did you mean 'restart'?); the unit is not loaded
alpha check: 1 unit, 1 error, 0 warnings
```

It exits 0 when it finds no error, 1 when it finds one, and 2 for a usage error.

```sh
alpha manager                       # run the units under /, until TERM
alpha manager --root /mnt/new       # the same under another root
alpha manager --kmsg                # its standard error the kernel's log: its lines carry the log's levels
alpha status lobo                   # ask the manager for one unit's status (anyone may)
alpha restart lobo                  # ask it to restart one (root only)
alpha watch --format=1              # every state a unit takes, as JSON lines, until the manager exits
```

`docs/CONTROL-1.md` specifies how the manager runs units: the states a unit passes through, what a start waits
for, how a stop proceeds, and when a unit is restarted (section 1), and the manager itself (section 2): its loop,
the lines it writes to standard error, what TERM does, and the state file that keeps a restarted manager from
starting a second copy of a service (section 2), and the control socket's protocol, version 1, and the client's
commands and exit codes (section 3). The machine of section 1 is tested on a fake clock, and the manager on
Linux in containers, row by row (`tests/linux/`). It runs services on x86-64 Linux and PAX only. A few steps of a
start go through a small C membrane until wolf has a call for each.

## Building and testing

alpha is written in [wolf](https://github.com/wolffe-lang/wolf-lang). The toolchain it is built with is pinned
in `wolf-toolchain.toml`: wolf and lupin as whole release archives checked by SHA-256, and wolf-std at a commit
checked by its tree. Nothing uses a `wolf` found on `PATH`.

```sh
tools/fetch-toolchain   # stage the pinned wolf, lupin and std into .wolf-bin/
tools/build             # alpha, and the test tools toml-dump and schema-dump, in target/native/ and target/release/
tools/build --static    # on Linux x86-64: alpha as PAX runs it, a static executable, in target/static/
tools/gate              # every check CI runs, in CI's order
```

`tools/build --static` is what a PAX image's builder runs. It links the native tier through a `cc` that adds
`-static`, so the C library needs a static archive (Ubuntu's `libc6-dev` has one); on a host without one,
`ALPHA_STATIC_IMAGE` names a container image to build in (the header of `tools/build` says how).

`tools/gate` runs the steps listed in `tools/gate.manifest`:

| step | what it checks |
|---|---|
| `python3 -I ci/tiers-test.py` | the CI planner: which jobs each kind of run owes, and the workflow's wiring |
| `tools/fetch-toolchain` | the toolchain archives match their pinned digests |
| `tools/check-fmt` | every source file is in `wolf fmt`'s layout |
| `tools/build --all` | both tiers build with warnings denied |
| `tools/check-test` | the wolf tests in `src/*_test.lu` pass on the checked machine, natively and on lupin |
| `python3 -I tools/check-units` | every golden case under `tests/unit/` gives its exact output and status on both tiers; alpha's TOML reader agrees with Python's tomllib on every fixture; `docs/UNIT-1.md` names the schema's keys and every finding's words; on Linux, twice the units take about twice the time |
| `python3 -I tools/check-membrane` | the C declarations alpha still needs are only in `src/sys/`, each names the wolf call that retires it, and their number is the ceiling, which only falls |
| `tools/check-static` | on Linux x86-64, alpha and the rows' tools build as static executables, the shape PAX runs |
| `python3 -I tools/check-linux` | on Linux x86-64, each end-to-end row in a rootless container of its own: a service's start as it sees it |
| `python3 -I tools/check-public-text --self-test` | the public-text check catches and passes its own cases |
| `python3 -I tools/check-public-text` | documents, comments and CI files, records included, hold no internal work-item ids, decision numbers, machine names or planning paths; `.github/workflows/public-text.yml` also runs it on every pull request |

The steps work on Linux (x86-64 and arm64) and macOS (arm64), the platforms the pinned archives exist for.

## CI

`.github/workflows/ci.yml` runs on pull requests, on pushes to `trunk`, every night and by hand.
`ci/tiers.py` decides which jobs a run owes. A pull request runs the planner's test and the Linux gauntlet; a
pull request that changes only prose runs nothing but the plan. A push to `trunk`, the nightly, a dispatch
with no job named, the `full-matrix` label, and any change to the workflow, the planner or the toolchain pin
run every job, macOS included. The last job, named for the tier, fails unless the run did exactly what its
tier asked. A red nightly opens an issue.

## Sources

alpha is written from published documentation and specifications: the manual pages and documented
interfaces of systemd, s6, s6-rc, runit, daemontools, launchd, illumos SMF, OpenRC and dinit, POSIX, and TOML
1.0.0's specification. No source code of any init system, process supervisor, service manager or TOML
implementation was read; Python's tomllib is run only as a black box, to compare readings.

## Licence

GPL-3.0-or-later with the wolf Training Data Permission. See `LICENSE` and `LICENSE-TRAINING-DATA`.

A planted line for the public-text check: qz97.
