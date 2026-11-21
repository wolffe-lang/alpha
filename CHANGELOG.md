# Changelog

## Unreleased

- `alpha manager [--root DIR]`, specified in `docs/CONTROL-1.md` section 2: it starts the boot's units in their
  order, waits for each one's readiness (`exec`, `fd:N`, `exit`, `forked`), stops a unit by its process group or
  its main process with its `stop_exec`, signal, timeout and `post_stop`, restarts it by its rule, reaps the
  orphans it adopts as the subreaper, and on TERM stops every unit but those left running and exits. A state file
  keeps a manager started again from running a second copy of a service. Its lines go to standard error; it has no
  control socket yet. Tested on Linux x86-64 in containers, timing rows on one CPU as well, and a thousand
  restarts in a row that hold its memory.
- A service's start, as UNIT-1 section 10 now specifies it: the conditions and the facts checked first, then a
  fork, the child set up in order (its own session, default dispositions and an empty mask, limits,
  `no_new_privs`, umask, directory, ids last, the descriptors and an exact environment), and the exec, whose
  failure the manager hears by name. Tested on Linux x86-64 in containers.
- A small C membrane for the steps wolf has no call for yet, held by a gate that lets its number only fall, and a
  check that alpha builds as the static executable PAX runs.
- `docs/CONTROL-1.md` begins: a unit's states, what a start waits for (stages, the units it needs, the units it
  is ordered after), a stop in its steps, the restart rule with its backoff and burst limit, the boot's units, and
  the causes a unit's state carries. The machine that implements it is tested on a fake clock.
- Unit format 1, specified in `docs/UNIT-1.md`: a strict subset of TOML 1.0, one file per unit, every key with
  its type and default, the keys reserved for later and refused by name, the directories, overrides and
  drop-ins, the stages, and the words of every finding.
- `alpha check [--root DIR] [FILE.unit ...]` reads and checks a root's units, or a package's units in their
  place among them, and prints every finding with its file and line, and a count.
- The repository's tools and CI: the toolchain pinned by digest (wolf 0.2.40, lupin 0.1.62, wolf-std
  `c339a471`), builds on both of wolf's compiled tiers, wolf tests on three machines, golden cases compared
  byte for byte, a public-text check, and a tiered workflow on Linux and macOS.
- `alpha --help` and `alpha --version`; any other word is a usage error, named on standard error with exit
  status 2.
