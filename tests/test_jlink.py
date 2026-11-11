"""Tests for the J-Link GDB Server process manager and CLI command group."""

import importlib
import json
import signal
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch

import pytest
from click.core import ParameterSource

from gdb_cli import jlink

# ---------------------------------------------------------------------------
# Task 1: process manager unit tests
# ---------------------------------------------------------------------------

def _make_instance(jlink_dir, **overrides):
    values = {
        "instance_id": "abcd1234",
        "cmdline": [
            "JLinkGDBServer", "-nogui", "-if", "SWD", "-device", "D",
            "-select", "usb=1", "-port", "2331",
        ],
        "port": 2331,
        "device": "D",
        "select": "usb=1",
        "pid": 4242,
        "start_time": "111",
        "log_path": str(jlink_dir / "abcd1234.log"),
        "started_at": time.time(),
        "extra": {},
    }
    values.update(overrides)
    instance = jlink.JLinkInstance(**values)
    jlink._save_instance(instance)
    return instance


@pytest.fixture
def jlink_dir(tmp_path, monkeypatch):
    directory = tmp_path / "jlink"
    monkeypatch.setattr(jlink, "JLINK_DIR", directory)
    return directory


def _value_after(cmdline, option):
    return cmdline[cmdline.index(option) + 1]


def test_build_cmdline_forced_defaults_and_options():
    cmdline = jlink.build_gdbserver_cmdline(
        device="D", select="usb=123", port=2331, extra_args=[]
    )

    assert cmdline[0] == "JLinkGDBServer"
    assert cmdline[1:10] == [
        "-nogui", "-if", "SWD", "-nolocalhostonly", "-halt",
        "-nosilent", "-vd", "-noir", "-notimeout",
    ]
    assert _value_after(cmdline, "-device") == "D"
    assert _value_after(cmdline, "-select") == "usb=123"
    assert _value_after(cmdline, "-port") == "2331"
    assert "-speed" not in cmdline


def test_build_cmdline_speed_interface_and_extra_args():
    cmdline = jlink.build_gdbserver_cmdline(
        device="D",
        select="usb=nick",
        port=2400,
        speed="4000",
        interface="JTAG",
        rtos="FreeRTOS",
        extra_args=["-jlinkscriptfile", "f.jlink"],
    )

    assert _value_after(cmdline, "-if") == "JTAG"
    assert _value_after(cmdline, "-speed") == "4000"
    assert _value_after(cmdline, "-rtos") == "GDBServer/RTOSPlugin_FreeRTOS"
    assert cmdline[-2:] == ["-jlinkscriptfile", "f.jlink"]


def test_build_cmdline_custom_executable():
    cmdline = jlink.build_gdbserver_cmdline(
        device="D", select="usb=1", port=2331, extra_args=[],
        jlink_exe="/opt/JLink/JLinkGDBServer",
    )
    assert cmdline[0] == "/opt/JLink/JLinkGDBServer"


def test_build_cmdline_rtos_prefixes_plugin_path():
    cmdline = jlink.build_gdbserver_cmdline(
        device="D", select="usb=1", port=2331, rtos="embOS", extra_args=[],
    )
    assert _value_after(cmdline, "-rtos") == "GDBServer/RTOSPlugin_embOS"


@pytest.mark.parametrize(
    "rtos",
    [
        "FreeRTOS/../x", "GDBServer/RTOSPlugin_FreeRTOS",
        "Free RTOS", "FreeRTOS\n", "-FreeRTOS",
    ],
)
def test_build_cmdline_rejects_invalid_rtos_name(rtos):
    with pytest.raises(jlink.JLinkManagerError):
        jlink.build_gdbserver_cmdline(
            device="D", select="usb=1", port=2331, rtos=rtos, extra_args=[],
        )


@pytest.mark.parametrize("rtos", ["", None])
def test_build_cmdline_blank_rtos_means_disabled(rtos):
    cmdline = jlink.build_gdbserver_cmdline(
        device="D", select="usb=1", port=2331, rtos=rtos, extra_args=[],
    )
    assert "-rtos" not in cmdline


@pytest.mark.parametrize("token", ["-select", "-gui", "-nogui", "-port", "-device", "-if", "-rtos"])
def test_build_cmdline_rejects_protected_extra_args(token):
    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.build_gdbserver_cmdline(
            device="D", select="usb=1", port=2331, extra_args=[token, "x"],
        )
    assert token in str(excinfo.value)


def test_build_cmdline_allows_unprotected_extra_args():
    cmdline = jlink.build_gdbserver_cmdline(
        device="D", select="usb=1", port=2331,
        extra_args=["-swoport", "19021", "-jlinkscriptfile", "a.jlink"],
    )
    assert "-swoport" in cmdline
    assert "-jlinkscriptfile" in cmdline


def test_build_cmdline_revalidates_select():
    with pytest.raises(jlink.JLinkManagerError):
        jlink.build_gdbserver_cmdline(
            device="D", select="foo", port=2331, extra_args=[],
        )


