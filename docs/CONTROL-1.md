# alpha's control interface, version 1

This document specifies how alpha's manager runs units and how a program talks to it: the states a unit passes
through and what moves it between them (section 1), the manager that drives them with real processes (section 2,
`alpha manager`), and the control socket, its framing, its operations, the status it reports and the client
commands (the sections to come). `docs/UNIT-1.md` says what a unit file may hold; this document says what the
manager does with it.

Sections:
1. A unit's states
2. The manager

## 1. A unit's states

### 1.1 The states

| state | meaning |
|---|---|
| `inactive` | not running and not asked to run. Every unit starts here, and returns here after a stop or an end that is not restarted |
| `waiting` | asked to start, and waiting for a stage, a unit it needs, or a unit it is ordered after (1.3) |
| `starting` | its `pre` is running, or its program was started and is not yet ready by its `ready` mode |
| `running` | ready, and its main process is alive |
| `reloading` | its `reload_exec` is running; it counts as running |
| `stopping` | being stopped: its `stop_exec`, its stop signal, the rest of its group after its main process ended, or its `post_stop` |
| `done` | a one-shot (`ready = "exit"`) whose program exited 0. It stays done until it is stopped or restarted |
| `backoff` | it ended in a way its `restart` applies to, and starts again at a set time |
| `failed` | it will not start again by itself; only an explicit start or restart clears it |
| `skipped` | a `[condition]` was false when it was started |
| `invalid` | its files did not pass `alpha check`; it is never started |

A unit is **ready** when it is `running`, `reloading` or `done`. It has **settled** when it is ready, `failed`,
`skipped`, `invalid`, or `inactive` and not being started. A state other than `running`, `reloading`, `waiting`,
`starting`, `stopping` and `done` carries a **cause** (1.8), and so does `waiting`.

