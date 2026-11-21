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
- `src/machine/`: the unit state machine of `docs/CONTROL-1.md` section 1, for a whole set, pure: time comes in
  with each event and what the manager must do comes out as `do` lines, in order. `spec.lu` is what the machine
  needs of a unit, with UNIT-1's defaults, read from `unit.load_set`; `machine.lu` holds the states, starts as jobs
  (needs, wants, after, before, stages as names), stops, the restart rule with its backoff and burst, reload, and a
  needed unit's stop. It reads no clock and touches no process, so the same code runs on the checked machine, on
  lupin and natively, and the manager drives it with real events (`feed`, `advance` for a timer, `drain` for
  what it said). The texts it keeps (a unit's cause) are bytes it owns, refilled in place, so the manager can run
  each turn in a region of its own.
- `src/supervise/`: the manager (CONTROL-1 section 2) and a service's start (UNIT-1 section 10). `start.lu`:
  `prepare` checks the unit's conditions and the facts that can change between checks and works out the plan
  (ids and groups from the root's `/etc/passwd` and `/etc/group`, the exact environment, the limits, the
  descriptors); `start` forks, sets the child up in UNIT-1's order and execs, and the exec's failure comes back
  over a pipe the exec itself closes. `manager.lu`: one thread and one wait (the start's pipes, the signals, the
  machine's next timer); each event goes to the machine and each action it answers is done before the next wait;
  the subreaper's orphans are reaped beside std's own children; the state file guards against a second copy.
  Each turn runs in a region, and what outlives it holds only plain values (a plan is made again where it is
  used), so a manager that restarts a service for months holds the same memory. `socket.lu`: the control socket
  (CONTROL-1 section 3), its listener and up to 64 clients in the same wait, each client's unsent and unfinished
  lines in bytes the manager owns, its bounds and the user id the kernel gives at accept. Linux and PAX only.
- `src/control/`: the control protocol, version 1, with no socket in it: the handshake, a request read from its
  line, the refusals and their words, a unit's status and a watch's events as JSON lines, and the answer to a
  request against the machine (its start, stop, restart or reload given to `machine.request`, which answers the
  machine's refusal word). Pure, like the machine, so its goldens run on every tier.
- `src/client/`: the client's commands (`alpha status`, `list`, `watch`, `start`, `stop`, `restart`, `reload`):
  connect, say the version, send one request, print the reply as text or as the protocol's objects.
- `src/sys/`: the C membrane, the steps of a start wolf has no call for yet (the mask, `no_new_privs`, limits,
  the child subreaper and its orphans): hand-declared glibc functions for x86-64 Linux under
  `#[cfg(target = ...)]`, with stubs answering "unsupported" on every other target. Each declaration names the
  wolf call that retires it, and `src/sys/CEILING` holds their number, which only falls (`tools/check-membrane`).
- `src/probe.lu`, `src/talk.lu` and `src/rowrun.lu`: the Linux rows' tools. `probe` is every service and command a
  row needs, its mode picked by its arguments (`probe report` prints the state it was started in from
  `/proc/self`); `talk` is the control socket's other end for the rows (raw lines, a flood, ten thousand status
  requests) and a service that hears HUP, a tool of its own so that the probe never links the event loop and the
  signal hub whose descriptors would be in its report; `rowrun` drives one row inside its container: it starts
  `alpha manager`, reads its lines, runs the client and `talk` (as another user where the row says), sends it
  TERM, and prints the manager's lines grouped by unit and the facts it checks. `tools/check-static` builds them,
  with alpha, statically for the containers.
- `src/toml_dump.lu`, `src/schema_dump.lu`, `src/machine_run.lu` and `src/control_run.lu`: test tools built
  beside alpha. `toml-dump FILE` prints the reader's parse as JSON for the TOML oracle; `schema-dump` prints the
  schema's keys for the docs check; `machine-run ROOT SCRIPT` runs the machine over a fixture root and a script
  of timed events and prints its transcript (its header gives both formats); `control-run ROOT SCRIPT` runs the
  control protocol over the machine, from a script of events and client lines, and prints every reply and event.

Every file at the top of `src/` is an entry or a test, never a module: a module is a directory, and two entries
in one module would be two `main`s. No function value calls a top-level function (lupin, the reference
interpreter, cannot resolve one from inside a closure at this pin), so sorting is written out.

## Tests

- `src/*_test.lu`: wolf tests. Each is a program whose `main` returns 0 when every check holds and names each
  failing check on standard error. `tools/check-test` runs each on the checked machine (`wolf test`, with no
  native fallback), as a native build, and on lupin. `cli_test` checks the command line, `toml_test` the reader,
  `values_test` the shapes, `set_test` the set on files held in memory, and `machine_test` the machine's
  arithmetic, two scripts and the calls a manager makes.
- `tests/unit/<group>/<case>/`: golden cases, read by `tools/check-units` (its header describes the files of a
  case): `syntax/` the reader and the format line, `keys/` and `values/` the schema, `set/` the layers,
  drop-ins and the rules across units, `examples/` the worked examples of UNIT-1 section 8, `cli/` the command
  line, `machine/` the state machine on a fake clock (each case a fixture root, a `script` and the transcript,
  run by `machine-run`), and `control/` the control protocol (each case a fixture root, a `script` of events and
  client lines, and the replies, run by `control-run`). Each expected output is written from UNIT-1 or CONTROL-1,
  never copied from alpha.
- `tests/linux/<row>/`: the Linux end-to-end rows, each run by `tools/check-linux` in a rootless container of its
  own (its header gives the container's shape), with the static alpha and test tools mounted; Linux x86-64 only.
  A row whose windows are timed runs twice, the second time pinned to one CPU.
- `tests/membrane/<case>/`: small trees the membrane gate must judge as each case's `expect` says, so the gate is
  seen refusing before it is trusted.
- `tools/check-units` also runs `tools/check-toml-oracle` (every fixture read by alpha and by Python's tomllib;
  where tomllib departs from TOML 1.0 itself, `tests/unit/toml-divergences.txt` says so), `tools/check-docs`
  (UNIT-1's keys are the schema's, and its findings' templates are the goldens'), and on Linux
  `tools/check-scale` (twice the units should take about twice the time).

## Tools and CI

- `tools/lib-toml.sh`, `tools/lib-toolchain.sh`, `tools/fetch-toolchain`: the pin, read and staged.
- `tools/gate.manifest` lists the gauntlet's steps; `tools/gate` runs them; the linux CI job runs the same
  commands in the same order.
- `ci/tiers.py` plans each CI run and judges it; `ci/tiers-test.py` proves the planner and the workflow's wiring.
