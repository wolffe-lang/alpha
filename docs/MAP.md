# A map of alpha's code

## The program

- `src/wolf.pkg`: the package manifest. alpha declares the `env` and `fs` capabilities and nothing more.
- `src/alpha.lu`: the entry. It hands the arguments to `cli.run`; for `alpha check` it reads the root's files
  and the named files through `unit.load` and `unit.load_named` and asks `unit.check` for the report. It writes
  what the answer says to standard output and standard error and exits with its status. A failed write turns a
  status of 0 into 1.
- `src/cli/`: the command line. `run` is a pure function from the arguments to an `Outcome` (what to print and
  the status, or for `alpha check` the root and the files to check), so the tests call it on every machine.
- `src/unit/`: unit files, format 1 (docs/UNIT-1.md). One module, in files:
  - `toml.lu`: the reader of the TOML subset. Bytes in, a `Doc` (the top table and the tables in file order,
    each key with its line) or the first syntax error out. It knows nothing of format 1's keys.
  - `schema.lu`: the format line, every key of format 1 with its type (`specs`), the checks of tables and keys
    by name (unknown, reserved), the merge of a unit's drop-ins key by key (`Item` records each key's file and
    line, so a finding names the drop-in it came from), the type checks, the value checks and the rules across
    keys.
  - `values.lu`: the strings with a shape: unit names, durations, modes, signals, calendar times, listeners,
    environment entries, substitutions, and the edit distance behind "did you mean".
  - `check.lu`: the set. `check` takes the root's files (at installed paths) and the named files as bytes,
    assembles the units by layer and their drop-ins in order, runs the checks, then the rules across units
    (dependencies, stages, the order graph's cycles, shared addresses), and returns the report. It touches no
    file, so the tests hand it a set held in memory.
  - `load.lu`: the one part that reads the disk: the directories of UNIT-1 section 4 under a root, a level
    deep for drop-ins, and `/etc/passwd` and `/etc/group`.
  - `finding.lu`: findings, their order (units by name in byte order, then file, line and the order they were
    made in; other files by path, after), their words, and a bottom-up merge sort that takes no recursion.
- `src/graph/`: the order graph's cycles, found by Tarjan's components on an explicit stack, and for each unit
  on a cycle the shortest way round it.
- `src/toml_dump.lu` and `src/schema_dump.lu`: test tools built beside alpha. `toml-dump FILE` prints the
  reader's parse as JSON for the TOML oracle; `schema-dump` prints the schema's keys for the docs check.

Every file at the top of `src/` is an entry or a test, never a module: a module is a directory, and two entries
in one module would be two `main`s. No function value calls a top-level function (lupin, the reference
interpreter, cannot resolve one from inside a closure at this pin), so sorting is written out.

## Tests

- `src/*_test.lu`: wolf tests. Each is a program whose `main` returns 0 when every check holds and names each
  failing check on standard error. `tools/check-test` runs each on the checked machine (`wolf test`, with no
  native fallback), as a native build, and on lupin. `cli_test` checks the command line, `toml_test` the reader,
  `values_test` the shapes, and `set_test` the set on files held in memory.
- `tests/unit/<group>/<case>/`: golden cases, read by `tools/check-units` (its header describes the files of a
  case): `syntax/` the reader and the format line, `keys/` and `values/` the schema, `set/` the layers,
  drop-ins and the rules across units, `examples/` the worked examples of UNIT-1 section 8, `cli/` the command
  line. Each expected output is written from UNIT-1, never copied from alpha.
- `tools/check-units` also runs `tools/check-toml-oracle` (every fixture read by alpha and by Python's tomllib;
  where tomllib departs from TOML 1.0 itself, `tests/unit/toml-divergences.txt` says so), `tools/check-docs`
  (UNIT-1's keys are the schema's, and its findings' templates are the goldens'), and on Linux
  `tools/check-scale` (twice the units should take about twice the time).

## Tools and CI

- `tools/lib-toml.sh`, `tools/lib-toolchain.sh`, `tools/fetch-toolchain`: the pin, read and staged.
- `tools/gate.manifest` lists the gauntlet's steps; `tools/gate` runs them; the linux CI job runs the same
  commands in the same order.
- `ci/tiers.py` plans each CI run and judges it; `ci/tiers-test.py` proves the planner and the workflow's wiring.
