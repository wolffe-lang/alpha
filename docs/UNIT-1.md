# alpha unit files, format 1

This is the specification of the files that tell alpha what to run: what a unit file may hold, what each key
means, where alpha looks for unit files, how it checks them, and the exact words of every finding `alpha
check` prints. `alpha check` implements sections 1 to 5 and 9; the manager that starts and stops services
implements the rest as it is built.

Sections:
1. Files and syntax
2. Every key of format 1
3. Keys reserved for later
4. Directories, overrides and enablement
5. Validation and `alpha check`
6. The compatibility alpha promises
7. systemd's units, mapped
8. Worked examples
9. Findings
10. What a start does

## 1. Files and syntax

**One file per unit**, named `NAME.unit`. `NAME` is 1 to 64 bytes of `a-z`, `0-9`, `.`, `_` and `-`, starting
with a letter or a digit. The unit's name is the file's name without `.unit`. A unit holds a service (`[run]`), a
socket trigger (`[socket]`) or a timer trigger (`[timer]`) with its service, or a timer that starts another
unit. A service and the thing that starts it are read together, in one file.

**Templates.** `NAME@.unit` is a template, and `NAME@INSTANCE` is a unit made from it, `INSTANCE` being 1 to 64
bytes of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`. alpha's own per-user managers are the built-in template
`user@` (`user@1000`, for example); no file may be named `user@.unit`.

**Syntax: a strict subset of TOML 1.0** (the specification at toml.io, version 1.0.0). Any TOML reader reads a
unit file and means the same by it; alpha refuses some files that are TOML (section 9 says which, by name):
- UTF-8 with no byte-order mark; `#` comments; lines end in LF or CRLF; spaces and tabs as TOML allows them.
- Keys at the top, then tables. The tables of format 1 are `[run]`, `[socket]`, `[timer]`, `[condition]` and
  `[limits]`, and the reserved tables of section 3. No other table, no table inside a table, no dotted key, no
  quoted key, no array of tables, no inline table.
