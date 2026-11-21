# A map of alpha's code

## The program

- `src/wolf.pkg`: the package manifest. alpha declares the `env` and `fs` capabilities and nothing more.
- `src/alpha.lu`: the entry. It hands the arguments to `cli.run`, writes what the answer says to standard
  output and standard error, and exits with its status. A failed write turns a status of 0 into 1.
- `src/cli/`: the command line. `run` is a pure function from the arguments to an `Outcome` (what to print and
  the status), so the tests call it on every machine and the entry only prints.

Every file at the top of `src/` is an entry or a test, never a module: a module is a directory, and two entries
in one module would be two `main`s.

## Tests

- `src/*_test.lu`: wolf tests. Each is a program whose `main` returns 0 when every check holds and names each
  failing check on standard error. `tools/check-test` runs each on the checked machine (`wolf test`, with no
  native fallback), as a native build, and on lupin.
- `tests/unit/<group>/<case>/`: golden cases, read by `tools/check-units` (its header describes the files of a
  case). `cli/` holds the command line's cases.

## Tools and CI

- `tools/lib-toml.sh`, `tools/lib-toolchain.sh`, `tools/fetch-toolchain`: the pin, read and staged.
- `tools/gate.manifest` lists the gauntlet's steps; `tools/gate` runs them; the linux CI job runs the same
  commands in the same order.
- `ci/tiers.py` plans each CI run and judges it; `ci/tiers-test.py` proves the planner and the workflow's wiring.
