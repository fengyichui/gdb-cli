# AGENTS.md

## Commands

```bash
# Fast unit test suite (excludes real-GDB e2e; the standard dev loop)
.venv/bin/python -m pytest tests -q \
  --ignore=tests/test_e2e_core_analysis.py \
  --ignore=tests/test_e2e_memory.py \
  --ignore=tests/test_e2e_multithread.py

# Single file / single test
.venv/bin/python -m pytest tests/test_jlink.py -q
.venv/bin/python -m pytest tests/test_jlink.py::TestJLinkCLI::test_default_subcommand_invokes_start -q

# Lint (ruff; config in pyproject.toml, line-length 100, target py37)
.venv/bin/ruff check src/gdb_cli tests
```

CI (`.github/workflows/ci.yml`) runs `ruff check src/ tests/` then `pytest tests/` on Python 3.8–3.12. Publishing is triggered by a GitHub release (`publish.yml`).

## Test suite quirks

- The three `test_e2e_*.py` files need real GDB (Python-enabled) plus a compiled crash binary; they self-skip when unavailable. They are slow — exclude them for the normal loop (command above).
- `tests/test_handlers.py` and other GDB-side tests work by injecting `sys.modules['gdb'] = MagicMock()` **at import time, before importing `gdb_cli.gdb_server.handlers`**, and setting `GDB_CLI_SERVER_DIR` to `src/gdb_cli/gdb_server`. If a test needs real behavior, it must reload the handlers module after reconfiguring the mock.
- `tests/test_cli_async.py` and `tests/test_jlink.py` (class `TestJLinkCLI`) import `gdb_cli.cli` under a `_FakeClick` shim (`sys.modules["click"] = _FakeClick()`), so Click decorators are inert. CLI functions are then called directly with plain kwargs; adding a new Click option means updating every direct call site and the `_start_kwargs`/`_call_jlink` dicts in tests.
- i18n: all three locale catalogs (`src/gdb_cli/locales/{en,zh_cn,ru}.py`) must have identical key sets — `tests/test_i18n.py::test_key_consistency` enforces it, and a separate test scans `cli.py` for `t("...")` calls. Any new user-facing string needs all three languages at once.

## Architecture

- `src/gdb_cli/cli.py` — Click entry point; `gdb-cli` script targets `cli:main`.
- `src/gdb_cli/launcher.py` — spawns GDB with `-ex` commands; the RPC server script (`gdb_server/gdb_rpc_server.py`) is injected via `source <script>` + `python start_server(...)` with session meta serialized into the command line. GDB's `-ex` does no shell quoting — `source`, `set sysroot`, `target remote` consume the rest of the line literally (do not quote), while `file`/`core-file`/`directory` strip quotes. Regression tests in `tests/test_launcher_commands.py` pin this.
- `src/gdb_cli/gdb_server/` — code that runs *inside* GDB's Python. It is loaded via `importlib.util.spec_from_file_location` (no package imports); `GDB_CLI_SERVER_DIR` env var locates it when `__file__` is unavailable.
- `src/gdb_cli/jlink.py` — JLinkGDBServer process manager: instances persisted as JSON in `~/.gdb-cli/jlink/`, sessions in `~/.gdb-cli/sessions/`. `stop_instance` validates `/proc/<pid>/stat` starttime before signalling (PID-reuse safety) — preserve this pattern when touching kill paths.
- `src/gdb_cli/session.py` — `SessionMeta` dataclass persisted to disk; `from_dict` deliberately drops unknown fields for forward/backward compatibility.
- No command whitelist/safety layer exists (removed in 0.5.0); `exec` passes commands to GDB unfiltered by design.

## Conventions

- Locale keys follow `cli.<command>.<field>_help` / `cli.<command>.doc`. The `jlink` help epilog is a module-level constant shared verbatim by `jlink --help` and `jlink start --help` — keep both pointing at the same object in all three locale files.
- User-facing messages go through `t()` (i18n); code comments are a mix of Chinese and English — follow the surrounding file.
- Commit style: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`), one logical change per commit, hardware verification described in the body when applicable.
- `docs/superpowers/` holds local working artifacts (brainstorming specs, implementation plans). Keep them on disk for reference, but leave them out of git: the directory is gitignored and untracked. Stage feature changes explicitly; never `git add` this directory.
- Remotes: `origin` = upstream `Cerdore/gdb-cli`, `mygithub` = fork `fengyichui/gdb-cli`. Work happens on local `main`.
- When changing jlink/CLI options, also update `skills/gdb-cli/SKILL.md` and `skills/gdb-cli/evals/evals.json` (agent-facing docs) in the same change.

## Hardware verification context (when a J-Link probe is attached)

- Current test device: probe serial `1057771304` (nickname `nRF54L15DK2`, J-Link OB-nRF5340-NordicSemi) → nRF54L15DK, Zephyr firmware at `/home/liqiang/github/nRFConnectSDK/build/hci_uart_zephyr_sdc/zephyr/zephyr.elf` (device name `nRF54L15_M33`, `--rtos Zephyr`). Do NOT use the LIQIANG1/OM6628X probe for new experiments.
- Use `--gdb-path /usr/bin/gdb-multiarch` (host `gdb` lacks ARM support). RTOS thread awareness: `--rtos <name>`; tasks only enumerate after the scheduler has run. Per-task `bt` tail frames at `0xa5a5a5a4` ("corrupt stack?") on FreeRTOS targets are `0xA5` stack fill, not real corruption.
- Always clean up: `gdb-cli jlink stop --all` and `rm -rf ~/.gdb-cli/{sessions,jlink}` after experiments; verify with `pgrep -af JLinkGDBServer`.
