# alpha

alpha is the service manager for PAX: it starts, supervises, restarts and stops the system's services.

It is at the start of its development. The program built here answers `--help` and `--version` and does
nothing else yet. The unit file format and `alpha check`, which reads and validates unit files, come next.

## Building and testing

alpha is written in [wolf](https://github.com/wolffe-lang/wolf-lang). The toolchain it is built with is pinned
in `wolf-toolchain.toml`: wolf and lupin as whole release archives checked by SHA-256, and wolf-std at a commit
checked by its tree. Nothing uses a `wolf` found on `PATH`.

```sh
tools/fetch-toolchain   # stage the pinned wolf, lupin and std into .wolf-bin/
tools/build             # target/native/alpha and target/release/alpha
tools/gate              # every check CI runs, in CI's order
```

`tools/gate` runs the steps listed in `tools/gate.manifest`:

| step | what it checks |
|---|---|
| `python3 -I ci/tiers-test.py` | the CI planner: which jobs each kind of run owes, and the workflow's wiring |
| `tools/fetch-toolchain` | the toolchain archives match their pinned digests |
| `tools/check-fmt` | every source file is in `wolf fmt`'s layout |
| `tools/build --all` | both tiers build with warnings denied |
| `tools/check-test` | the wolf tests in `src/*_test.lu` pass on the checked machine, natively and on lupin |
| `python3 -I tools/check-units` | every golden case under `tests/unit/` gives its exact output and status on both tiers |
| `python3 -I tools/check-public-text` | tracked files hold no private host, lane or planning names |

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
interfaces of systemd, s6, s6-rc, runit, daemontools, launchd, illumos SMF, OpenRC and dinit, and POSIX. No
source code of any init system, process supervisor or service manager was read.

## Licence

GPL-3.0-or-later with the wolf Training Data Permission. See `LICENSE` and `LICENSE-TRAINING-DATA`.
