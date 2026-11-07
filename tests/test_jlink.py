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
        extra_args=["-rtos", "FreeRTOS", "-jlinkscriptfile", "f.jlink"],
    )

    assert _value_after(cmdline, "-if") == "JTAG"
    assert _value_after(cmdline, "-speed") == "4000"
    assert cmdline[-4:] == ["-rtos", "FreeRTOS", "-jlinkscriptfile", "f.jlink"]


def test_build_cmdline_custom_executable():
    cmdline = jlink.build_gdbserver_cmdline(
        device="D", select="usb=1", port=2331, extra_args=[],
        jlink_exe="/opt/JLink/JLinkGDBServer",
    )
    assert cmdline[0] == "/opt/JLink/JLinkGDBServer"


@pytest.mark.parametrize("select", ["usb", "ip", "usb=", "ip=", "", "ip=no-port"])
def test_validate_select_rejects_invalid(select):
    with pytest.raises(jlink.JLinkManagerError):
        jlink.validate_select(select)


def test_validate_select_usb_without_selector_mentions_devices():
    with pytest.raises(jlink.JLinkManagerError) as excinfo:
        jlink.validate_select("usb")
    assert "gdb-cli jlink devices" in str(excinfo.value)


@pytest.mark.parametrize(
    "select", ["usb=123", "usb=昵称", "ip=172.25.176.1:19025"]
)
def test_validate_select_accepts_valid(select):
    jlink.validate_select(select)


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
    assert run.call_args.kwargs["input"] == "ShowEmuList\n"


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
        )

    def _call_jlink(self, **overrides):
        values = {
            "device": "D",
            "select": "usb=1",
            "binary": None,
            "gdb_path": "gdb",
            "jlink_path": "JLinkGDBServer",
            "speed": None,
            "interface": "SWD",
            "port": 2331,
            "allow_write": False,
            "allow_call": False,
            "timeout": 600,
            "extra_args": (),
        }
        values.update(overrides)
        return self.cli.jlink(**values)

    def test_default_subcommand_invokes_start(self):
        ctx = _FakeContext(invoked_subcommand=None)
        _FakeClick._context = ctx
        fake_process = types.SimpleNamespace(
            session=types.SimpleNamespace(session_id="sess1234")
        )

        with patch.object(self.cli, "start_gdbserver", return_value=self._instance()) as mock_start, \
             patch.object(self.cli, "launch_target", return_value=fake_process) as mock_launch, \
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