@pytest.mark.parametrize("port", [0, -1, 65536, 70000])
def test_build_cmdline_rejects_invalid_port(port):
    with pytest.raises(jlink.JLinkManagerError):
        jlink.build_gdbserver_cmdline(
            device="D", select="usb=1", port=port, extra_args=[],
        )


@pytest.mark.parametrize(
    "select",
    [
        "usb", "ip", "usb=", "ip=", "", "ip=no-port",
        "usb=*", "USB=123", "foo", "123", "usb= 123", "usb=12 3",
        "ip=host:0", "ip=host:65536", "ip=host:abc", "ip=:123",
        "ip=host:", "ip=host", "ip=host:12 3", "usb=1\nusb=2",
    ],
)
def test_validate_select_rejects_invalid(select):
    with pytest.raises(jlink.JLinkManagerError):
        jlink.validate_select(select)


def test_validate_select_usb_without_selector_mentions_devices():
    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.validate_select("usb")
    assert "gdb-cli jlink devices" in str(excinfo.value)


def test_validate_select_ip_without_port_mentions_form():
    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.validate_select("ip")
    assert "ip=HOST:PORT" in str(excinfo.value)


@pytest.mark.parametrize(
    "select", ["usb=123", "usb=昵称", "ip=172.25.176.1:19025", "usb=nRF54L15DK"]
)
def test_validate_select_accepts_valid(select):
    assert jlink.validate_select(select) == select


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" usb=123 ", "usb=123"),
        ("\tusb=nRF54L15DK", "usb=nRF54L15DK"),
        ("  ip=10.0.0.1:2331  ", "ip=10.0.0.1:2331"),
    ],
)
def test_validate_select_strips_and_returns_normalized(raw, expected):
    assert jlink.validate_select(raw) == expected


def test_validate_select_unknown_prefix_names_value():
    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.validate_select("USB=123")
    assert "USB=123" in str(excinfo.value)
    assert "usb=" in str(excinfo.value)


def test_find_free_port_returns_bound_port(monkeypatch):
    sock = types.SimpleNamespace(
        bound=None,
        closed=False,
    )

    def fake_bind(address):
        sock.bound = address

    def fake_getsockname():
        return ("0.0.0.0", 45678)

    sock.bind = fake_bind
    sock.getsockname = fake_getsockname
    sock.close = lambda: setattr(sock, "closed", True)

    monkeypatch.setattr(jlink.socket, "socket", lambda *a, **k: sock)

    assert jlink.find_free_port() == 45678
    assert sock.bound == ("", 0)
    assert sock.closed is True


def test_start_gdbserver_ready_persists_instance(jlink_dir, tmp_path, monkeypatch):
    process = Mock()
    process.pid = 4242
    process.poll.return_value = None
    popen = Mock(return_value=process)
    monkeypatch.setattr(jlink.subprocess, "Popen", popen)
    probes = []

    def fake_port_open(host, port):
        probes.append((host, port))
        # First probe is the pre-spawn "is it busy?" check; later probes are
        # readiness checks and succeed.
        return len(probes) > 1

    monkeypatch.setattr(jlink, "_port_open", fake_port_open)
    monkeypatch.setattr(jlink, "_read_proc_starttime", lambda pid: "777")

    log_path = tmp_path / "server.log"
    instance = jlink.start_gdbserver(
        ["JLinkGDBServer", "-device", "D", "-select", "usb=1", "-port", "2331"],
        str(log_path),
    )

    assert instance.pid == 4242
    assert instance.start_time == "777"
    assert instance.port == 2331
    assert instance.device == "D"
    assert instance.select == "usb=1"

    kwargs = popen.call_args.kwargs
    assert kwargs["start_new_session"] is True

    files = list(jlink_dir.glob("*.json"))
    assert len(files) == 1
    stored = json.loads(files[0].read_text(encoding="utf-8"))
    assert stored["instance_id"] == instance.instance_id
    assert stored["port"] == 2331
    assert stored["start_time"] == "777"


