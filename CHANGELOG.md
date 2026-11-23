# Changelog

## Unreleased

- `tools/check-public-text` is now the check every repository of the organization carries, pinned by digest in
  `tools/public-text.conf`: documents, code comments and CI files (records too, here) hold no internal work-item
  ids, decision numbers, machine names or planning paths, and `--self-test` holds it to its own cases.
  `.github/workflows/public-text.yml` runs both on every pull request, with no label.
- `alpha manager --kmsg`, for a manager whose standard error is the kernel's log: each of its lines begins with a
  record's facility and level, `<28>` (daemon, warning) when a unit failed or the manager could not do something,
  `<30>` (daemon, information) otherwise, so a console that shows warnings and worse shows only those. A service's
  own output is left as it writes it.
- The manager makes its waiter once and keeps it, so a turn of its loop opens nothing to wait with: a manager
  whose descriptors run out (or, on PAX, whose machine has no epoll object left) goes on supervising its units
  instead of exiting. A client it cannot accept waits in the socket's queue; the manager says so once and takes
  the socket out of the wait for 100 ms at a time. A host that gives it no waiter at its start stops it there,
  before any unit has started. Tested on Linux with the manager's descriptor table filled and freed.
- `tools/build --static` builds alpha as the static executable PAX runs (Linux x86-64), into
  `target/static/alpha`, or the programs it names; `tools/check-static` builds through it. It is the entry a PAX
  image's builder calls.
- The control socket's two other bounds tested on Linux: the 64th connection of a user other than root is
  refused while root's place stays free, and a client with more than 16 requests unanswered is answered busy.
  A reply partly sent is now finished before `busy`, so a client never reads half a line.
- The control socket, specified in `docs/CONTROL-1.md` section 3: JSON lines over a Unix stream socket, version 1
  with a handshake, a fixed list of refusal words, a unit's status with every field version 1 will ever have, and
  a watch of every state; anyone may read, only root may change a unit, by the user id the kernel gives. The
  client: `alpha status [UNIT]`, `list`, `watch` (with `--format=1` for the protocol's objects), `start`, `stop`,
  `restart` and `reload`, exiting 0, 1 when refused, 2 for a usage error and 3 when no manager answers. A second
  manager on the same root refuses to start. Tested on Linux x86-64 in containers, ten thousand status requests
  beside a thousand restarts holding the manager's memory.
- `alpha manager [--root DIR]`, specified in `docs/CONTROL-1.md` section 2: it starts the boot's units in their
  order, waits for each one's readiness (`exec`, `fd:N`, `exit`, `forked`), stops a unit by its process group or
  its main process with its `stop_exec`, signal, timeout and `post_stop`, restarts it by its rule, reaps the
  orphans it adopts as the subreaper, and on TERM stops every unit but those left running and exits. A state file
  keeps a manager started again from running a second copy of a service. Its lines go to standard error. Tested on Linux x86-64 in containers, timing rows on one CPU as well, and a thousand
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
