# alpha's control interface, version 1

This document specifies how alpha's manager runs units and how a program talks to it: the states a unit passes
through and what moves it between them (section 1, which `alpha manager` implements), and the control socket, its
framing, its operations, the status it reports and the client commands (the sections to come). `docs/UNIT-1.md`
says what a unit file may hold; this document says what the manager does with it.

Sections:
1. A unit's states

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
  after every unit whose `before` names it. Each of those that is being started (`waiting`, `starting`, `stopping`
  towards a start, or `backoff`) must have settled first. One that is not being started is not waited for.

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
that stop has completed, the unit is `waiting` if X is being started again (`waiting`, `starting`, `backoff`, or
`stopping` towards a start), and starts when X is ready; otherwise it is `inactive` with that cause. A `waiting`
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
