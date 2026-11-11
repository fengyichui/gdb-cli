# jlink probe reuse — design (approved)

Date: 2026-11-11
Status: approved by user (design + USB/IP clarification)

## Intent / why

`gdb-cli jlink` currently starts a brand-new JLinkGDBServer + GDB session on
every invocation. Starting a second time against the same physical probe
silently spawns a second server that fights the first for the USB device.
Observed live: two `target` sessions (`7b80d61b`@49281, `5e24c387`@43769), two
running instances (`bf247e4c`, `fe8b6b3f`), both `select=usb=69406159`,
`device=OM6628X`. The first server's log shows the contention symptom once the
second attached:

```
ERROR: Failed to halt CPU.
Downloading 416 bytes @ address 0x00204000 - Verify failed ...
```

The user wants the second start to **reuse the existing session** instead of
creating a duplicate.

## Root cause (verified)

`jlink_start` (`src/gdb_cli/cli.py:1166`) always does
`find_free_port()` → `start_gdbserver()` → `_connect_gdb_session()`. The only
duplicate detection is `duplicate_probes` (`cli.py:1220-1223`), which matches
`select` string equality and merely appends a `warning` to the output
(`cli.py:1263-1270`) — it neither blocks nor reuses. `find_session_by_remote`
idempotence only fires on an identical `host:port`, and the port is new each
time, so it never triggers.

## Goals

- Second start against an already-serving probe reuses the existing
  server/session; no new server process, no new port.
- Works for both `--select usb=<serial|nickname>` and `--select ip=<host>:<port>`.
- Nickname and serial forms of the same USB probe are recognized as one probe.
- A probe already serving a *different* device is an error, not a silent reuse.
- A running server whose GDB session died is reconnected, not duplicated.

## Non-goals / anti-goals

- Do not change `jlink restart` semantics (already keeps session_id).
- Do not silently apply different `--rtos/--speed/--init-cmd` onto a reused
  server; one probe = one server. To change config: stop+start or restart.
- Anti-goal: leaving two servers contending for one probe (the current bug).

## Approaches considered

1. **Warn-only (current).** Rejected: does not prevent the contention.
2. **Block duplicate starts with an error.** Rejected: user explicitly wants
   reuse, not an error, when the same device is already served.
3. **Reuse by probe identity + device (chosen).** Insert a reuse check before
   port allocation; match on normalized probe identity and device; reuse the
   live session, reconnect a dead one, error on device conflict.

## Design (chosen)

Matching key = **physical probe identity + device**.

Probe identity normalization (`--select`):
- `usb=<selector>`: resolve `<selector>` (serial OR nickname) to the probe
  serial via `enumerate_usb_devices()`. Identity = `usb:<serial>`. If
  enumeration fails or the selector is unknown, fall back to the literal
  `usb=<selector>` string (still covers identical-select starts).
- `ip=<host>:<port>`: identity = `ip:<host>:<port>` (normalized, no
  enumeration). Two IP selects are the same probe iff host:port match.
- USB and IP identities never collide (different prefixes).

Decision table at `jlink_start`, before `find_free_port()`:

| Existing running instance on same probe | device | session | action |
|---|---|---|---|
| yes | same | alive | reuse → `status:"reused"`, return existing `jlink_id`/`session_id` |
| yes | same | dead/missing | reconnect to that server → `status:"reconnected"`, new session_id, same server |
| yes | different | — | error exit (`probe_device_conflict`) |
| no | — | — | normal start |

- Reuse output mirrors `load`/`attach`/`target`: `status:"reused"` + `message`.
- Reconnect reuses the running server (no new process); creates a fresh GDB
  session via `_connect_gdb_session`, replaying persisted `session_config`
  (incl. default init cmds). Keeps the same `jlink_id`.
- Remove the `duplicate_probes` warn path and `cli.jlink.probe_in_use_warning`.

## Implementation notes (builder)

- Add probe-identity helpers in `jlink.py` (pure + one enumeration-backed
  resolver); unit-test normalization without hardware by injecting the device
  list.
- Reuse/reconnect/conflict logic lives in `jlink_start`; session liveness via
  `session._is_session_alive` / `get_session`.
- New locale keys (en/zh_cn/ru, identical key sets):
  `cli.jlink.session_reused_message`, `cli.jlink.session_reconnected_message`,
  `cli.jlink.probe_device_conflict`.
- Replace `test_start_warns_when_probe_already_in_use` with reuse assertions;
  add tests for reconnect, device conflict, nickname==serial, ip match.
- TDD: failing tests first. Fast suite + ruff. Hardware verify second start
  returns `reused` with no new server (usb serial, usb nickname, and ip paths
  where feasible). Update SKILL.md + CHANGELOG. Single commit.