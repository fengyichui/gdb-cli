# jlink probe reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (native execution; hardware verification must run in this session). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A second `gdb-cli jlink` start against an already-serving probe reuses the existing server/session instead of spawning a contending duplicate.

**Architecture:** Add pure probe-identity normalization in `jlink.py` (usb serial/nickname → serial via enumeration, ip → host:port). In `jlink_start`, before port allocation, find a running instance on the same probe identity: reuse its live session, reconnect a dead one to the same server, or error on a device conflict. Remove the warn-only `duplicate_probes` path.

**Tech Stack:** Python 3.8+, Click, pytest, ruff. i18n via `t()` (en/zh_cn/ru identical key sets).

**Spec:** `docs/superpowers/specs/2026-11-11-jlink-probe-reuse-design.md`

## Global Constraints

- Fast suite: `.venv/bin/python -m pytest tests -q --ignore=tests/test_e2e_core_analysis.py --ignore=tests/test_e2e_memory.py --ignore=tests/test_e2e_multithread.py`
- Lint: `.venv/bin/ruff check src/gdb_cli tests` (line-length 100, py37 target)
- Locale keys identical across `src/gdb_cli/locales/{en,zh_cn,ru}.py`; new user-facing strings in all three at once.
- `tests/test_jlink.py::TestJLinkCLI` runs under a FakeClick shim; call CLI functions with plain kwargs; `_start_kwargs`/`_call_jlink` dicts must include every option.
- Reuse output mirrors `load`/`attach`/`target`: `status` machine code + `message` locale string.
- One logical change, single commit at the end (user convention). TDD: failing test before production code.
- Hardware: probe serial `69406159` (nickname `LIQIANG1`, OM6628X), `--gdb-path /usr/bin/gdb-multiarch`. Always clean up: `jlink stop --all` + `rm -rf ~/.gdb-cli/{sessions,jlink}` + `pgrep -af JLinkGDBServer`.

## Review Focus

- USB nickname vs serial for the same physical probe must reuse (not duplicate) — Task 1+3.
- `ip=` selects match on host:port and never collide with `usb=` — Task 1+3.
- Enumeration failure (no JLinkExe / probe unplugged) must not crash start; falls back to literal select — Task 1.
- Dead GDB session but live server must reconnect, not orphan or duplicate — Task 3.
- Same probe, different device must error clearly, not silently reuse wrong firmware — Task 3.

## File Structure

- Modify `src/gdb_cli/jlink.py`: add `probe_identity(select, devices=None)` pure helper + `_resolve_probe_identity(select)` enumeration-backed wrapper.
- Modify `src/gdb_cli/cli.py`: import helpers + `_is_session_alive`; add `_find_reusable_instance`, `_reuse_instance_payload`; rewrite reuse section of `jlink_start`; remove `duplicate_probes`.
- Modify `src/gdb_cli/locales/{en,zh_cn,ru}.py`: replace `probe_in_use_warning` with `session_reused_message`, `session_reconnected_message`, `probe_device_conflict`.
- Modify `tests/test_jlink.py`: probe-identity unit tests; replace warn test with reuse/reconnect/conflict/nickname/ip tests.
- Modify `skills/gdb-cli/SKILL.md`, `CHANGELOG.md`: document reuse semantics.

---

### Task 1: Probe identity normalization

**Files:**
- Modify: `src/gdb_cli/jlink.py` (after `validate_select`, ~line 144)
- Test: `tests/test_jlink.py` (module-level, after `test_enumerate_usb_devices_parses_sample_output`)

**Interfaces:**
- Produces: `probe_identity(select: str, devices: Optional[List[dict]] = None) -> str`
  - `usb=<selector>`: if `devices` given and selector matches a `serial` or `nickname` (case-insensitive), return `usb:<serial>`; else return literal `usb=<selector>`.
  - `ip=<host>:<port>`: return `ip:<host>:<port>` (lowercased host).
  - `devices` is the list from `enumerate_usb_devices()` (keys: `serial`, `nickname`).
- Produces: `_resolve_probe_identity(select: str) -> str` — calls `enumerate_usb_devices()` inside try/except `JLinkManagerError`/`Exception`; on failure passes `devices=None` to `probe_identity`.

- [ ] **Step 1: Write failing tests** (module-level in test_jlink.py)