def test_start_gdbserver_premature_exit_reports_log_tail(jlink_dir, tmp_path, monkeypatch):
    log_path = tmp_path / "server.log"
    log_path.write_text(
        "\n".join(f"line{i}" for i in range(20)), encoding="utf-8"
    )

    process = Mock()
    process.pid = 4242
    process.poll.return_value = 1
    monkeypatch.setattr(jlink.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(jlink, "_port_open", lambda host, port: False)

    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.start_gdbserver(
            ["JLinkGDBServer", "-device", "WRONG", "-select", "usb=1", "-port", "2331"],
            str(log_path),
        )

    message = str(excinfo.value)
    assert "line19" in message
    assert "line5" in message
    assert "line4" not in message
    assert list(jlink_dir.glob("*.json")) == []


def test_start_gdbserver_rejects_busy_port(jlink_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(jlink, "_port_open", lambda host, port: True)
    popen = Mock()
    monkeypatch.setattr(jlink.subprocess, "Popen", popen)

    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.start_gdbserver(
            ["JLinkGDBServer", "-device", "D", "-select", "usb=1", "-port", "2331"],
            str(tmp_path / "server.log"),
        )

    assert "2331" in str(excinfo.value)
    popen.assert_not_called()


def test_start_gdbserver_rechecks_process_after_port_ready(
    jlink_dir, tmp_path, monkeypatch
):
    log_path = tmp_path / "server.log"
    log_path.write_text("server died\n", encoding="utf-8")

    process = Mock()
    process.pid = 4242
    # First poll: alive while waiting; second poll (after port ready): dead.
    process.poll.side_effect = [None, 1]
    monkeypatch.setattr(jlink.subprocess, "Popen", Mock(return_value=process))
    probes = []

    def fake_port_open(host, port):
        probes.append((host, port))
        return len(probes) > 1

    monkeypatch.setattr(jlink, "_port_open", fake_port_open)

    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.start_gdbserver(
            ["JLinkGDBServer", "-device", "D", "-select", "usb=1", "-port", "2331"],
            str(log_path),
        )

    assert "server died" in str(excinfo.value)
    assert list(jlink_dir.glob("*.json")) == []


def test_terminate_process_escalates_to_kill():
    process = Mock()
    process.wait.side_effect = [
        jlink.subprocess.TimeoutExpired("proc", 5),
        None,
    ]

    assert jlink._terminate_process(process) is True
    process.terminate.assert_called_once()
    process.kill.assert_called_once()


def test_terminate_process_reports_survivor():
    process = Mock()
    process.wait.side_effect = [
        jlink.subprocess.TimeoutExpired("proc", 5),
        jlink.subprocess.TimeoutExpired("proc", 1),
    ]
    process.poll.return_value = None

    assert jlink._terminate_process(process) is False


def test_save_instance_is_atomic_and_round_trips(jlink_dir):
    _make_instance(jlink_dir, instance_id="atom0001")
    loaded = jlink.get_instance("atom0001")

    assert loaded.instance_id == "atom0001"
    assert loaded.session_id is None
    assert loaded.session_config == {}
    stored = json.loads((jlink_dir / "atom0001.json").read_text(encoding="utf-8"))
    assert stored["session_id"] is None
    # No temp files left behind.
    assert list(jlink_dir.glob("*.tmp")) == []


def test_stop_instance_mismatched_starttime_never_signals(jlink_dir, monkeypatch):
    _make_instance(jlink_dir)
    monkeypatch.setattr(jlink, "_read_proc_starttime", lambda pid: "999")
    kill = Mock()
    monkeypatch.setattr(jlink.os, "kill", kill)

    result = jlink.stop_instance("abcd1234")

    kill.assert_not_called()
    assert not (jlink_dir / "abcd1234.json").exists()
    assert result["killed"] is False


def test_stop_instance_matching_starttime_kills(jlink_dir, monkeypatch):
    _make_instance(jlink_dir)
    monkeypatch.setattr(jlink, "_read_proc_starttime", lambda pid: "111")
    kill = Mock(side_effect=[None, OSError()])
    monkeypatch.setattr(jlink.os, "kill", kill)
    monkeypatch.setattr(jlink.time, "sleep", lambda seconds: None)

    result = jlink.stop_instance("abcd1234")

    kill.assert_any_call(4242, signal.SIGTERM)
    assert (jlink_dir / "abcd1234.json").exists() is False
    assert result["killed"] is True


def test_stop_instance_reports_stop_failed_when_survivor(jlink_dir, monkeypatch):
    _make_instance(jlink_dir)
    monkeypatch.setattr(jlink, "_read_proc_starttime", lambda pid: "111")
    monkeypatch.setattr(jlink.os, "kill", Mock())
    monkeypatch.setattr(jlink, "_wait_process_exit", lambda pid, timeout=5.0: False)

    result = jlink.stop_instance("abcd1234")

    assert result["status"] == "stop_failed"
    # Metadata is kept so the user can retry / inspect the log.
    assert (jlink_dir / "abcd1234.json").exists()


def test_stop_instance_confirmed_kill_removes_log(jlink_dir, monkeypatch):
    instance = _make_instance(jlink_dir)
    (jlink_dir / "abcd1234.log").write_text("log", encoding="utf-8")
    monkeypatch.setattr(jlink, "_read_proc_starttime", lambda pid: "111")
    monkeypatch.setattr(jlink.os, "kill", Mock(side_effect=[None, OSError()]))

    result = jlink.stop_instance("abcd1234")

    assert result["status"] == "stopped"
    assert not (jlink_dir / "abcd1234.log").exists()
    assert not (jlink_dir / "abcd1234.json").exists()
    assert instance is not None


def test_list_instances_includes_running_flag(jlink_dir, monkeypatch):
    _make_instance(jlink_dir, instance_id="aaaa1111", pid=1001, start_time="111")
    _make_instance(jlink_dir, instance_id="bbbb2222", pid=1002, start_time="111")

    def fake_starttime(pid):
        return "111" if pid == 1001 else "999"

    monkeypatch.setattr(jlink, "_read_proc_starttime", fake_starttime)
    states = {i.instance_id: i.running for i in jlink.list_instances()}

    assert states == {"aaaa1111": True, "bbbb2222": False}


def test_stop_instance_missing_metadata_errors(jlink_dir):
    with pytest.raises(jlink.JLinkManagerError):
        jlink.stop_instance("nope")


def test_list_and_get_instances(jlink_dir):
    _make_instance(jlink_dir, instance_id="aaaaaaaa")
    _make_instance(jlink_dir, instance_id="bbbbbbbb")

    instances = jlink.list_instances()
    assert {instance.instance_id for instance in instances} == {"aaaaaaaa", "bbbbbbbb"}
    assert jlink.get_instance("aaaaaaaa").instance_id == "aaaaaaaa"
    assert jlink.get_instance("missing") is None


def test_restart_instance_reuses_id_and_cmdline(jlink_dir, monkeypatch):
    original = _make_instance(jlink_dir)
    stop = Mock(return_value={"jlink_id": original.instance_id, "killed": True})

    def fake_start(cmdline, log_path, *, wait_timeout=15.0, instance_id=None):
        assert cmdline == original.cmdline
        assert log_path == original.log_path
        assert instance_id == original.instance_id
        return _make_instance(jlink_dir, start_time="222")

    monkeypatch.setattr(jlink, "stop_instance", stop)
    monkeypatch.setattr(jlink, "start_gdbserver", fake_start)

    restarted = jlink.restart_instance("abcd1234")

    stop.assert_called_once_with("abcd1234")
    assert restarted.instance_id == "abcd1234"
    assert restarted.start_time == "222"


def test_enumerate_usb_devices_parses_sample_output(monkeypatch):
    sample = (
        "SEGGER J-Link Commander V8.88\n"
        "J-Link[0]: Connection: USB, Serial number: 1057723511, "
        "ProductName: J-Link OB-nRF5340-NordicSemi, Nickname: nRF54L15DK\n"
    )
    completed = Mock(returncode=0, stdout=sample, stderr="")
    run = Mock(return_value=completed)
    monkeypatch.setattr(jlink.subprocess, "run", run)

    devices = jlink.enumerate_usb_devices()

    assert devices == [{
        "index": 0,
        "connection": "USB",
        "serial": "1057723511",
        "product": "J-Link OB-nRF5340-NordicSemi",
        "nickname": "nRF54L15DK",
    }]
    args = run.call_args.args[0]
    assert args[0] == "JLinkExe"
    assert run.call_args.kwargs["input"] == "ShowEmuList\nexit\n"


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


# ---------------------------------------------------------------------------
# Task 2: CLI command group tests (FakeClick pattern from test_cli_async)
# ---------------------------------------------------------------------------

class _FakeContext:
    def __init__(self, invoked_subcommand=None):
        self.invoked_subcommand = invoked_subcommand
        self.help_text = "jlink help"
        self.invoked = []

    def invoke(self, command, **kwargs):
        self.invoked.append((command, kwargs))
        return command(**kwargs)

    def get_help(self):
        return self.help_text


class _FakeGroup:
    def __init__(self, func):
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def command(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def group(self, *args, **kwargs):
        def decorator(func):
            return _FakeGroup(func)
        return decorator


class _FakeClick(types.SimpleNamespace):
    _context = None

    class ClickException(Exception):
        pass

    class exceptions:
        class Exit(Exception):
            def __init__(self, code=0):
                super().__init__(code)
                self.exit_code = code

    @staticmethod
    def group(*args, **kwargs):
        def decorator(func):
            return _FakeGroup(func)
        return decorator

    @staticmethod
    def get_current_context():
        return _FakeClick._context

    @staticmethod
    def version_option(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    @staticmethod
    def option(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    @staticmethod
    def IntRange(min=None, max=None):
        return int

    @staticmethod
    def argument(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    @staticmethod
    def Choice(values):
        return values

    @staticmethod
    def echo(*args, **kwargs):
        return None


class TestJLinkCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        saved_click = sys.modules.get("click")
        sys.modules["click"] = _FakeClick()
        try:
            sys.modules.pop("gdb_cli.cli", None)
            cls.cli = importlib.import_module("gdb_cli.cli")
        finally:
            if saved_click is not None:
                sys.modules["click"] = saved_click
            else:
                sys.modules.pop("click", None)

    def _instance(self):
        return types.SimpleNamespace(
            instance_id="abcd1234",
            port=2331,
            device="D",
            select="usb=1",
            session_id=None,
            session_config={},
            cmdline=[
                "JLinkGDBServer", "-nogui", "-device", "D",
                "-select", "usb=1", "-port", "2331",
            ],
            log_path="/tmp/abcd1234.log",
        )

    def _call_jlink(self, **overrides):
        values = {
            "device": "D",
            "select": "usb=1",
            "binary": None,
            "gdb_path": "gdb",
            "jlink_path": "JLinkGDBServer",
            "speed": None,
            "rtos": None,
            "interface": "SWD",
            "port": 2331,
            "timeout": 600,
            "init_cmds": (),
            "extra_args": (),
        }
        values.update(overrides)
        return self.cli.jlink(**values)

    def test_default_subcommand_invokes_start(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx
        fake_process = types.SimpleNamespace(
            session=types.SimpleNamespace(
                session_id="sess1234", sock_path="/tmp/fake.sock"
            )
        )

        with patch.object(self.cli, "start_gdbserver", return_value=self._instance()) as mock_start, \
             patch.object(self.cli, "launch_target", return_value=fake_process) as mock_launch, \
             patch.object(self.cli, "_wait_session_ready",
                          return_value={"state": "ready"}), \
             patch.object(self.cli, "_save_instance"), \
             patch.object(self.cli, "print_json") as mock_print:
            self._call_jlink()

        assert len(ctx.invoked) == 1
        mock_start.assert_called_once()
        launch_kwargs = mock_launch.call_args.kwargs
        assert launch_kwargs["remote"] == "127.0.0.1:2331"
        payload = mock_print.call_args.args[0]
        assert payload["status"] == "started"
        assert payload["jlink_id"] == "abcd1234"
        assert payload["session_id"] == "sess1234"

    def test_init_cmds_are_executed_after_connect(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx
        fake_process = types.SimpleNamespace(
            session=types.SimpleNamespace(
                session_id="sess1234", sock_path="/tmp/fake.sock"
            )
        )

        with patch.object(self.cli, "start_gdbserver",
                          return_value=self._instance()), \
             patch.object(self.cli, "launch_target", return_value=fake_process), \
             patch.object(self.cli, "_wait_session_ready",
                          return_value={"state": "ready"}), \
             patch.object(self.cli, "_run_init_cmds", return_value=[]) as mock_init, \
             patch.object(self.cli, "_save_instance"), \
             patch.object(self.cli, "print_json"):
            self._call_jlink()

        mock_init.assert_called_once()
        # Default device configuration is applied even without --init-cmd...
        assert mock_init.call_args.args[1] == self.cli._DEFAULT_JLINK_INIT_CMDS

    def test_user_init_cmds_run_after_defaults(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx
        fake_process = types.SimpleNamespace(
            session=types.SimpleNamespace(
                session_id="sess1234", sock_path="/tmp/fake.sock"
            )
        )

        with patch.object(self.cli, "start_gdbserver",
                          return_value=self._instance()), \
             patch.object(self.cli, "launch_target", return_value=fake_process), \
             patch.object(self.cli, "_wait_session_ready",
                          return_value={"state": "ready"}), \
             patch.object(self.cli, "_run_init_cmds", return_value=[]) as mock_init, \
             patch.object(self.cli, "_save_instance"), \
             patch.object(self.cli, "print_json"):
            self._call_jlink(init_cmds=("monitor exec SetRTTTelnetPort = 1234",))

        mock_init.assert_called_once()
        # ...and user commands run after the defaults, in order.
        assert mock_init.call_args.args[1] == (
            self.cli._DEFAULT_JLINK_INIT_CMDS
            + ["monitor exec SetRTTTelnetPort = 1234"]
        )

    def test_rtos_option_injects_plugin_path(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx
        fake_process = types.SimpleNamespace(
            session=types.SimpleNamespace(
                session_id="sess1234", sock_path="/tmp/fake.sock"
            )
        )

        with patch.object(self.cli, "start_gdbserver",
                          return_value=self._instance()) as mock_start, \
             patch.object(self.cli, "launch_target", return_value=fake_process), \
             patch.object(self.cli, "_wait_session_ready",
                          return_value={"state": "ready"}), \
             patch.object(self.cli, "_save_instance"), \
             patch.object(self.cli, "print_json"):
            self._call_jlink(rtos="FreeRTOS")

        cmdline = mock_start.call_args.args[0]
        assert _value_after(cmdline, "-rtos") == (
            "GDBServer/RTOSPlugin_FreeRTOS"
        )

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

    def test_invalid_rtos_name_exits_before_start(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx

        with patch.object(self.cli, "start_gdbserver") as mock_start, \
             patch.object(self.cli, "print_error") as mock_error:
            with pytest.raises(self.cli.click.exceptions.Exit) as excinfo:
                self._call_jlink(rtos="../FreeRTOS")

        assert excinfo.value.exit_code == 1
        mock_start.assert_not_called()
        assert "RTOS" in mock_error.call_args.args[0]

    def test_usb_without_selector_errors_and_mentions_devices(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx

        with patch.object(self.cli, "start_gdbserver") as mock_start, \
             patch.object(self.cli, "print_error") as mock_error:
            with pytest.raises(self.cli.click.exceptions.Exit) as excinfo:
                self._call_jlink(select="usb")

        assert excinfo.value.exit_code == 1
        mock_start.assert_not_called()
        assert "gdb-cli jlink devices" in mock_error.call_args.args[0]

    def test_explicit_busy_port_errors(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx

        with patch.object(self.cli, "start_gdbserver") as mock_start, \
             patch.object(self.cli, "print_error") as mock_error:
            mock_start.side_effect = self.cli.JLinkManagerError("Port 2331 is already in use")
            with pytest.raises(self.cli.click.exceptions.Exit) as excinfo:
                self._call_jlink()

        assert excinfo.value.exit_code == 1
        mock_error.assert_called_once()

    def test_launch_target_failure_stops_gdbserver_and_exits(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx

        with patch.object(self.cli, "start_gdbserver", return_value=self._instance()), \
             patch.object(self.cli, "launch_target",
                          side_effect=self.cli.GDBLauncherError("boom")), \
             patch.object(self.cli, "stop_instance") as mock_stop, \
             patch.object(self.cli, "print_error") as mock_error:
            with pytest.raises(self.cli.click.exceptions.Exit) as excinfo:
                self._call_jlink()

        assert excinfo.value.exit_code == 1
        mock_stop.assert_called_once_with("abcd1234")
        mock_error.assert_called_once()

    def test_subcommand_present_does_not_default_to_start(self):
        ctx = _FakeContext(invoked_subcommand="status")
        _FakeClick._context = ctx

        with patch.object(self.cli, "jlink_start") as mock_start:
            self._call_jlink()

        mock_start.assert_not_called()


# ---------------------------------------------------------------------------
# Task 3: session lifecycle, option scoping and stop hardening (pytest style)
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_module():
    """Import ``gdb_cli.cli`` with the FakeClick shim (several tests need it)."""
    saved_click = sys.modules.get("click")
    sys.modules["click"] = _FakeClick()
    try:
        sys.modules.pop("gdb_cli.cli", None)
        module = importlib.import_module("gdb_cli.cli")
        yield module
    finally:
        if saved_click is not None:
            sys.modules["click"] = saved_click
        else:
            sys.modules.pop("click", None)


class _ParamCtx:
    def __init__(self, params, sources=None, parent=None):
        self.params = params
        self.sources = sources or {}
        self.parent = parent

    def get_parameter_source(self, name):
        return self.sources.get(name)


def _start_kwargs(**overrides):
    values = {
        "device": "D",
        "select": "usb=1",
        "binary": None,
        "gdb_path": "gdb",
        "jlink_path": "JLinkGDBServer",
        "speed": None,
        "rtos": None,
        "interface": "SWD",
        "port": 2331,
        "timeout": 600,
        "init_cmds": (),
        "extra_args": (),
    }
    values.update(overrides)
    return values


def test_merge_group_params_subcommand_commandline_wins(cli_module):
    parent = _ParamCtx(
        {"device": "group-device"},
        {"device": ParameterSource.COMMANDLINE},
    )
    ctx = _ParamCtx(
        {"device": "sub-device"},
        {"device": ParameterSource.COMMANDLINE},
        parent,
    )

    merged = cli_module._merge_group_params(ctx, ("device",))

    assert merged["device"] == "sub-device"


def test_merge_group_params_falls_back_to_group_commandline(cli_module):
    parent = _ParamCtx(
        {"device": "group-device"},
        {"device": ParameterSource.COMMANDLINE},
    )
    ctx = _ParamCtx(
        {"device": None},
        {"device": ParameterSource.DEFAULT},
        parent,
    )

    merged = cli_module._merge_group_params(ctx, ("device",))

    assert merged["device"] == "group-device"


def test_merge_group_params_uses_subcommand_default(cli_module):
    parent = _ParamCtx(
        {"device": None},
        {"device": ParameterSource.DEFAULT},
    )
    ctx = _ParamCtx(
        {"device": "sub-default"},
        {"device": ParameterSource.DEFAULT},
        parent,
    )

    merged = cli_module._merge_group_params(ctx, ("device",))

    assert merged["device"] == "sub-default"


def test_wait_session_ready_returns_ready_status(cli_module):
    client = Mock()
    client.call.return_value = {"state": "ready"}

    with patch.object(cli_module, "GDBClient", return_value=client):
        result = cli_module._wait_session_ready("/tmp/fake.sock", timeout=1.0)

    assert result["state"] == "ready"


def test_wait_session_ready_times_out_while_loading(cli_module):
    client = Mock()
    client.call.return_value = {"state": "loading"}

    with patch.object(cli_module, "GDBClient", return_value=client), \
         patch.object(cli_module.time, "sleep", lambda seconds: None):
        with pytest.raises(cli_module.JLinkManagerError) as excinfo:
            cli_module._wait_session_ready("/tmp/fake.sock", timeout=0)

    assert "loading" in str(excinfo.value)


def test_start_failure_cascade_cleans_up_and_preserves_error(cli_module):
    _FakeClick._context = _FakeContext(invoked_subcommand=None)
    instance = types.SimpleNamespace(
        instance_id="abcd1234",
        port=2331,
        device="D",
        select="usb=1",
        session_id=None,
        session_config={},
    )
    fake_process = types.SimpleNamespace(
        session=types.SimpleNamespace(
            session_id="sess1234", sock_path="/tmp/fake.sock"
        )
    )
    order = []

    def fake_session_stop(session_id):
        order.append(("session", session_id))

    def fake_stop(instance_id):
        order.append(("server", instance_id))
        return {"jlink_id": instance_id, "status": "stopped"}

    with patch.object(cli_module, "start_gdbserver", return_value=instance), \
         patch.object(cli_module, "launch_target", return_value=fake_process), \
         patch.object(
             cli_module, "_wait_session_ready",
             side_effect=cli_module.JLinkManagerError("not ready"),
         ), \
         patch.object(cli_module, "_stop_gdb_session", side_effect=fake_session_stop), \
         patch.object(cli_module, "stop_instance", side_effect=fake_stop), \
         patch.object(cli_module, "print_error") as mock_error, \
         patch.object(cli_module, "print_json") as mock_print:
        with pytest.raises(cli_module.click.exceptions.Exit) as excinfo:
            cli_module.jlink(**_start_kwargs())

    assert excinfo.value.exit_code == 1
    assert order == [("session", "sess1234"), ("server", "abcd1234")]
    mock_print.assert_not_called()
    # Original reason stays in ``details``; cleanup did not replace it.
    assert mock_error.call_args.args[1] == "not ready"


def test_start_failure_cleanup_errors_are_separate(cli_module):
    _FakeClick._context = _FakeContext(invoked_subcommand=None)
    instance = types.SimpleNamespace(
        instance_id="abcd1234",
        port=2331,
        device="D",
        select="usb=1",
        session_id=None,
        session_config={},
    )
    fake_process = types.SimpleNamespace(
        session=types.SimpleNamespace(
            session_id="sess1234", sock_path="/tmp/fake.sock"
        )
    )

    with patch.object(cli_module, "start_gdbserver", return_value=instance), \
         patch.object(cli_module, "launch_target", return_value=fake_process), \
         patch.object(
             cli_module, "_wait_session_ready",
             side_effect=cli_module.JLinkManagerError("not ready"),
         ), \
         patch.object(
             cli_module, "_stop_gdb_session",
             side_effect=RuntimeError("cleanup boom"),
         ), \
         patch.object(
             cli_module, "stop_instance",
             side_effect=RuntimeError("server boom"),
         ), \
         patch.object(cli_module, "print_error") as mock_error:
        with pytest.raises(cli_module.click.exceptions.Exit):
            cli_module.jlink(**_start_kwargs())

    assert mock_error.call_args.args[1] == "not ready"
    cleanup_errors = mock_error.call_args.args[2]
    assert len(cleanup_errors) == 2
    assert any("cleanup boom" in error for error in cleanup_errors)
    assert any("server boom" in error for error in cleanup_errors)


def test_stop_stops_session_before_server(cli_module, jlink_dir):
    _make_instance(jlink_dir, session_id="sess1234")
    order = []

    def fake_session_stop(session_id):
        order.append(("session", session_id))

    def fake_stop(instance_id):
        stored = json.loads(
            (jlink_dir / f"{instance_id}.json").read_text(encoding="utf-8")
        )
        order.append(("server", stored["session_id"]))
        return {"jlink_id": instance_id, "status": "stopped"}

    with patch.object(cli_module, "_stop_gdb_session", side_effect=fake_session_stop), \
         patch.object(cli_module, "stop_instance", side_effect=fake_stop), \
         patch.object(cli_module, "print_json"):
        cli_module.jlink_stop("abcd1234", False)

    assert order == [("session", "sess1234"), ("server", None)]


def test_stop_reports_stop_failed_and_exits(cli_module, jlink_dir):
    _make_instance(jlink_dir)

    with patch.object(
        cli_module, "stop_instance",
        return_value={"jlink_id": "abcd1234", "status": "stop_failed"},
    ), patch.object(cli_module, "print_error") as mock_error, \
         patch.object(cli_module, "print_json") as mock_print:
        with pytest.raises(cli_module.click.exceptions.Exit) as excinfo:
            cli_module.jlink_stop("abcd1234", False)

    assert excinfo.value.exit_code == 1
    mock_print.assert_not_called()
    mock_error.assert_called_once()


def test_stop_all_removes_dead_instance_jsons(cli_module, jlink_dir, monkeypatch):
    _make_instance(jlink_dir, instance_id="aaaa1111", pid=1001, start_time="111")
    _make_instance(jlink_dir, instance_id="bbbb2222", pid=1002, start_time="111")

    def fake_starttime(pid):
        return "111" if pid == 1001 else "999"

    monkeypatch.setattr(jlink, "_read_proc_starttime", fake_starttime)

    with patch.object(
        cli_module, "stop_instance",
        return_value={"jlink_id": "aaaa1111", "status": "stopped"},
    ), patch.object(cli_module, "print_json") as mock_print:
        cli_module.jlink_stop(None, True)

    assert (jlink_dir / "aaaa1111.json").exists()
    assert not (jlink_dir / "bbbb2222.json").exists()
    payload = mock_print.call_args.args[0]
    assert payload["removed_stale"] == ["bbbb2222"]


def test_restart_reconnects_with_persisted_config(cli_module, jlink_dir):
    _make_instance(
        jlink_dir,
        session_id="oldsess",
        session_config={
            "binary": "fw.elf",
            "gdb_path": "arm-gdb",
            "timeout": 120,
            "init_cmds": ["monitor exec EnableLowPowerHandlingMode"],
        },
    )
    restarted = _make_instance(jlink_dir, instance_id="newinst1")
    captured = {}

    def fake_connect(instance, **kwargs):
        captured.update(kwargs)
        instance.session_id = kwargs.get("session_id") or "newsess"
        return instance.session_id

    with patch.object(cli_module, "_stop_gdb_session") as mock_session_stop, \
         patch.object(
             cli_module, "stop_instance",
             return_value={"jlink_id": "abcd1234", "status": "stopped"},
         ), \
         patch.object(cli_module, "start_gdbserver", return_value=restarted), \
         patch.object(cli_module, "_connect_gdb_session", side_effect=fake_connect), \
         patch.object(cli_module, "print_json") as mock_print:
        cli_module.jlink_restart("abcd1234")

    mock_session_stop.assert_called_once_with("oldsess")
    # The session id must be stable across a restart.
    assert captured["session_id"] == "oldsess"
    # Init commands are replayed from the persisted session config.
    assert captured["init_cmds"] == ["monitor exec EnableLowPowerHandlingMode"]
    payload = mock_print.call_args.args[0]
    assert payload["session_id"] == "oldsess"
    assert payload["status"] == "restarted"


def test_restart_connect_failure_cleans_up_and_exits(cli_module, jlink_dir):
    _make_instance(jlink_dir, session_config={"binary": "fw.elf"})
    restarted = _make_instance(jlink_dir, instance_id="newinst2")

    with patch.object(cli_module, "_stop_gdb_session"), \
         patch.object(
             cli_module, "stop_instance",
             return_value={"jlink_id": "abcd1234", "status": "stopped"},
         ), \
         patch.object(cli_module, "start_gdbserver", return_value=restarted), \
         patch.object(
             cli_module, "_connect_gdb_session",
             side_effect=cli_module.JLinkManagerError("reconnect failed"),
         ), \
         patch.object(
             cli_module, "_cleanup_failed_instance", return_value=["cleanup"]
         ) as mock_cleanup, \
         patch.object(cli_module, "print_error") as mock_error:
        with pytest.raises(cli_module.click.exceptions.Exit) as excinfo:
            cli_module.jlink_restart("abcd1234")

    assert excinfo.value.exit_code == 1
    mock_cleanup.assert_called_once_with(restarted)
    assert mock_error.call_args.args[1] == "reconnect failed"
    assert mock_error.call_args.args[2] == ["cleanup"]


def test_merge_group_params_propagates_rtos(cli_module):
    parent = _ParamCtx(
        {"rtos": "FreeRTOS"},
        {"rtos": ParameterSource.COMMANDLINE},
    )
    ctx = _ParamCtx(
        {"rtos": None},
        {"rtos": ParameterSource.DEFAULT},
        parent,
    )

    assert cli_module._merge_group_params(ctx)["rtos"] == "FreeRTOS"


@pytest.mark.parametrize(
    "catalog_name",
    ["ENGLISH_CATALOG", "ZH_CN_CATALOG", "RU_CATALOG"],
)
def test_jlink_help_epilogs_match(catalog_name):
    module = importlib.import_module(
        {
            "ENGLISH_CATALOG": "gdb_cli.locales.en",
            "ZH_CN_CATALOG": "gdb_cli.locales.zh_cn",
            "RU_CATALOG": "gdb_cli.locales.ru",
        }[catalog_name]
    )
    catalog = getattr(module, catalog_name)

    # Group help and ``start --help`` must document the same server options.
    assert catalog["cli.jlink.epilog"] == catalog["cli.jlink.start_epilog"]


def test_english_jlink_help_has_meanings_and_no_deprecated_options():
    from gdb_cli.locales.en import ENGLISH_CATALOG

    text = ENGLISH_CATALOG["cli.jlink.epilog"]
    # Each bridged option is described, not just mapped.
    assert "--rtos <name>" in text
    assert "raw SWO output" in text
    assert "target printf" in text
    assert "single GDB connection" in text
    # All currently supported RTOS plugins are listed.
    for name in ("FreeRTOS", "embOS", "Zephyr", "Azure", "ChibiOS", "NuttX"):
        assert name in text
    # The internal server mapping is an implementation detail.
    assert "GDBServer/RTOSPlugin_" not in text
    # Deprecated / replaced options must not be advertised.
    assert "-JLinkDevicesXMLPath" not in text
    assert "-USB" not in text
    assert "-IP " not in text


def test_rtos_help_lists_supported_plugins_without_internals():
    from gdb_cli.locales.en import ENGLISH_CATALOG

    text = ENGLISH_CATALOG["cli.jlink.rtos_help"]
    for name in ("FreeRTOS", "embOS", "Zephyr", "Azure", "ChibiOS", "NuttX"):
        assert name in text
    assert "GDBServer/RTOSPlugin_" not in text