Each unit counts its **invocations**, one more each time its program is started (the first is 1, counted from the
manager's start), and its **restarts**, one more each time it starts again from `backoff`.

### 1.2 A start

A start is asked for by `alpha start` or `alpha restart`, by the boot (1.6), or by a unit that needs or wants it
(1.3). A unit that is `invalid` is never started; one that is ready, `waiting` or `starting` is left as it is; one
in `backoff` starts at once; one that is `stopping` starts as soon as its stop completes. An explicit start or
restart also clears `failed` and the restart counts of 1.5.

1. The unit is `waiting` while anything of 1.3 is not yet satisfied, and goes on as soon as all of it is. A unit with
   nothing to wait for goes straight to step 2 and is never shown `waiting`.
2. It becomes `starting`, and its ready timeout begins (`ready_timeout`, for every `ready` mode, `pre` included).
   The manager checks the facts of `docs/UNIT-1.md` section 5 step 5 and the unit's `[condition]` before anything
   runs: a false condition leaves it `skipped`, and a refused fact leaves it `failed`; nothing ran, so nothing is
   stopped.
3. If the unit has `pre`, it runs. An exit of 0 goes on to step 4; any other end leaves the unit `failed`.
4. The program is started (a new invocation), and the unit becomes ready by its mode:
   - `"exec"`: the program was executed;
   - `"fd:N"`: the program wrote a newline on descriptor N; if it closes N without one, the start has failed;
   - `"exit"`: the program exited 0, and the unit is `done`; any other end is a failed start;
   - `"forked"`: the first process exited 0 and the manager found the main process (`pid_file`'s, or the group's only
     process); if it finds none, or the first process ends any other way, the start has failed.
   A ready unit is `running` (or `done`).
5. **A failed start** is any of: the ready timeout passing, the program ending before it is ready, the descriptor
   closed without a newline, and the main process not found. The unit stops what is left (1.4) and then the restart
   rule (1.5) decides. **A program that cannot be executed** (the manager hears the failed exec) leaves the unit
   `failed` at once: the restart rule does not apply to it, nor to a failed `pre` or a refused fact.

A stop asked while `pre` runs ends `pre` with SIGKILL.

### 1.3 What a start waits for

- **Its stage.** A unit waits until the stage before its own has been reached (1.6): an `early` unit waits for
  nothing, a `base` unit for `early`, a `network` unit for `base`, then `time` for `network`, `multi-user` for `time`,
  and a `maintenance` unit for `base`.
- **Stages it names.** A stage named in `needs`, `wants` or `after` must have been reached.
- **The units it needs.** Every unit named in `needs` must be ready. A start pulls in each unit it needs or wants that
  is not ready and not being started, and starts it too, except a unit that is `failed` (only an explicit start
  clears that), `invalid`, or holds a `[socket]` or `[timer]` (1.7). A needed unit that is `failed`, `skipped` or
  `invalid`, or `inactive` and not being started, ends the wait: the unit becomes `inactive`, with the cause
  `needs X, which …` (1.8).
- **The units it is ordered after.** A unit is ordered after every unit it names in `needs`, `wants` and `after`, and
  after every unit whose `before` names it. Each of those that is **being started** must have settled first: one
  that is `waiting`, `starting` or in `backoff`, or `stopping` after its main process ended or its start failed (the
  restart rule has yet to decide) or towards a start. One that is not being started is not waited for.

A dependency on a unit that does not exist is not waited for (`alpha check` warns of it, or refuses the unit for a
`needs`), and neither is one on an instance (`NAME@INSTANCE`, `user@…` included): this version starts no
template's instance, and never a template itself. `conflicts` takes effect in a later version.

### 1.4 A stop

A stop is asked for by `alpha stop` or `alpha restart`, or follows the end of the main process, a failed start, or a
unit it needs stopping (1.7). It runs in this order, the unit `stopping` throughout:

1. If the stop was asked for while the main process is alive and the unit has `stop_exec`, the command runs, for at
   most `stop_timeout` (then SIGKILL to it).
2. The stop signal (`stop_signal`) goes to the main process (`stop_scope = "main"`) or to the whole group
   (`"group"`). After the main process has ended, it goes only to what is left of the group under `"group"`, and to
   nothing under `"main"`.
3. The manager waits for the main process to end (`"main"`) or for the group to be empty (`"group"`), for at most
   `stop_timeout` from the signal; then it sends SIGKILL to the main process or to the group, and waits for that.
4. If the unit has `post_stop`, it runs, for at most `stop_timeout` (then SIGKILL to it).
5. The unit takes its next state, at once when nothing in steps 1 to 4 had anything to do (it then never shows
   `stopping`): `inactive` after a stop that was asked for (`stopped by request`), the restart
   rule's choice after an end or a failed start, `waiting` or `inactive` after a needed unit's stop (1.7), and a new
   start at once when a start was asked for meanwhile (a restart).

A stop asked while the unit is `waiting` or in `backoff` leaves it `inactive` at once; one asked while it is
`stopping` makes its next state `inactive`. Stopping a `done` unit runs its `stop_exec` and `post_stop` (there is no
process to signal) and leaves it `inactive`. A stop of a unit that is `inactive`, `failed`, `skipped` or `invalid`
changes nothing.

**Reload.** A reload of a `running` unit sends `reload_signal` to its main process, which leaves it `running`, or
runs `reload_exec`, the unit `reloading` until the command ends. A unit with neither cannot be reloaded, and only a
`running` unit can.

### 1.5 The restart rule

When the main process of a `running` unit has ended, or a start has failed, and the stop that follows has completed:

- `restart` applies to the end when it is `"always"` (any end), or `"on-failure"` and the end is a failure: an exit
  other than 0, an end by a signal, or a failed start. `"never"` applies to nothing. (`ready = "exit"` makes
  `"never"` the default.)
- When it does not apply, the unit is `inactive` after an exit of 0 (cause `exited 0`) and `failed` after a failure.
- When it applies, the unit's **starts** within the last `burst_window` are counted, the start that just ended
  included; a start counts while less than `burst_window` has passed since it. When there are `burst_count` or
  more, the unit is `failed` (cause `burst: N starts within T`).
  Otherwise it is in `backoff` for `min(backoff[0] × 2^k, backoff[1])`, `k` being the number of starts from
  `backoff` since the counts were last cleared, and then starts again (1.2), counting a restart.
- **The counts are cleared** (the starts within the window, and `k`) when the unit has been `running` for
  `healthy_after` without a break, and by an explicit start or restart.

### 1.6 The boot

At its start the manager starts, as one start of 1.2, every unit that is **enabled** (its `enable` key, overridden
by a marker in `/etc/alpha/enable.d/` and then by one in `/etc/alpha/disable.d/`), is not `invalid`, holds no
`[socket]` or `[timer]` (1.7), and whose stage is `early`, `base`, `network`, `time` or `multi-user`. Those units
are **the boot's units**.

A stage is **reached** when the stage before it has been reached and every boot unit of its own stage has settled:
`early` first (nothing before it), then `base`, `network`, `time` and `multi-user` in turn. `maintenance` and
`shutdown` are not reached by this version. Until the boot has begun, no stage has been reached. The checks that
later versions add for `network` and `time` (the network up, the clock set) are not made by this one.

### 1.7 A unit it needs stops, and units this version does not run

When a ready unit stops (for any reason: a stop asked for, its end, a reload is not a stop), every unit that needs
it and is `starting`, `running` or `reloading` is stopped too (1.4), with the cause `needs X, which stopped`. When
that stop has completed, the unit is `waiting` if X is being started (1.3), and starts when X is ready; otherwise
it is `inactive` with that cause. A `waiting`
unit whose needed unit ends `failed`, `skipped` or `inactive` becomes `inactive` (1.3).

A unit that holds a `[socket]` or a `[timer]` is not started by this version: an explicit start is refused, and the
boot leaves it `inactive`.

### 1.8 Causes

A cause is one of these texts, with the values filled in. Durations are written as `docs/UNIT-1.md` writes them,
in the largest unit that divides them exactly (`30s`, `1min`, `1500ms`). A signal is written by its name in
`docs/UNIT-1.md` section 1 (`TERM`), or by its number.

| cause | when |
|---|---|
| `exited <n>` | the main process exited |
| `killed by signal <signal>` | the main process ended by a signal |
| `ready timeout (<duration>)` | the ready timeout passed |
| `closed descriptor <n> without a newline` | `ready = "fd:N"` |
| `the main process was not found: <text>` | `ready = "forked"` |
| `exec failed: <errno>` | the program could not be executed; `<errno>` is the error's name as the manager hears it (`not_found`) |
| `pre exited <n>`, `pre killed by signal <signal>` | `pre` failed |
| `burst: <n> starts within <duration>` | the burst limit |
| `stopped by request` | a stop that was asked for |
| `needs <name>, which failed`, `which stopped`, `which was skipped`, `which is not loaded`, `which is not running` | a needed unit (1.3, 1.7) |
| `condition: <text>` | a false `[condition]` |
| `refused: <text>` | a fact of `docs/UNIT-1.md` section 5 step 5 |
| `waiting for <what>` | `waiting`: the stage, unit or units it waits for, as `the stage base`, `b`, or `b and c` |
| `did not pass alpha check` | `invalid` |
| `holds a [socket] or [timer], which this version of alpha does not run` | 1.7 |

### 1.9 Order

Everything the manager does happens in an order that does not depend on the host:
- Timers due at or before the time of anything else fire first, in the order of their times, then of their units'
  names (byte order), then ready timeout, stop timeout, backoff, healthy.
- After each event or timer, the manager settles the waiting units in the byte order of their names, again and
  again until nothing changes, and says which stages that reached.

## 2. The manager

`alpha manager [--root DIR]` runs the units under DIR (by default `/`), read as `alpha check --root DIR` reads
them, by section 1, until it is told to stop. This version has no control socket: it starts the boot's units,
supervises them, and stops them on TERM.

### 2.1 Its start

1. Where it cannot start services (on a host other than x86-64 Linux or PAX) it says so on standard error and exits
   1. With a DIR that is not a directory it exits 2.
2. It reads the units. Every unit that is not a template's is one of section 1's units; one that did not pass
   `alpha check` is `invalid`.
3. On Linux it becomes the **subreaper** of its descendants, so that a process whose parent ends is given to the
   manager, which reaps it (a `forked` unit's daemon among them). Where the kernel refuses (PAX), it says so and
   watches a `forked` unit's main process by its pid instead.
4. It reads the state file an earlier manager left (2.5).
5. It listens for the end of a child, TERM, INT and HUP, and starts the boot (1.6).

### 2.2 The loop

The manager is one thread with one wait: the status pipe of each start in flight, the readiness pipe of each
`fd:N` start not yet ready, the signals of 2.1, and the machine's next timer (and, while a unit waits for its
group to empty, a tick of at most 100 ms). Each thing it hears goes to the machine of section 1 as an event, at
the time it is heard (milliseconds since the manager started), and each action the machine answers is done, in
order, before the next wait.

When a process of a unit ends, the manager tells the machine in this order: what the status pipe says (the
program was executed, or the error of its exec), what the readiness pipe has (a newline, or its end), then, if the
unit's process group has no member left, that the group is empty, and then the end itself. A process the manager
did not start but was given as the subreaper is reaped as soon as it ends; when it is a `forked` unit's main
process, its end is that unit's end.

| action | what the manager does |
|---|---|
| `check` | the unit's `[condition]` and the facts of `docs/UNIT-1.md` section 10, in that section's order, and the state file's record of the unit (2.5): the start goes on, is skipped, or is refused |
| `fork N` | the start of `docs/UNIT-1.md` section 10, as invocation N: the program leads a session and a process group of its own, whose id is its pid |
| `pre`, `stop-exec`, `post-stop`, `reload-exec` | the command, as the unit's user, with its environment and its output, as section 10 starts the program; its end is the event |
| `signal main SIG`, `signal group SIG` | SIG to the main process, or to every process of the unit's group |
| `kill main`, `kill group` | KILL to the main process, or to the group |
| `kill pre`, `kill stop-exec`, `kill post-stop` | KILL to the command and its own group |
| `find-main` | the main process of a `forked` unit: the pid in `pid_file`, which must be a running member of the unit's group, or, with no `pid_file`, the group's only process. None, or more than one with no `pid_file`, is the main process not found, with which of them in the cause |

### 2.3 What it says

The manager writes to its standard error, one line each, beginning `alpha: `:

- at its start, `alpha: manager VERSION pid P root DIR`, then `alpha: subreaper on` or `alpha: subreaper refused
  (errno N): ...`;
- every line of the machine's transcript, as `alpha: @T LINE`, T in milliseconds since the manager started: the
  events it was told (`> exec-ok a`), the states (`a: starting -> running`), the actions (`a: do fork 1`), the
  timers and the stages reached;
- what it did beside them: `alpha: @T U: pid P` (a program started), `alpha: @T U: KIND pid P` (a command beside
  it), `alpha: @T U: main pid P` (a `forked` unit's main process found), `alpha: @T reaped P (exited N)` (a process
  given to it that was no unit's main process), and a signal it could not send;
- `alpha: @T stopping every unit (TERM)`, and at its end `alpha: @T exit 0`.

A service's output (`stdout = "log"`, the default, until logs exist) goes to the same stream, as the service writes
it. These lines are for people and for the tests; the control socket of the sections to come is what a program
relies on.

### 2.4 TERM, INT and HUP

TERM or INT stops every unit (1.4) but those with `shutdown = "leave"`, as a stop of each in the byte order of the
units' names. When none of the others is `waiting`, `starting`, `running`, `reloading`, `stopping`, `done` or in
`backoff`, and no command of 2.2 runs, the manager writes its state file and exits 0, leaving the units it left
running. A second TERM changes nothing. HUP is ignored, said once: rereading the units comes in a later version.

### 2.5 The state file

`DIR/run/alpha/state` holds one line for each unit with a process: `NAME INVOCATION MAINPID PGID` (MAINPID 0 when
the main process has ended and the group has not). The manager rewrites it whenever it changes.

At its start the manager reads the file an earlier manager left. A unit whose recorded process group still has a
member is not started again: its check is refused, with the cause `refused: its process group P from an earlier
manager still has members`. A manager started again after a crash, or after a TERM that left units running,
therefore never runs a second copy of a service; taking the old processes back comes in a later version. Such a
record stays in the file while its group has a member and the manager runs nothing of that unit.