```python
def test_probe_identity_usb_serial_and_nickname_resolve_same():
    devices = [{"serial": "69406159", "nickname": "LIQIANG1"}]
    assert jlink.probe_identity("usb=69406159", devices) == "usb:69406159"
    assert jlink.probe_identity("usb=LIQIANG1", devices) == "usb:69406159"
    assert jlink.probe_identity("usb=liqiang1", devices) == "usb:69406159"

def test_probe_identity_usb_unknown_selector_falls_back_to_literal():
    devices = [{"serial": "69406159", "nickname": "LIQIANG1"}]
    assert jlink.probe_identity("usb=999", devices) == "usb=999"
    assert jlink.probe_identity("usb=999", None) == "usb=999"

def test_probe_identity_ip_normalizes_host_port():
    assert jlink.probe_identity("ip=192.168.0.21:2331") == "ip:192.168.0.21:2331"
    assert jlink.probe_identity("ip=HOST.local:2331") == "ip:host.local:2331"

def test_probe_identity_usb_and_ip_never_collide():
    assert jlink.probe_identity("usb=1") != jlink.probe_identity("ip=1:2331")

def test_resolve_probe_identity_survives_enumeration_failure(monkeypatch):
    def boom(*a, **k):
        raise jlink.JLinkManagerError("no JLinkExe")
    monkeypatch.setattr(jlink, "enumerate_usb_devices", boom)
    assert jlink._resolve_probe_identity("usb=69406159") == "usb=69406159"
```

- [ ] **Step 2: Run, verify FAIL** — `pytest tests/test_jlink.py -k probe_identity -q` → AttributeError (function missing).

- [ ] **Step 3: Implement** `probe_identity` + `_resolve_probe_identity` in jlink.py. Match serial first, then nickname (case-insensitive). IP: split on first `=`, lowercase host portion only (keep port). `_resolve_probe_identity` wraps enumeration in try/except returning `probe_identity(select, None)` on any failure.

- [ ] **Step 4: Run, verify PASS** — `pytest tests/test_jlink.py -k probe_identity -q`.

### Task 2: Locale keys

**Files:**
- Modify: `src/gdb_cli/locales/en.py:248`, `zh_cn.py:243`, `ru.py:250`

**Interfaces:**
- Produces keys: `cli.jlink.session_reused_message`, `cli.jlink.session_reconnected_message`, `cli.jlink.probe_device_conflict` (params: `select`, `device`, `instance_id`, `port`, `existing_device` as needed).
- Removes: `cli.jlink.probe_in_use_warning`.

- [ ] **Step 1:** Replace `probe_in_use_warning` block in all three catalogs with the three new keys. EN: reused="A session for this probe already exists; reusing it", reconnected="The J-Link server is running but its session was gone; reconnected", conflict="Probe {select} is already serving device {existing_device} (instance {instance_id}); stop it before starting device {device}". Translate zh_cn/ru equivalently.
- [ ] **Step 2:** `pytest tests/test_i18n.py -q` → key consistency passes.

### Task 3: Reuse / reconnect / conflict in jlink_start

**Files:**
- Modify: `src/gdb_cli/cli.py` (imports ~27-51; `jlink_start` ~1197-1271; add helpers near `_connect_gdb_session`)
- Test: `tests/test_jlink.py` (replace `test_start_warns_when_probe_already_in_use`; add new tests in TestJLinkCLI)

**Interfaces:**
- Consumes: `jlink.probe_identity`, `jlink._resolve_probe_identity`, `session._is_session_alive`, `get_session`, `_connect_gdb_session(instance, *, binary, gdb_path, timeout, session_id=None, init_cmds=None)`.
- Produces: `_find_reusable_instance(select, device) -> Optional[JLinkInstance]` — iterate `list_instances()`, keep `running` and `probe_identity(existing.select, devices) == probe_identity(select, devices)` (devices resolved once via `_resolve_probe_identity` helper that returns identity; compare identities). Returns first match or None.
- Produces: `_reuse_instance_payload(instance, session_id, status) -> dict` — `{jlink_id, port, device, select, session_id, status, message}`.

- [ ] **Step 1: Write failing tests** (TestJLinkCLI). Replace warn test with:

```python
def test_start_reuses_running_session_on_same_probe(self):
    _FakeClick._context = _FakeContext(invoked_subcommand=None)
    existing = types.SimpleNamespace(
        instance_id="old12345", port=5000, device="D", select="usb=1",
        running=True, session_id="sess1234",
    )
    alive_session = types.SimpleNamespace(session_id="sess1234", gdb_pid=1)
    with patch.object(self.cli, "list_instances", return_value=[existing]), \
         patch.object(self.cli, "_resolve_probe_identity", side_effect=lambda s: s), \
         patch.object(self.cli, "get_session", return_value=alive_session), \
         patch.object(self.cli, "_is_session_alive", return_value=True), \
         patch.object(self.cli, "start_gdbserver") as mock_start, \
         patch.object(self.cli, "print_json") as mock_print:
        self._call_jlink()
    mock_start.assert_not_called()
    payload = mock_print.call_args.args[0]
    assert payload["status"] == "reused"
    assert payload["session_id"] == "sess1234"
    assert payload["jlink_id"] == "old12345"

def test_start_errors_on_device_conflict(self):
    _FakeClick._context = _FakeContext(invoked_subcommand=None)
    existing = types.SimpleNamespace(
        instance_id="old12345", port=5000, device="OTHER", select="usb=1",
        running=True, session_id="sess1234",
    )
    with patch.object(self.cli, "list_instances", return_value=[existing]), \
         patch.object(self.cli, "_resolve_probe_identity", side_effect=lambda s: s), \
         patch.object(self.cli, "start_gdbserver") as mock_start, \
         patch.object(self.cli, "print_error") as mock_error:
        with pytest.raises(self.cli.click.exceptions.Exit) as exc:
            self._call_jlink(device="D")
    assert exc.value.exit_code == 1
    mock_start.assert_not_called()
    assert "OTHER" in mock_error.call_args.args[0]

def test_start_reconnects_when_session_dead_but_server_running(self):
    _FakeClick._context = _FakeContext(invoked_subcommand=None)
    existing = types.SimpleNamespace(
        instance_id="old12345", port=5000, device="D", select="usb=1",
        running=True, session_id="deadsess",
        session_config={"binary": None, "gdb_path": "gdb", "timeout": 600,
                        "init_cmds": []},
    )
    with patch.object(self.cli, "list_instances", return_value=[existing]), \
         patch.object(self.cli, "_resolve_probe_identity", side_effect=lambda s: s), \
         patch.object(self.cli, "get_session", return_value=None), \
         patch.object(self.cli, "start_gdbserver") as mock_start, \
         patch.object(self.cli, "_connect_gdb_session", return_value="newsess") as mock_conn, \
         patch.object(self.cli, "print_json") as mock_print:
        self._call_jlink()
    mock_start.assert_not_called()
    mock_conn.assert_called_once()
    payload = mock_print.call_args.args[0]
    assert payload["status"] == "reconnected"
    assert payload["session_id"] == "newsess"
    assert payload["jlink_id"] == "old12345"

def test_start_reuses_usb_nickname_matching_serial(self):
    _FakeClick._context = _FakeContext(invoked_subcommand=None)
    existing = types.SimpleNamespace(
        instance_id="old12345", port=5000, device="D", select="usb=69406159",
        running=True, session_id="sess1234",
    )
    alive = types.SimpleNamespace(session_id="sess1234", gdb_pid=1)
    devices = [{"serial": "69406159", "nickname": "LIQIANG1"}]
    with patch.object(self.cli, "list_instances", return_value=[existing]), \
         patch.object(self.cli, "enumerate_usb_devices", return_value=devices), \
         patch.object(self.cli, "get_session", return_value=alive), \
         patch.object(self.cli, "_is_session_alive", return_value=True), \
         patch.object(self.cli, "start_gdbserver") as mock_start, \
         patch.object(self.cli, "print_json") as mock_print:
        self._call_jlink(select="usb=LIQIANG1")
    mock_start.assert_not_called()
    assert mock_print.call_args.args[0]["status"] == "reused"
```

Note: `_resolve_probe_identity` must be imported into cli namespace so `patch.object(self.cli, ...)` works; the nickname test patches `enumerate_usb_devices` instead and exercises the real resolver.

- [ ] **Step 2: Run, verify FAIL** — reuse test fails (status "started", start_gdbserver called).

- [ ] **Step 3: Implement** in cli.py:
  - Import `probe_identity`, `_resolve_probe_identity` from `.jlink`; `_is_session_alive` from `.session`.
  - `_find_reusable_instance(select, device)`: resolve `identity = _resolve_probe_identity(select)` once; for each running instance compare `_resolve_probe_identity(existing.select) == identity`; return first match.
  - In `jlink_start`, after validation, before `find_free_port`: `match = _find_reusable_instance(select, device)`. If match and `match.device != device` → `print_error(t("cli.jlink.probe_device_conflict", ...))`, Exit(1). If match: `sess = get_session(match.session_id) if match.session_id else None`; if sess and `_is_session_alive(sess)` → print reuse payload, return. Else reconnect: `_connect_gdb_session(match, binary=cfg.get("binary"), gdb_path=cfg.get("gdb_path") or "gdb", timeout=cfg.get("timeout",600), init_cmds=cfg.get("init_cmds") or [])` wrapped in try/except like the start path; print reconnected payload, return.
  - Remove `duplicate_probes` list and the `payload["warning"]` block.

- [ ] **Step 4: Run, verify PASS** — `pytest tests/test_jlink.py -q`.

### Task 4: Full verification + docs + commit

- [ ] **Step 1:** Fast suite + ruff green.
- [ ] **Step 2:** Hardware: clean state; start probe (serial) → record jlink_id/session_id; second start (serial) → assert `status:reused`, same ids, `jlink status` shows ONE instance; second start (nickname LIQIANG1) → reused. Stop+start to test reconnect path if feasible. Clean up; `pgrep -af JLinkGDBServer` empty.
- [ ] **Step 3:** Update SKILL.md (reuse semantics: second start reuses; device conflict errors; restart for config changes) + CHANGELOG 0.5.0 entry.
- [ ] **Step 4:** Single commit `feat(jlink): reuse existing session when probe already served` with hardware verification in body.