- Values: basic strings (`"…"` with TOML's escapes), literal strings (`'…'`), integers written as plain decimal
  digits (`0`, or digits not starting with `0`) that fit in 64 bits, `true` and `false`, and arrays of strings on
  one line or several, with comments and a trailing comma allowed. No floats, dates or times, multi-line
  strings, signs, underscores, or hexadecimal, octal and binary integers.
- A key appears once in its table, and a table once in its file.
- Keys are written in lower case with `_`. Bare keys may also hold `-`, so a vendor's `x-` keys read.

**The format line.** The first key of every unit file and every drop-in is `alpha = 1`; comments and blank lines
may come before it. A file without it, with a key before it, or with another number is refused by name
("format 2 is not known to this alpha").

**Typed by key, written as strings:**
- a *duration* is one or more terms separated by single spaces, each a decimal integer and a unit (`ms`, `s`,
  `min`, `h`, `d`): `"90s"`, `"1h 30min"`, `"0s"`;
- a *mode* is 3 or 4 octal digits: `"0640"`;
- a *signal* is a name without `SIG`: `"TERM"`, `"HUP"`, `"INT"`, `"QUIT"`, `"KILL"`, `"USR1"`, `"USR2"`,
  `"WINCH"`;
- a *unit name* follows the rule above (`NAME`, or `NAME@INSTANCE`), or names a stage (section 2).

**No shell, no code, no includes, no variable expansion.** `exec` is an argument vector. The one substitution
is `%i` (a template's instance) and `%%` (a `%`), in `description`, `exec`, `user`, `dir` and `listen` only, and
`%i` only in a template. Any other `%` in those five keys is refused; in every other key `%` is an ordinary
character.

## 2. Every key of format 1

Each row gives the key, its type, its default and its meaning. "Required" has no default. A key in none of
these tables and not reserved (section 3) is **refused by name**, with the file, the line and the nearest known
key:

    alpha: /etc/alpha/units/lobo.unit:9: [run] has no key 'Restart' (keys are lowercase: did you mean 'restart'?); the unit is not loaded

Keys starting `x-`, at the top or in a table, are ignored: they are a vendor's own data. A table starting `x-`
is not a table of format 1 and is refused like any other.

### The top

| key | type | default | meaning |
|---|---|---|---|
| `alpha` | integer | required | the format: `1` |
| `description` | string | `""` | one line shown by `alpha status` |
| `doc` | array of strings | `[]` | where to read about it (a manual page, a path, a URL) |
| `needs` | array of unit names | `[]` | start after each is ready; if one fails, is refused or stops, this one stops (or never starts) |
| `wants` | array of unit names | `[]` | start each too, and start after it is ready or has failed; its failure does not stop this one |
| `after` | array of unit names | `[]` | order only: when both are being started, start after it is ready |
| `before` | array of unit names | `[]` | order only, the other way |
| `conflicts` | array of unit names | `[]` | starting this one stops each; starting one of them stops this one |
| `stage` | string | `"multi-user"` | the stage whose start starts this unit when it is enabled: `"early"`, `"base"`, `"network"`, `"time"`, `"multi-user"`, `"maintenance"` |
| `enable` | boolean | `false` | the vendor's default: started with its stage. The admin's markers (section 4) win |

`needs` and `wants` imply `after`. A `needs`, or a timer's `unit`, naming a unit that does not exist makes this
unit invalid; a `wants`, `after`, `before` or `conflicts` naming one is a warning and otherwise empty (there is
nothing to order against).

**Stages as names.** The stages `early`, `base`, `network`, `time`, `multi-user`, `maintenance` and `shutdown`
are names every unit may use in `needs`, `wants`, `after` and `before`: `wants = ["network"]` starts a unit once
the network stage is reached. A boot reaches them in this order: `early`, then `base`, then either `network`,
`time` and `multi-user` in turn or `maintenance` instead of those three, and `shutdown` last. A `needs`, `wants`
or `after` naming a stage that is not reached before the unit's own stage is an error (an `early` unit cannot
wait for `network`, nor a unit for its own stage), and so is a `before` naming a stage, other than the unit's
own, that is not reached after it. A stage can never be in `conflicts`, and no unit file may have a stage's name.

### `[run]`: the service

| key | type | default | meaning |
|---|---|---|---|
| `exec` | array of strings | required | the program (an absolute path) and its arguments |
| `ready` | string | `"exec"` | when the service counts as ready: `"exec"` (the program was executed), `"fd:N"` with N from 3 to 9 (it wrote a newline on descriptor N), `"exit"` (it exited 0: a one-shot, which then stays done), `"forked"` (it forked and its first process exited 0; the main process is `pid_file`'s, or the group's only process) |
| `ready_timeout` | duration | `"30s"` | not ready in this long: the start failed and the group is stopped |
| `pid_file` | string | none | only with `ready = "forked"`: the absolute path the daemon writes its process id to |
| `user` | string | `"root"` | the account it runs as (ids set before it starts) |
| `group` | string | the user's primary group | the group |
| `groups` | array of strings | the groups `/etc/group` lists the user in | supplementary groups |
| `no_new_privs` | boolean | `true` when `user` is not root, else `false` | `prctl(PR_SET_NO_NEW_PRIVS)` before the program starts: a set-ID program cannot raise its privileges afterwards |
| `dir` | string | `"/"` | the working directory (absolute) |
| `env` | array of strings | `[]` | `NAME=VALUE` entries added to the base environment |
| `env_file` | string | none | an absolute path of `NAME=VALUE` lines read at each start; a missing file is an error |
| `umask` | mode | `"0022"` | the umask |
| `stdin` | string | `"null"` | `"null"` (format 1 has only this) |
| `stdout` | string | `"log"` | `"log"` (the unit's log), `"null"`, `"console"`, `"kmsg"` |
| `stderr` | string | `"stdout"` | `"stdout"` (the same stream), `"log"`, `"null"`, `"console"`, `"kmsg"` |
| `restart` | string | `"on-failure"`; `"never"` when `ready = "exit"` | `"on-failure"` (an exit other than 0, a signal, a ready timeout), `"always"`, `"never"` |
| `backoff` | array of 2 durations | `["1s", "300s"]` | the first wait before a restart, and the longest; each wait doubles |
| `burst_count` | integer, 1 or more | `5` | this many starts within `burst_window` and the next unexpected end leaves the unit failed, not restarted |
| `burst_window` | duration | `"60s"` | |
| `healthy_after` | duration | `"60s"` | running this long resets the backoff and the burst count |
| `stop_signal` | signal | `"TERM"` | sent to the main process to stop it (after `stop_exec`, if any) |
| `stop_exec` | array of strings | none | a command run to stop it, before the signal |
| `stop_timeout` | duration | `"10s"` | then SIGKILL to what is left (in `stop_scope`) |
| `stop_scope` | string | `"group"` | what a stop and a restart end: `"group"` (every process the service started) or `"main"` (the main process; the rest stay in the service's group) |
| `shutdown` | string | `"stop"` | `"stop"` at shutdown, or `"leave"` it for the kernel's end |
| `reload_signal` | signal | none | `alpha reload NAME` sends it to the main process |
| `reload_exec` | array of strings | none | or runs this command |
| `pre` | array of strings | none | one command run before `exec`, with the same user and environment; it must exit 0 |
| `post_stop` | array of strings | none | one command run after the service has stopped, however it ended |
| `runtime_dir` | string | none | a name: `/run/NAME` made at start (owned by the unit's user, mode `0755`), removed after it stops |
| `state_dir` | string | none | a name: `/var/lib/NAME` made when missing (owned by the unit's user, mode `0750`), kept |
| `pids_max` | integer, 1 or more | none | the most threads and processes the service's group may hold; on a kernel without service groups the start is refused by name |
| `foreign` | boolean | `false` | run in the foreign root. `true` is **refused by name** until alpha has a foreign root; its meaning is fixed now: `exec`, `dir`, `env_file` and `pid_file` are paths inside that root, and `user` and `group` are its accounts |

### `[limits]`: per-process resource limits, set before the program starts

| key | type | default | meaning |
|---|---|---|---|
| `nofile` | integer, 0 or more | the kernel's | RLIMIT_NOFILE, soft and hard |
| `nproc` | integer, 0 or more | the kernel's | RLIMIT_NPROC |
| `core` | integer, 0 or more | the kernel's | RLIMIT_CORE, in bytes |
| `stack` | integer, 0 or more | the kernel's | RLIMIT_STACK, in bytes |

On a kernel that cannot set limits, a value equal to the current limit is accepted and any other refuses the
start by name.

### `[socket]`: a listening trigger

| key | type | default | meaning |
|---|---|---|---|
| `listen` | array of strings | required | `"tcp:ADDRESS:PORT"` (an IPv4 address in dotted decimal, or `*`, and a port from 1 to 65535) and `"unix:/ABSOLUTE/PATH"` (a stream socket); bound by alpha |
| `names` | array of strings | `[]` | one name for each listener, passed as `LISTEN_FDNAMES`; a name is 1 to 255 bytes with no `:` |
| `backlog` | integer, 1 to 65535 | `128` | `listen(2)`'s backlog |
| `unix_mode` | mode | `"0666"` | a path socket's mode |
| `unix_owner` | string | `"root"` | a path socket's owner |
| `start` | string | `"on-connection"` | `"on-connection"` (the service starts when the first connection waits) or `"now"` (the service starts with its stage, given the listeners) |

The listeners are descriptors 3, 4, … in `listen`'s order, with `LISTEN_FDS`, `LISTEN_PID` and `LISTEN_FDNAMES`
set as sd_listen_fds(3) documents, so a daemon written for that convention works unchanged. alpha keeps its own
copy of each listener, so a restart loses no queued connection. No two units listen on one address: `tcp:*:P`
takes port P on every address.

### `[timer]`: a time trigger

| key | type | default | meaning |
|---|---|---|---|
| `unit` | unit name | this unit | what the timer starts |
| `on_boot` | duration | none | the first start this long after boot (the monotonic clock) |
| `every` | duration | none | again this long after the last start (the monotonic clock) |
| `calendar` | string | none | `"hourly"`, `"daily"`, `"weekly"`, `"monthly"`, or `"HH:MM"` (each day), `"DAY HH:MM"` (a weekday: `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`), `"*-MM-DD HH:MM"` (a day of a month each year) or `"*-*-DD HH:MM"` (a day of each month); a date no year has, such as `*-02-30`, is refused |
| `zone` | string | `"utc"` | `"utc"` or `"local"` (`/etc/localtime`) for `calendar` |
| `persistent` | boolean | `false` | a calendar start missed while the machine was off happens once soon after boot |
| `jitter` | duration | `"0s"` | a random delay up to this, drawn once per start |
| `wait_for_time` | boolean | `true` when `calendar` is set | hold calendar starts until the `time` stage is reached |

A timer has at least one of `on_boot`, `every` and `calendar`. A timer never starts a unit that is already
running; the start is counted as skipped.

### `[condition]`: whether to start at all

| key | type | default | meaning |
|---|---|---|---|
| `path_exists` | array of strings | `[]` | each path must exist |
| `path_missing` | array of strings | `[]` | each must not |
| `cmdline_has` | array of strings | `[]` | each word must be on the kernel's command line (on a kernel without `/proc/cmdline` the start is refused by name) |
| `cmdline_lacks` | array of strings | `[]` | each must not be |

A false condition leaves the unit skipped, which satisfies `wants` and fails `needs`.

### Rules across keys

- `pid_file` only with `ready = "forked"`.
- `[run]` needs `exec`.
- A `[socket]` needs `[run]` in the same unit; a unit holds one trigger, `[socket]` or `[timer]`, not both.
- A unit needs `[run]`, or a `[timer]` whose `unit` names another unit.
- `backoff` holds two durations, the first no longer than the second.

## 3. Keys reserved for later

A reserved key or table in a format 1 file is **refused by name**, never ignored, so a unit never runs less
confined or less limited than it asked:

    alpha: /etc/alpha/units/lobo.unit:14: [sandbox] is reserved (UNIT-1 §3): confinement this alpha cannot enforce yet; the unit is not loaded

| reserved | meaning fixed now | refused with |
|---|---|---|
| `[sandbox] read_only_paths`, `writable_paths`, `hidden_paths` (arrays) | paths the service sees read-only, writable, or not at all | confinement this alpha cannot enforce yet |
| `[sandbox] private_tmp` (boolean) | a `/tmp` of the service's own | the same |
| `[sandbox] network` (boolean) | `false`: no socket but AF_UNIX | the same |
| `[sandbox] syscalls_deny`, `syscalls_allow` (arrays of names) | a system-call filter, a deny list and then an allow list | the same |
| `[account] memory_max`, `memory_high` (integers, bytes) | the service group's memory: a hard limit and a reclaim point | resource accounting this alpha cannot enforce yet |
| `[account] cpu_weight` (1 to 10000), `cpu_max` (a string `"PCT%"`) | the group's share of the processors and its cap | the same |
| `[account] io_weight` (1 to 10000) | the group's share of disk time | the same |
| `[path] watch`, `on` | start when a path appears or changes | path triggers this alpha cannot watch yet |
| `[device] match` | start when a device matching `key=value` words appears | device triggers this alpha cannot watch yet |
| `[log] max`, `keep`, `rate` | the unit's own log limits | per-unit log limits this alpha cannot apply yet |
| `[run] watchdog` (duration) | the service must say it is alive this often | a liveness check format 1 does not define |
| `[run] fd_store` (integer) | descriptors alpha keeps for the service across restarts | descriptors kept across restarts, which this alpha cannot do yet |
| `[socket] accept` (boolean) | one service instance per connection (`NAME@N`) | one instance per connection, which format 1 does not define |
| `[socket]` listeners `"udp:…"` and `"unixdgram:…"` | datagram listeners | datagram listeners |

## 4. Directories, overrides and enablement

**The system manager** reads, in rising precedence:
1. `/usr/lib/alpha/units/`: vendor units, the image's and packages'. An upgrade replaces them whole; nobody edits
   them.
2. `/var/lib/alpha/imported/`: units written by `alpha import` from foreign units (section 7).
3. `/etc/alpha/units/NAME.unit`: an admin unit. A file of the same name as a lower unit replaces it whole, and
   the lower file is not read.
4. `/etc/alpha/units/NAME.d/*.conf`: drop-ins, each a file starting `alpha = 1`, applied in the byte order of
   their names over whichever unit won. **A drop-in's key replaces the same key, arrays included**, dependencies
   too. A drop-in may add a table.

A drop-in directory with no unit of its name, a file in a units directory that is neither `NAME.unit` nor a
`NAME.d/` directory (where drop-ins belong), and a file in `NAME.d/` that does not end `.conf` are warnings, and
are not read.

**Enablement** is the admin's state, not unit text: an empty file `/etc/alpha/enable.d/NAME` enables the unit,
and `/etc/alpha/disable.d/NAME` disables it; `disable.d` wins over `enable.d`, and either wins over the unit's
`enable`. `alpha enable` and `alpha disable` make and remove these files. An image upgrade keeps `/etc`, so
enablement and overrides survive upgrades. A marker that names no unit, or is not empty, is a warning.

**The per-user manager** reads, in rising precedence, `/usr/lib/alpha/user/` (vendor), `/etc/alpha/user/` (the
admin's, for every user), and `$HOME/.config/alpha/units/` with its `NAME.d/` (the user's own), with enablement
under `$HOME/.config/alpha/enable.d/` and `disable.d/`.

## 5. Validation and `alpha check`

At boot, at `alpha reread` and at `alpha check`, every unit is read and checked whole:
1. **syntax**: the TOML subset of section 1, with the file and line;
2. **keys and types**: every key known for its table (section 2) or starting `x-`, reserved keys refused
   (section 3), every value of its type;
3. **values**: absolute paths where paths are asked; users and groups present in `/etc/passwd` and `/etc/group`
   (`root` always is; a value holding `%i` is checked when the instance is known, and a foreign unit's accounts
   are the foreign root's); signals, durations,
   modes, calendar strings and listeners well formed; the rules across keys;
4. **across units**: every `needs` and timer `unit` names a unit (a `wants`, `after`, `before` or `conflicts`
   naming none is a warning); the stage rules of section 2; no cycle in the order graph (`needs`, `wants`,
   `after` and `before` together); no two units listening on one address; an instance's template present;
5. **at each start** (facts that can change): `exec`'s program exists and can be executed; the kernel can do
   what the unit asks (`cmdline_has`, `cmdline_lacks`, `pids_max`, `[limits]`).

At **boot**, a unit that fails steps 1 to 4 is not loaded and never started, with every reason in `alpha
status`; the rest of the system boots. A unit that `needs` a unit which is not loaded gets a warning (it will not
start); the error stays with the unit at fault. At **`alpha reread`**, any unit not loaded refuses the whole
reread and the running set stays as it was.

### `alpha check`

    alpha check [--root DIR] [FILE.unit ...]

- With no FILE, `alpha check` reads the system set from the directories of section 4 under `DIR` (by default
  `/`) and prints every finding of steps 1 to 4. Paths are printed as installed (`/etc/alpha/units/lobo.unit`),
  whatever `DIR` is.
- With FILEs, each named file takes the vendor place of its name (`/usr/lib/alpha/units/NAME.unit`) in the set
  under `DIR`, where admin units and drop-ins still apply over it, and the whole set is checked. This is how a
  package's units are checked before they are installed. Every finding is printed, with a named file's path as
  it was given, but the exit status counts only the errors in the named files and the errors across units that
  involve them. A named file that an admin unit replaces is still checked on its own, with a warning that it is
  not used. A drop-in is checked with its unit, never alone.
- Findings go to standard output, one a line, in the byte order of the units' names, then each unit's file and
  its drop-ins in order, then the line (a finding about a whole file before that file's lines, and findings on
  one line in the order of their items); findings about files and directories that are not units come last, in
  the byte order of their paths. A last
  line counts them:

        alpha check: 9 units, 1 error, 0 warnings
        alpha check: 9 units, 2 errors, 0 warnings; 1 error in the named files

- The exit status is 0 when no error is counted (warnings allowed), 1 when one is, and 2 for a usage error, a
  missing root or a file that cannot be read; usage errors are named on standard error.

## 6. The compatibility alpha promises

- **Format 1 is read unchanged by every later alpha.** No key of format 1 is removed or given a new meaning; a
  new key, or a reserved key made active, comes only with a new format number, which a unit asks for with
  `alpha = 2`.
- **A package ships its units under `/usr/lib/alpha/units/` (or `user/`) with `alpha = 1`**, never under
  `/etc/alpha`, and never depends on an admin unit. A package manager runs `alpha check` on them before a
  transaction commits and `alpha reread` after it.
- **The control protocol and `alpha status --format=1` are versioned on their own**: scripts read the machine
  format, never the human text.

## 7. systemd's units, mapped

The documented core of systemd.service(5), systemd.socket(5), systemd.timer(5), systemd.target(5) and
systemd.unit(5) (version 262's manual), against format 1. "Import" says what a later `alpha import` does with
each.

| systemd | format 1 | import |
|---|---|---|
| `[Unit] Description=` | `description` | yes |
| `Documentation=` | `doc` | yes |
| `Wants=` and `After=` | `wants` | yes |
| `Requires=` and `After=` | `needs` | yes |
| `Requires=` or `Wants=` without `After=` | `needs` or `wants` (alpha always orders) | yes, said in the import note |
| `After=`, `Before=` | `after`, `before` | yes |
| `Conflicts=` | `conflicts` | yes |
| `BindsTo=`, `PartOf=`, `Requisite=`, `Upholds=` | none (`needs` is the nearest) | refused by name |
| `OnFailure=`, `OnSuccess=` | none in format 1 | refused by name |
| `ConditionPathExists=` (and `!`) | `[condition] path_exists`, `path_missing` | yes |
| `ConditionKernelCommandLine=` | `cmdline_has`, `cmdline_lacks` | yes |
| other `Condition*=`, `Assert*=` | none | refused by name |
| `StartLimitIntervalSec=`, `StartLimitBurst=` | `burst_window`, `burst_count` | yes |
| `[Service] Type=simple`, `exec` | `ready = "exec"` | yes |
| `Type=notify`, `notify-reload` | none (`ready = "fd:N"` is a different protocol) | imported as `"exec"` with a note until alpha can take that notification |
| `Type=forking` with `PIDFile=` | `ready = "forked"`, `pid_file` | yes |
| `Type=oneshot` (`RemainAfterExit=yes`) | `ready = "exit"` (stays done) | yes; `RemainAfterExit=no` refused by name |
| `Type=dbus`, `BusName=` | none (no D-Bus) | refused by name |
| `Type=idle` | `"exec"` | yes |
| `ExecStart=` (one, no prefix) | `exec` | yes; `$VAR` expansion and the `-`, `@`, `+`, `!` and `:` prefixes refused by name |
| `ExecStartPre=` (one; several) | `pre`; none | one: yes; several: refused |
| `ExecStop=` | `stop_exec` | yes (one) |
| `ExecStopPost=` | `post_stop` | yes (one) |
| `ExecReload=` (one) | `reload_exec` | yes; `kill -HUP $MAINPID` becomes `reload_signal = "HUP"` |
| `Restart=no`, `on-failure`, `always` | `restart` | yes; `on-success`, `on-abnormal`, `on-watchdog`, `on-abort` refused |
| `RestartSec=`, `RestartMaxDelaySec=` | `backoff` | yes |
| `TimeoutStartSec=`, `TimeoutStopSec=` | `ready_timeout`, `stop_timeout` | yes |
| `KillMode=control-group`, `process`; `mixed`, `none` | `stop_scope = "group"`, `"main"`; none | yes; `mixed` and `none` refused |
| `KillSignal=` | `stop_signal` | yes |
| `User=`, `Group=`, `SupplementaryGroups=` | `user`, `group`, `groups` | yes (the foreign root's accounts) |
| `WorkingDirectory=`, `Environment=`, `EnvironmentFile=`, `UMask=` | `dir`, `env`, `env_file`, `umask` | yes (`EnvironmentFile=-` refused) |
| `StandardOutput=journal`, `null`, `kmsg` | `stdout = "log"`, `"null"`, `"kmsg"` | yes |
| `LimitNOFILE=`, `LimitNPROC=`, `LimitCORE=`, `LimitSTACK=` | `[limits]` | yes |
| `NoNewPrivileges=` | `no_new_privs` | yes |
| `RuntimeDirectory=`, `StateDirectory=` (one name) | `runtime_dir`, `state_dir` | yes |
| `TasksMax=` | `pids_max` | yes |
| `MemoryMax=`, `CPUWeight=`, `CPUQuota=`, `IOWeight=` | reserved `[account]` | refused until those keys are active |
| `ProtectSystem=`, `PrivateTmp=`, `CapabilityBoundingSet=`, `SystemCallFilter=` and the rest of systemd.exec(5)'s sandbox | reserved `[sandbox]`, or none | refused by name: a unit never runs less confined than it asked |
| `DynamicUser=`, credentials, `RootDirectory=`, namespaces, specifiers beyond `%i`, `%n`, `%%` | none | refused by name |
| `[Socket] ListenStream=` (IPv4 or a path) | `[socket] listen` | yes |
| `ListenDatagram=`, `ListenSequentialPacket=`, `Accept=yes` | reserved | refused |
| `SocketMode=`, `SocketUser=`, `Backlog=`, `FileDescriptorName=`, `Service=` | `unix_mode`, `unix_owner`, `backlog`, `names`, the file's name | yes |
| `[Timer] OnBootSec=`, `OnUnitActiveSec=` | `on_boot`, `every` | yes |
| `OnCalendar=` | `calendar` | the shapes of section 2; any other expression refused by name |
| `Persistent=`, `RandomizedDelaySec=`, `Unit=` | `persistent`, `jitter`, `unit` | yes |
| `AccuracySec=`, `OnClockChange=`, `WakeSystem=` | none | dropped with a note (accuracy); refused (the others) |
| `[Install] WantedBy=multi-user.target` | `stage = "multi-user"`; enabling is the admin's act | the stage is taken; enabling stays explicit |
| `WantedBy=` another target, `RequiredBy=`, `Alias=`, `Also=` | none | refused, or dropped with a note |
| `.target` units | the stages (`network.target` and `network-online.target` are `network`; `time-sync.target` is `time`; `multi-user.target` is `multi-user`) | other targets refused |
| `.mount`, `.path`, `.device`, `.slice`, `.scope`, `.swap`, `.automount` | none | refused by name |

**What an importer can translate:** a plain long-running daemon or one-shot, with its account, environment,
limits, ordering, restart policy, sockets on IPv4 or paths, and simple timers. **What it cannot:** D-Bus
activation, the exec sandbox, templates and specifiers beyond `%i`, notify readiness, generators, mount, path,
device and slice units, and any unit whose meaning depends on systemd running as process 1. Each refusal names
the key and the line.

## 8. Worked examples

Each of these is a golden case of `alpha check` (`tests/unit/examples/`).

### burrowd, the ssh server (`/usr/lib/alpha/units/burrowd.unit`)

```toml
alpha = 1
description = "burrowd, the ssh server"
doc = ["burrowd(8)"]
wants = ["network", "burrowd-key"]
enable = true

[run]
exec = ["/bin/burrowd", "-D", "-E", "/var/log/burrowd.log"]
stop_scope = "main"
stderr = "log"
backoff = ["1s", "300s"]
```

`stop_scope = "main"`: a restart or stop of burrowd leaves running ssh sessions alone; they stay in burrowd's
group, so `alpha status burrowd` counts them. `-E` keeps burrowd's own log file. alpha starts every service with
every signal at its default and an empty mask, so nothing needs to reset them first.

### burrowd's host key (`/usr/lib/alpha/units/burrowd-key.unit`)

```toml
alpha = 1
description = "burrowd's host key, made at the first boot, its fingerprint shown at every boot"
stage = "base"
after = ["seed-load"]

[run]
exec = ["/usr/lib/alpha/libexec/burrowd-key"]
ready = "exit"
stdout = "console"
```

Started through burrowd's `wants`. `seed-load` is an order only: when the entropy seed's unit is installed the
key is made after the pool is seeded; on a system without it, the `after` names nothing and `alpha check` says
so in one warning.

### logd (`/usr/lib/alpha/units/logd.unit`)

```toml
alpha = 1
description = "logd, the kernel's log and the services' logs on disk"
stage = "base"
enable = true

[run]
exec = ["/bin/logd"]
restart = "always"
backoff = ["1s", "300s"]
stdout = "null"
stderr = "kmsg"
shutdown = "leave"
```

`shutdown = "leave"`: logd writes its shutdown record only when the kernel ends the run, so alpha never stops it
at shutdown. `stderr = "kmsg"`: logd cannot log through itself.

### lobo, the web server (`/usr/lib/alpha/units/lobo.unit`)

```toml
alpha = 1
description = "lobo, the web server"
doc = ["lobo(8)", "/usr/share/doc/lobo/CONTROL.md"]
wants = ["network"]

[run]
exec = ["/bin/lobo", "-p", "/srv/www", "-c", "/etc/lobo/lobo.conf"]
reload_signal = "HUP"
stop_signal = "QUIT"
stop_timeout = "30s"
runtime_dir = "lobo"

[limits]
nofile = 1024
```

The master keeps root and binds ports 80 and 443; its workers drop to the `lobo` account by lobo's own
configuration. `QUIT` is the graceful stop. `runtime_dir` makes `/run/lobo` for its control socket. `enable` is
left `false`: shipped, and started at every boot only once the admin runs `alpha enable --now lobo`.

### lobo with socket activation (`/etc/alpha/units/lobo.d/10-sockets.conf`)

```toml
alpha = 1

[socket]
listen = ["tcp:*:80", "tcp:*:443"]
names = ["http", "https"]
start = "now"

[run]
exec = ["/bin/lobo", "-c", "/etc/lobo/lobo.conf"]
user = "lobo"
```

An admin's drop-in. alpha binds both ports as root and starts lobo as `lobo` from the first moment, with
descriptors 3 and 4, `LISTEN_FDS=2` and `LISTEN_FDNAMES=http:https`; `no_new_privs` is `true` for a user other
than root. This needs a lobo that adopts inherited listeners.

### warren at a user's login (`/usr/lib/alpha/user/warren.unit`)

```toml
alpha = 1
description = "warren's server for this user"
doc = ["warren(1)"]

[run]
exec = ["/bin/warren", "server", "--foreground"]
ready = "fd:3"
```

A user unit: the user's manager runs it as the user, the user turns it on with `alpha --user enable warren`, and
it starts with the user's manager at their first session.

### A daily refresh (`/usr/lib/alpha/units/pxg-refresh.unit`)

```toml
alpha = 1
description = "refresh pxg's repository metadata before the timestamp expires"
wants = ["network", "time"]

[run]
exec = ["/bin/pxg", "update"]
ready = "exit"

[timer]
calendar = "daily"
jitter = "1h"
persistent = true
```

Enabled, the timer is armed with `multi-user`; each day it starts the run, which is `ready = "exit"` and so
`restart = "never"`. `wait_for_time` is `true` with a calendar, so nothing is fetched before the clock is right.

### A one-shot boot task (`/usr/lib/alpha/units/pax-upgrade-boot.unit`)

```toml
alpha = 1
description = "see to an upgrade staged over ssh (disarm, re-arm or clean)"
stage = "early"
enable = true

[condition]
path_exists = ["/bin/pax-upgrade"]

[run]
exec = ["/bin/pax-upgrade", "boot"]
ready = "exit"
stdout = "console"
```

### A one-shot with a stop action (`/usr/lib/alpha/units/seed-load.unit`)

```toml
alpha = 1
description = "load the entropy seed carried from the last boot; save it at shutdown"
stage = "base"
enable = true
before = ["burrowd-key"]

[condition]
path_exists = ["/var/lib/pax-random/seed"]

[run]
exec = ["/bin/pax-seed", "load"]
ready = "exit"
stop_exec = ["/bin/pax-seed", "save"]
```

A one-shot that stays done; at shutdown its stop runs `stop_exec`.

### A daemon from the foreign root, as an importer would write it

The input is a unit of the shape packages for systemd ship, written for this example from systemd.service(5)'s
keys:

```ini
[Unit]
Description=Key-value store
After=network.target

[Service]
Type=notify
User=kv
ExecStart=/usr/bin/kv-server /etc/kv/kv.conf
Restart=always
LimitNOFILE=10032

[Install]
WantedBy=multi-user.target
```

`alpha import kv` writes `/var/lib/alpha/imported/kv.unit`. (Had the unit carried a sandbox key such as
`ProtectSystem=`, the import would have been refused by name: a unit never runs less confined than it asked.)

```toml
alpha = 1
description = "Key-value store"
x-imported-from = "/usr/lib/systemd/system/kv.service"
x-imported-notes = ["Type=notify (imported as ready = exec)"]
wants = ["network"]
stage = "multi-user"

[run]
foreign = true
exec = ["/usr/bin/kv-server", "/etc/kv/kv.conf"]
user = "kv"
restart = "always"

[limits]
nofile = 10032
```

This alpha refuses the file at load, because `foreign = true` waits for the foreign root; that refusal is the
one error of the worked set. It would also be refused at start, `nofile = 10032` being above a kernel's fixed
limit. Both refusals are by name. Enabling it is a separate, explicit `alpha enable kv`.

## 9. Findings

Every finding `alpha check` prints has one of these shapes:

    alpha: <path>:<line>: <text>; the unit is not loaded
    alpha: <path>: <text>; the unit is not loaded
    alpha: <path>:<line>: warning: <text>
    alpha: <path>: warning: <text>

The first two are errors and the others warnings. The line is left out when the finding is about a whole file or
directory (its name, or a directory with no unit); a finding about a whole unit that no key or table carries is
at the unit's format line, and one about a table at its header. The reader (step 1) stops at the first syntax
error of a file, so a file has at most one; steps 2 to 4 report everything they find.

In the templates below, `<key>` stands for a key as `'exec' in [run]` (a key in a table) or `'description'` (a
key at the top), and the other words in angle brackets for the value at fault. Every template below is matched
by at least one golden case under `tests/unit/`, and every finding a golden case expects matches a template
(`tools/check-docs` holds the two together).

**Not TOML** (every TOML reader refuses these):

| template | when |
|---|---|
| `the file is not UTF-8` | a byte sequence that is not UTF-8 |
| `a byte-order mark is not allowed at the start of a unit file` | the file starts with U+FEFF |
| `a carriage return must be followed by a line feed` | a CR alone |
| `control character U+<nnnn> is not allowed in a comment` | a control character other than tab in a comment |
| `control character U+<nnnn> is not allowed in a string` | the same in a string |
| `the string is not closed on its line` | no closing quote before the end of the line |
| `the array is not closed` | the file ends inside an array |
| `unknown escape '<escape>'` | a backslash TOML does not define |
| `'<escape>' is not a Unicode scalar value` | a `\u` or `\U` escape outside the scalar values |
| `'<escape>' needs <n> hexadecimal digits` | a short `\u` (4) or `\U` (8) |
| `<key> is set twice (first on line <n>)` | a key repeated in its table |
| `[<table>] appears twice (first on line <n>)` | a table header repeated |
| `a line holds a key, '=' and a value, or a [table]` | a line that is neither |
| `<key> has no value` | nothing after `=` on the line |
| `unexpected '<char>' after the value` | more than a comment after a value |
| `unexpected '<char>' in a key` | a character no bare key holds |
| `integers have no leading zero: '<value>'` | `007` |
| `'<value>' does not fit in 64 bits` | an integer past 9223372036854775807 |
| `'<value>' is not a value (a string is quoted)` | a bare word after `=` |
| `a key is missing before '='` | `= 1` |
| `the array's items need a comma between them` | two items with no comma |
| `the table header is not closed` | `[run` |

**TOML, but not format 1:**

| template | when |
|---|---|
| `format 1 integers are plain decimal digits: '<value>'` | a sign, an underscore, a hexadecimal, octal or binary integer |
| `floats are not in format 1: '<value>'` | a float, `inf` or `nan` |
| `dates and times are not in format 1: '<value>'` | a date, a time, or both |
| `multi-line strings are not in format 1` | `"""` or `'''` |
| `inline tables are not in format 1` | `{` as a value |
| `arrays of tables are not in format 1` | `[[run]]` |
| `dotted keys are not in format 1: '<key>'` | `run.exec = …` |
| `quoted keys are not in format 1` | `"exec" = …` |
| `nested tables are not in format 1: [<table>]` | `[run.env]` |
| `arrays inside arrays are not in format 1` | `[["a"]]` as a value |
| `format 1 arrays hold strings only` | an array holding an integer or a boolean |
| `a unit file starts with 'alpha = 1'` | no `alpha` key, or another key first |
| `format <n> is not known to this alpha` | `alpha` is another number |

**Keys and types:**

| template | when |
|---|---|
| `<table> has no key '<name>'` | a key format 1 does not have; `<table>` is `[run]` (or another table) or `the top level` |
| `<table> has no key '<name>' (keys are lowercase: did you mean '<name>'?)` | the key differs from a known one only by case |
| `<table> has no key '<name>' (did you mean '<name>'?)` | a known key of the same table within two edits |
| `<table> has no key '<name>' ('<name>' belongs in [<table>])` | the key is another table's |
| `<table> has no key '<name>' ('<name>' belongs at the top level)` | the key is a top-level key |
| `format 1 has no table [<table>] (did you mean [<table>]?)` | a table within two edits of a known one, or differing by case |
| `format 1 has no table [<table>] (the tables are [run], [socket], [timer], [condition] and [limits])` | any other unknown table, `x-` tables included |
| `[<table>] is reserved (UNIT-1 §3): <reason>` | a reserved table (section 3 gives each reason) |
| `<key> is reserved (UNIT-1 §3): <reason>` | a reserved key in a table of format 1 |
| `'foreign' in [run] is refused: this alpha has no foreign root yet` | `foreign = true` |
| `<key> must be <type>` | a value of the wrong TOML type; `<type>` is `a string`, `an integer`, `true or false`, `an array of strings`, `an array of unit names`, `a duration such as "30s"`, `an array of two durations such as ["1s", "300s"]`, `a mode such as "0644"`, `a signal name such as "TERM"`, `a unit name`, `a calendar time such as "daily" or "03:00"`, or the key's words |

**Values:**

| template | when |
|---|---|
| `<key> is '<value>'; it must be <words>` | a word the key does not take (`ready`, `restart`, `stage`, …); `<words>` is `"null"` for a key of one word and `one of "a", "b" or "c"` otherwise (`ready`'s are `one of "exec", "fd:3" to "fd:9", "exit" or "forked"`) |
| `<key>: '<value>' is not a duration: each term is a number and a unit, as "90s" or "1h 30min"` | a malformed duration |
| `<key>: '<value>' is not a duration: '<unit>' is not a unit (did you mean '<unit>'?)` | a unit alpha can name the meaning of: `m` and `mins` (`min`), `sec` and `secs` (`s`), `hr` and `hours` (`h`), `day` and `days` (`d`), `msec` (`ms`) |
| `<key>: '<value>' is not a duration: '<unit>' is not a unit (the units are ms, s, min, h and d)` | any other unit |
| `<key>: '<value>' is not a duration: it is longer than alpha can count` | a sum past 64 bits of milliseconds |
| `<key>: '<value>' is not a mode (3 or 4 octal digits, as "0644")` | |
| `<key>: '<value>' is not a signal format 1 knows (TERM, HUP, INT, QUIT, KILL, USR1, USR2 or WINCH)` | any other word |
| `<key>: '<value>' is not a signal format 1 knows (write it without SIG: '<signal>')` | `SIGTERM` |
| `<key>: '<value>' is not a signal format 1 knows (signal names are upper case: '<signal>')` | `term` |
| `<key>: '<value>' is not a unit name (<why>)` | `<why>` is `1 to 64 bytes`, `a name starts with a letter or a digit`, `a name is lowercase letters, digits, '.', '_' and '-'`, or `an instance is 1 to 64 bytes of letters, digits, '.', '_' and '-'` |
| `the file name '<file>' is not NAME.unit with a unit name (<why>)` | a unit file's own name, with the same `<why>` |
| `<key>: '<value>' is not an absolute path` | |
| `<key> needs at least the program` | `exec = []` |
| `<key>: '<value>' is not NAME=VALUE with NAME of letters, digits and '_', not starting with a digit` | an `env` entry |
| `<key> is <n>; it must be <range>` | `<range>` is `1 or more`, `0 or more` or `from 1 to 65535` |
| `<key>: '<value>' is not a listener (<why>)` | `<why>` is `"tcp:ADDRESS:PORT" or "unix:/PATH"`, `IPv6 listeners are not in format 1`, `the address is an IPv4 address or '*'`, `the port is from 1 to 65535` or `the path is absolute` |
| `<key>: '<value>' is reserved (UNIT-1 §3): datagram listeners` | `udp:` and `unixdgram:` |
| `<key> does not give one name to each listener` | `names` is neither empty nor as long as `listen` |
| `<key>: '<value>' is not a listener name (<why>)` | `<why>` is `a name is not empty`, `a name has no ':'` or `a name is at most 255 bytes` |
| `<key>: '<value>' is not a calendar time (<why>)` | `<why>` is `"hourly", "daily", "weekly", "monthly", "HH:MM", "DAY HH:MM", "*-MM-DD HH:MM" or "*-*-DD HH:MM"`, `the hour is 00 to 23 and the minute 00 to 59`, `the days are MON, TUE, WED, THU, FRI, SAT and SUN`, `the month is 01 to 12 and the day 01 to 31`, or `no year has day <dd> of month <mm>` |
| `<key> needs two durations, the first wait and the longest` | `backoff` not of two |
| `<key>: the first wait '<value>' is longer than the longest '<value>'` | |
| `<key>: '<value>' is not in /etc/passwd` | an account `user` or `unix_owner` names |
| `<key>: '<value>' is not in /etc/group` | a group `group` or `groups` names |
| `<key>: '%<char>' is not a substitution (format 1 has %i and %%)` | `%` followed by anything but `i` or `%`, or nothing |
| `<key>: '%i' is only for templates (NAME@.unit)` | `%i` in a unit that is not a template |
| `'pid_file' in [run] is only for ready = "forked"` | |
| `[run] needs exec` | |
| `[timer] needs on_boot, every or calendar` | |
| `[socket] needs [run] in the same unit` | |
| `a unit holds one trigger: [socket] or [timer], not both` | |
| `a unit needs [run], or a [timer] whose unit names another unit` | |
| `the file cannot be read: <why>` | a unit file or drop-in alpha may not read |

**Across units:**

| template | when |
|---|---|
| `<key> names '<name>', which is no unit` | an error for `needs` and a timer's `unit`, a warning for `wants`, `after`, `before` and `conflicts` |
| `<key> names '<name>', which is not loaded, so this unit will not start` | a warning: a `needs` naming a unit with an error |
| `the order has a cycle: <cycle>` | one error for each unit on the cycle (`a -> b -> a`, each unit waiting for the next), at its key naming the next unit, or its format line when it has none |
| `<key>: '<value>' takes the same address as '<value>' in '<name>'` | two units on one address, an error in each |
| `<key> names the stage '<stage>', which is not reached before this unit's stage '<stage>'` | `needs`, `wants` or `after` |
| `<key> names the stage '<stage>', which is not reached after this unit's stage '<stage>'` | `before` |
| `<key> names the stage '<stage>': a stage cannot be a conflict` | |
| `'<name>' is a stage; no unit file may have its name` | `network.unit` |
| `'user@.unit' is alpha's own template; no unit file may have its name` | |

**Files, directories and markers** (all warnings):

| template | when |
|---|---|
| `there is no unit '<name>' for these drop-ins` | a `NAME.d/` with no unit |
| `not a unit file (NAME.unit) or a drop-in directory (NAME.d); not read` | anything else in a units directory |
| `not a drop-in (NAME.conf); not read` | anything else in `NAME.d/` |
| `the marker names no unit` | an `enable.d` or `disable.d` file |
| `the marker is not empty; only its name counts` | |
| `'<path>' replaces this unit, so it is not used` | a named file an admin unit replaces |

## 10. What a start does

The manager (`alpha manager`) starts a service's program in its own process, set up in this order between the
fork and the exec, so the program begins in a known state whatever state the manager is in:

1. A new session and process group, led by the service; no controlling terminal.
2. Every signal's disposition back to its default, and the signal mask emptied.
3. The limits of `[limits]`, each set soft and hard. A value equal to the current limit is left as it is, never
   set again (a kernel that cannot set limits accepts a unit asking for what it has).
4. `no_new_privs`, when the unit's `no_new_privs` is true (by default, whenever `user` is not root).
5. The umask (`umask`) and the working directory (`dir`).
6. The supplementary groups, the group and the user, last, so nothing after them runs with the manager's ids.
7. The descriptors: 0 from `/dev/null`; 1 and 2 by `stdout` and `stderr` (below); for `ready = "fd:N"`, the
   readiness pipe at N; every other descriptor closed.
8. The environment, exactly: `PATH=/usr/bin:/bin`, `HOME`, `USER`, `LOGNAME` and `SHELL` from the user's line of
   `/etc/passwd`, `ALPHA_UNIT` (the unit's name), `ALPHA_INVOCATION` (its invocation, docs/CONTROL-1.md 1.1), then
   the lines of `env_file`, then `env`, a later entry replacing an earlier one of the same name. Nothing of the
   manager's own environment is passed.
9. The exec of `exec`. If it fails, the manager hears why (the error's name) and the start fails; the program is
   never counted as started.

Before any of this, the manager checks the facts that can change between checks (section 5, step 5): `exec[0]`
exists and can be executed, `env_file` can be read, each `[condition]`, and `pids_max`, which this version of alpha
refuses at start by name, since it contains a service by its process group and only the kernel's service group can
count its processes. A false condition skips the start; any other refused fact fails it.

**Output.** `stdout = "log"` (and `stderr = "log"`, or `"stdout"` when stdout is `"log"`) sends the stream to the
manager's own standard error until alpha's logs exist; `"null"` is `/dev/null`, `"console"` the system console and
`"kmsg"` the kernel's log.

**Ready, in detail.** `"exec"`: the exec succeeded. `"fd:N"`: the program writes a newline on N; anything before the
newline is ignored, and closing N without one fails the start. `"forked"`: the program's first process exits 0,
then the main process is the one whose id `pid_file` holds (read once, and it must be a member of the unit's
group), or, with no `pid_file`, the group's only process; anything else fails the start. `"exit"`: the program
exits 0.
