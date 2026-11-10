# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-11-10

### Added
- `jlink --init-cmd "<gdb command>"` (repeatable): executed automatically
  once the session is ready (e.g. J-Link `monitor exec` device
  configuration). Persisted with the instance and replayed by
  `jlink restart`; failures surface as `init_errors` in the output.
- `jlink restart` now keeps the same session_id across a restart, so
  callers' `$SESSION` references survive.
- `gdb-cli stop -s <session>` now also stops the JLinkGDBServer bound to
  a session that was started by `jlink`.
- `jlink --rtos` lists the supported RTOS plugins in all locales without
  exposing the internal plugin path.

### Removed
- Removed the command safety filter and all related policy: `--safe`,
  `--allow-write`, `--allow-call`, `safety_level` session metadata and
  `safety.py`. `exec` and `thread-apply` now run any GDB command without a
  whitelist, including `source`, `python`, `shell` and multi-line input.

### Fixed
- `ptype` accepts type names (`TCB_t`, `struct tskTaskControlBlock`) by
  resolving them with `gdb.lookup_type` before falling back to expression
  evaluation.
- `eval --deref` formats `char*` as a string when GDB reports C `char` as
  `TYPE_CODE_INT` instead of `TYPE_CODE_CHAR`.
- `jlink` warns when another running instance already uses the same probe
  selector, instead of silently starting a second GDBServer on that probe.

## [0.4.0] - 2026-11-09

### Added
- `jlink` command group: manage JLinkGDBServer end-to-end for embedded
  debugging — `start` (auto-start GDBServer + auto-establish GDB session,
  strict ready verification), `stop`, `restart` (server + session
  reconnect), `status`, `devices` (USB probe enumeration)
- Probe selection via `--select usb=<serial|nickname>` or
  `--select ip=<host>:<port>`; bare `usb`/`ip` and `usb=*` rejected to
  prevent GUI dialogs on multi-probe hosts
- `--extra-arg` passthrough for JLinkGDBServer options with reserved
  parameter protection (`-select/-port/-device/-if/-gui/-nogui`)
- `gdb-cli stop --before-detach` pre-detach command hook (rarely needed
  for J-Link: the server resumes the target automatically on disconnect)
- `eval --deref` opt-in pointer auto-dereference (default off, MMIO-safe)
- `target --remote-mode` (remote | extended-remote)
- Embedded debugging workflow in the gdb-cli skill (Step 1 J-Link entry,
  Cortex-M HardFault pattern, J-Link eval cases)

### Security
- `--allow-write/--allow-call` now actually reach the RPC server (session
  meta previously dropped safety_level) and are enforced at the GDB level
  via `set may-write-memory/-registers/may-call-functions off`
- Multi-line GDB commands rejected (second-line bypass); `source` blocked
  at all levels; `thread apply ... <cmd>` filtered by the wrapped verb;
  safety module unavailability is fail-closed
- Process kill paths validate /proc starttime identity (PID reuse can no
  longer kill innocent processes); `stop --force` required for kill
  fallback

### Fixed
- `-ex` argument quoting broke `source`, `target extended-remote` and
  `set` commands (remote/embedded targets could not connect at all)
- `__file__` unavailable after GDB `source` (RPC server failed to start)
- `handle_exec` nested `post_event` deadlocked every raw command
- Architecture-aware default registers (armv7e-m/armv8-m.main, AArch64)
- `Frame.find_sal()` replaces non-existent `Frame.sal()`
- `gdb.TYPE_CODE_FLT` replaces non-existent `TYPE_CODE_FLOAT`
- Failed connect/attach/load no longer reports "started" (launcher RPC
  handshake + inferior check, dead ports fail fast with exit 1)
- Handler errors now surface as `ok:false` with non-zero CLI exit codes;
  heartbeat generation guard, correct `detach inferiors` syntax,
  per-connection RPC threads (ping/status/stop responsive during long
  commands), command timeout uses the configured value
- Startup failure rollback (no GDB/JLinkGDBServer orphans), atomic
  metadata writes, JLinkGDBServer devices enumeration exit code
- Skill docs: stale command names (`eval-cmd`/`locals-cmd`) corrected

### Tests
- 359 unit tests (was 200); ruff clean; end-to-end verified on dual USB
  probes (nRF54L15DK + J-Link CE) and a J-Link remote server

## [0.3.0] - 2026-04-25

### Security
- Fix RCE via `exec` command: `python` command now blocked, `SafetyFilter` integrated at runtime
- Fix RCE via `thread-apply`: zero safety filtering now enforced with `SafetyFilter.check_command()`
- Fix privilege escalation: server now enforces session-configured `safety_level`, ignores client override

### Added
- Signal handlers (SIGTERM/SIGINT) for clean GDB child process cleanup
- PID reuse detection via `psutil.Process(name)` cross-verification

### Changed
- All handler calls now routed through `gdb.post_event()` for thread safety
- `_wait_for_socket` now checks GDB process health during polling

### Fixed
- FIFO/file descriptor leak in launcher exception paths
- Heartbeat timeout now cleans up socket file before `os._exit()`
- `SafetyFilter` path resolution in `handlers.py` (was pointing to wrong directory)

### Tests
- Rewrote `test_safety.py` (32 tests), `test_handlers.py` (20 tests), `test_session.py` (10 tests), `test_client.py` (11 tests) — previously all `pass` stubs
- Added E2E test suite: `test_e2e_core_analysis.py`, `test_e2e_multithread.py`, `test_e2e_memory.py` (11 tests, skipped when GDB unavailable)
- Added test infrastructure: `conftest.py` with pytest fixtures, `helpers.py` with test utilities

## [0.2.0] - 2026-04-25

### Added
- Multilanguage support (i18n): en, zh-CN, ru — auto-detected from `GDB_CLI_LANG` / `LANG` / `LC_ALL` (#1)
- `target` command: SSH remote debugging via `gdb-cli target --remote HOST:PID`
- `status` now shows elapsed time since session start
- `env-check --gdb-path` option for specifying GDB executable
- Python 3.6.8+ compatibility restored
- `thread-switch` command for switching current thread
- `up`/`down` commands for stack frame navigation
- `sharedlibs` command for viewing loaded shared libraries
- `disasm` command for disassembly

### Changed
- All user-facing error messages now translated via i18n catalog
- License: MIT → Apache 2.0
- Skill renamed to `gdb-cli` for consistency with bunx ecosystem

### Fixed
- Handler thread safety: replaced `gdb.execute()` with Python API
- Commands now execute on Python main thread to avoid GDB concurrency issues
- `sessions` shows GDB process PID instead of target PID in attach mode
- Various lint and CI fixes

### Docs
- DB Core Debugging Skill documentation
- E2E Testing strategy document

## [0.1.0] - 2025-03-21

### Added
- Initial release
- Core dump analysis with symbol resident in memory
- Live attach debugging with non-stop mode support
- Structured JSON output for all commands
- Command whitelist security mechanism
- Heartbeat timeout auto-cleanup
- Session management with idempotency
- SSH remote debugging support
- Multi-language documentation (English, Chinese)

### Commands
- `load` - Load core dump files
- `attach` - Attach to running processes
- `threads` - List threads
- `bt` - Get backtrace
- `eval-cmd` - Evaluate C/C++ expressions
- `eval-element` - Access array/container elements
- `exec` - Execute raw GDB commands
- `thread-apply` - Batch thread operations
- `locals-cmd` - View local variables
- `status` - Check session status
- `sessions` - List active sessions
- `stop` - Stop a session
- `env-check` - Environment validation