"""Tests for async load command ordering and loading state handling."""

import os
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gdb_cli.session import SessionMeta


class TestLaunchCoreAsyncOrder(unittest.TestCase):
    """Ensure core loading starts the RPC server before heavy file/core work."""

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_launch_core_starts_server_before_file_and_core(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_core

        session = SessionMeta(
            session_id="test1234",
            mode="core",
            binary="/tmp/a.out",
            core="/tmp/core.1",
            sock_path="/tmp/test.sock",
            heartbeat_timeout=123,
        )
        session._gdb_process = Mock(pid=4321)
        mock_create_session.return_value = session

        result = launch_core(
            binary="/tmp/a.out",
            core="/tmp/core.1",
            timeout=123,
        )

        self.assertEqual(result.session.session_id, "test1234")
        args = mock_start.call_args.args[0]
        commands = [args[i + 1] for i, value in enumerate(args[:-1]) if value == "-ex"]

        start_index = commands.index(next(cmd for cmd in commands if "start_server(" in cmd))
        file_index = commands.index("file '/tmp/a.out'")
        core_index = commands.index("core-file '/tmp/core.1'")
        ready_index = commands.index("python _gdb_rpc_server.set_ready()")

        self.assertLess(start_index, file_index)
        self.assertLess(file_index, core_index)
        self.assertLess(core_index, ready_index)

        from gdb_cli.launcher import SOCKET_WAIT_TIMEOUT

        self.assertEqual(
            mock_start.call_args.kwargs["timeout"], SOCKET_WAIT_TIMEOUT
        )


class TestGDBRPCServerLoadingState(unittest.TestCase):
    """Verify loading mode only exposes safe commands."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        os.environ["GDB_CLI_SERVER_DIR"] = str(
            Path(__file__).resolve().parent.parent / "src" / "gdb_cli" / "gdb_server"
        )

        gdb_mock = Mock()
        gdb_mock.MemoryError = type("MemoryError", (Exception,), {})
        gdb_mock.error = type("GDBError", (Exception,), {})
        gdb_mock.events = Mock()
        gdb_mock.events.new_objfile = Mock()
        gdb_mock.events.new_objfile.connect = Mock()
        gdb_mock.events.before_prompt = Mock()
        gdb_mock.events.before_prompt.connect = Mock()
        gdb_mock.write = Mock()
        gdb_mock.post_event = lambda fn: fn()  # Execute immediately for testing
        sys.modules["gdb"] = gdb_mock

    def test_dispatch_blocks_non_status_while_loading(self):
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        server = GDBRPCServer(
            sock_path=str(Path(self.temp_dir) / "sock"),
            session_meta={"session_id": "abc123", "mode": "core"},
        )
        server._handlers = {"bt": Mock(return_value={"frames": []})}

        with self.assertRaisesRegex(ValueError, "Session is loading"):
            server._dispatch({"cmd": "bt"})

    def test_dispatch_returns_lightweight_status_while_loading(self):
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        server = GDBRPCServer(
            sock_path=str(Path(self.temp_dir) / "sock"),
            session_meta={"session_id": "abc123", "mode": "core"},
        )

        result = server._dispatch({"cmd": "status"})

        self.assertEqual(result["state"], "loading")
        self.assertIn("elapsed", result)
        self.assertEqual(result["session_meta"]["session_id"], "abc123")

    def test_set_ready_allows_normal_dispatch(self):
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        handler = Mock(return_value={"state": "ready"})
        server = GDBRPCServer(
            sock_path=str(Path(self.temp_dir) / "sock"),
            session_meta={"session_id": "abc123", "mode": "core"},
        )
        server._handlers = {"status": handler}

        server.set_ready()
        result = server._dispatch({"cmd": "status"})

        self.assertEqual(result["state"], "ready")
        handler.assert_called_once()

    def test_start_server_exports_global_for_followup_python_commands(self):
        import __main__
        from gdb_cli.gdb_server.gdb_rpc_server import start_server

        fake_server = Mock()

        with patch("gdb_cli.gdb_server.gdb_rpc_server.GDBRPCServer", return_value=fake_server):
            start_server("/tmp/test.sock", {"session_id": "abc123"}, 600)

        self.assertIs(__main__._gdb_rpc_server, fake_server)


class TestSetReadyInferiorCheck(unittest.TestCase):
    """set_ready must mark the session as error when no inferior exists."""

    def setUp(self):
        import tempfile

        import gdb_cli.gdb_server.gdb_rpc_server as srv

        self.temp_dir = tempfile.mkdtemp()
        os.environ["GDB_CLI_SERVER_DIR"] = str(
            Path(__file__).resolve().parent.parent / "src" / "gdb_cli" / "gdb_server"
        )
        # Mutate the gdb mock actually referenced by the server module
        # (replacing sys.modules["gdb"] would desync it from other tests).
        self.srv = srv
        self.gdb = srv.gdb
        self._orig_inferiors = getattr(self.gdb, "inferiors", None)
        self.gdb.inferiors = Mock(return_value=[])

    def tearDown(self):
        if self._orig_inferiors is not None:
            self.gdb.inferiors = self._orig_inferiors
        else:
            del self.gdb.inferiors

    def _make_server(self, mode):
        return self.srv.GDBRPCServer(
            sock_path=str(Path(self.temp_dir) / "ready.sock"),
            session_meta={"session_id": "abc123", "mode": mode},
        )

    def test_target_without_inferior_marks_error(self):
        self.gdb.inferiors = Mock(return_value=[])
        server = self._make_server("target")
        server.set_ready()
        self.assertEqual(server._state, "error")
        self.assertIn("inferior", server._error_reason)

    def test_target_with_live_inferior_marks_ready(self):
        inferior = Mock(pid=42000)
        self.gdb.inferiors = Mock(return_value=[inferior])
        server = self._make_server("target")
        server.set_ready()
        self.assertEqual(server._state, "ready")

    def test_inferiors_api_unavailable_assumes_ready(self):
        # Mocks / very old GDB without a list-like inferiors(): fail open.
        self.gdb.inferiors = Mock(side_effect=TypeError("not iterable"))
        server = self._make_server("target")
        server.set_ready()
        self.assertEqual(server._state, "ready")


class TestStopHandler(unittest.TestCase):
    """Verify graceful stop: optional pre-detach commands, detach, shutdown."""

    @classmethod
    def setUpClass(cls):
        import tempfile

        cls.temp_dir = tempfile.mkdtemp()
        os.environ["GDB_CLI_SERVER_DIR"] = str(
            Path(__file__).resolve().parent.parent / "src" / "gdb_cli" / "gdb_server"
        )

        gdb_mock = sys.modules.get("gdb") or Mock()
        gdb_mock.MemoryError = type("MemoryError", (Exception,), {})
        gdb_mock.error = type("GDBError", (Exception,), {})
        gdb_mock.events = Mock()
        gdb_mock.events.new_objfile = Mock()
        gdb_mock.events.new_objfile.connect = Mock()
        gdb_mock.events.before_prompt = Mock()
        gdb_mock.events.before_prompt.connect = Mock()
        gdb_mock.write = Mock()
        gdb_mock.post_event = lambda fn: fn()
        sys.modules["gdb"] = gdb_mock

    def setUp(self):
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        self.gdb = sys.modules["gdb"]
        self.gdb.execute = Mock()

        self.server = GDBRPCServer(
            sock_path=str(Path(self.temp_dir) / "stop.sock"),
            session_meta={"session_id": "abc123", "mode": "target"},
        )
        self.server.set_ready()

    def test_stop_runs_before_detach_and_detaches(self):
        result = self.server._dispatch(
            {"cmd": "stop", "before_detach": "monitor go\nmonitor reset"}
        )

        self.assertTrue(self.server._stop_requested)
        self.assertTrue(result["detached"])
        calls = [c.args[0] for c in self.gdb.execute.call_args_list]
        self.assertEqual(calls, ["monitor go", "monitor reset", "detach"])

    def test_stop_allowed_while_loading(self):
        self.server._state = "loading"

        result = self.server._dispatch({"cmd": "stop"})

        self.assertTrue(self.server._stop_requested)
        self.assertTrue(result["detached"])

    def test_detach_without_inferior_is_not_an_error(self):
        self.gdb.execute.side_effect = [
            Exception("No inferior to detach"),
        ]

        result = self.server._dispatch({"cmd": "stop"})

        self.assertFalse(result["detached"])
        self.assertEqual(result["errors"], [])


class _ServerTestCase(unittest.TestCase):
    """Shared setup: a GDBRPCServer backed by the mocked ``gdb`` module."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        os.environ["GDB_CLI_SERVER_DIR"] = str(
            Path(__file__).resolve().parent.parent
            / "src"
            / "gdb_cli"
            / "gdb_server"
        )

        gdb_mock = Mock()
        gdb_mock.MemoryError = type("MemoryError", (Exception,), {})
        gdb_mock.error = type("GDBError", (Exception,), {})
        gdb_mock.events = Mock()
        gdb_mock.events.new_objfile = Mock()
        gdb_mock.events.new_objfile.connect = Mock()
        gdb_mock.events.before_prompt = Mock()
        gdb_mock.events.before_prompt.connect = Mock()
        gdb_mock.write = Mock()
        gdb_mock.post_event = lambda fn: fn()
        sys.modules["gdb"] = gdb_mock

        from gdb_cli.gdb_server import gdb_rpc_server as server_module

        cls.gdb = server_module.gdb

    def make_server(self, **kwargs):
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        server = GDBRPCServer(
            sock_path=str(Path(self.temp_dir) / "sock"),
            session_meta={"session_id": "abc123", "mode": "core"},
            **kwargs,
        )
        server.set_ready()
        self._servers.append(server)
        return server

    def setUp(self):
        self.gdb = type(self).gdb
        self.gdb.write.reset_mock()
        self.gdb.post_event = lambda fn: fn()
        self.gdb.execute = Mock()
        self._servers = []

    def tearDown(self):
        for server in self._servers:
            if server.heartbeat_timer is not None:
                server.heartbeat_timer.cancel()
                server.heartbeat_timer = None
            if server._loading_timer is not None:
                server._loading_timer.cancel()
                server._loading_timer = None


class TestDispatchErrorContract(_ServerTestCase):
    """Handler-level errors must be surfaced as ok=False, not ok=True."""

    def test_top_level_error_dict_raises(self):
        server = self.make_server()
        server._handlers = {"eval": Mock(return_value={"error": "boom"})}

        with self.assertRaisesRegex(ValueError, "boom"):
            server._dispatch({"cmd": "eval"})

    def test_nested_error_keys_are_not_treated_as_failure(self):
        server = self.make_server()
        payload = {"registers": [{"name": "rax", "error": "unavailable"}]}
        server._handlers = {"registers": Mock(return_value=payload)}

        self.assertEqual(server._dispatch({"cmd": "registers"}), payload)

    def test_handler_exception_raises(self):
        server = self.make_server()
        server._handlers = {"eval": Mock(side_effect=RuntimeError("kaboom"))}

        with self.assertRaisesRegex(RuntimeError, "kaboom"):
            server._dispatch({"cmd": "eval"})

    def test_status_gets_injected_server_state(self):
        server = self.make_server()
        handler = Mock(return_value={"state": "ready"})
        server._handlers = {"status": handler}

        server._dispatch({"cmd": "status"})

        self.assertEqual(
            handler.call_args.kwargs["_server_state"], "ready"
        )


class TestDispatchCommandTimeout(_ServerTestCase):
    """The configured timeout must be used and abandoned requests tracked."""

    def test_uses_self_command_timeout(self):
        server = self.make_server()
        server.command_timeout = 0.05
        server._handlers = {"slow": Mock(return_value={})}

        # Do not execute the posted callback: simulate a hung handler.
        self.gdb.post_event = Mock()

        with self.assertRaisesRegex(RuntimeError, "0.05"):
            server._dispatch({"cmd": "slow"})

        self.assertEqual(len(server._abandoned), 1)

    def test_late_result_for_abandoned_request_is_logged(self):
        server = self.make_server()
        server.command_timeout = 0.01
        server._handlers = {"slow": Mock(return_value={"value": 1})}

        posted = []
        self.gdb.post_event = posted.append
        self.gdb.write.reset_mock()

        with self.assertRaises(RuntimeError):
            server._dispatch({"cmd": "slow"})

        self.assertEqual(len(posted), 1)
        # The client already timed out; running the late callback must log and
        # not pretend the handler never ran.
        posted[0]()

        messages = [c.args[0] for c in self.gdb.write.call_args_list]
        self.assertTrue(any("abandoned" in m for m in messages), messages)
        self.assertEqual(server._abandoned, set())


class TestHeartbeatTimer(_ServerTestCase):
    """Heartbeat generation guard and disabled mode."""

    def test_zero_timeout_disables_timer(self):
        server = self.make_server(heartbeat_timeout=0)

        server._start_heartbeat_timer()

        self.assertIsNone(server.heartbeat_timer)

    def test_stale_generation_does_not_post_cleanup(self):
        server = self.make_server(heartbeat_timeout=10)
        server.running = True

        server._start_heartbeat_timer()
        stale_generation = server._heartbeat_generation

        # A newer request resets the heartbeat and bumps the generation.
        server._reset_heartbeat()
        server.last_active = time.time()

        posted = []
        self.gdb.post_event = posted.append

        server._heartbeat_timeout(stale_generation)

        self.assertEqual(posted, [])

    def test_timer_thread_does_not_call_gdb_write(self):
        server = self.make_server(heartbeat_timeout=10)
        server.running = True
        server.last_active = time.time() - 100
        server._start_heartbeat_timer()
        generation = server._heartbeat_generation

        self.gdb.inferiors = Mock(return_value=[])
        posted = []
        self.gdb.post_event = posted.append
        self.gdb.write.reset_mock()

        server._heartbeat_timeout(generation)

        # Everything GDB-level is deferred to the posted event.
        self.gdb.write.assert_not_called()
        self.assertEqual(len(posted), 1)

        posted[0]()

        self.assertTrue(self.gdb.write.called)

    def test_detach_uses_inferiors_syntax(self):
        server = self.make_server(heartbeat_timeout=10)
        server.running = True
        server.last_active = time.time() - 100
        server._start_heartbeat_timer()
        generation = server._heartbeat_generation

        inferior = types.SimpleNamespace(pid=1234, num=7)
        self.gdb.inferiors = Mock(return_value=[inferior])
        self.gdb.execute = Mock()

        server._heartbeat_timeout(generation)
        # With post_event executing immediately the cleanup already ran.
        commands = [c.args[0] for c in self.gdb.execute.call_args_list]

        self.assertIn("detach inferiors 7", commands)
        self.assertIn("quit", commands)
        self.assertNotIn("detach 1234", commands)

    def test_detach_falls_back_to_plain_detach(self):
        server = self.make_server(heartbeat_timeout=10)
        server.running = True
        server.last_active = time.time() - 100
        server._start_heartbeat_timer()
        generation = server._heartbeat_generation

        inferior = types.SimpleNamespace(pid=1234, num=7)
        self.gdb.inferiors = Mock(return_value=[inferior])
        self.gdb.execute = Mock(side_effect=[Exception("bad selector"), None, None])

        server._heartbeat_timeout(generation)

        commands = [c.args[0] for c in self.gdb.execute.call_args_list]
        self.assertEqual(
            commands, ["detach inferiors 7", "detach", "quit"]
        )


class TestServerStateMachine(_ServerTestCase):
    """Error state only allows ping/status/stop."""

    def test_error_state_blocks_regular_commands(self):
        server = self.make_server()
        server._state = "error"
        server._error_reason = "core file missing"
        server._handlers = {"bt": Mock(return_value={"frames": []})}

        with self.assertRaisesRegex(
            ValueError, "session failed during initialization: core file missing"
        ):
            server._dispatch({"cmd": "bt"})

    def test_error_state_allows_status_with_reason(self):
        server = self.make_server()
        server._state = "error"
        server._error_reason = "core file missing"

        result = server._dispatch({"cmd": "status"})

        self.assertEqual(result["state"], "error")
        self.assertEqual(result["error_reason"], "core file missing")

    def test_error_state_allows_ping_and_stop(self):
        server = self.make_server()
        server._state = "error"
        server._error_reason = "bad"

        ping = server._dispatch({"cmd": "ping"})
        self.assertTrue(ping["pong"])

        stop = server._dispatch({"cmd": "stop"})
        self.assertIn("detached", stop)

    def test_loading_timeout_sets_error_reason(self):
        server = self.make_server()
        server._state = "loading"
        self.gdb.post_event = lambda fn: fn()

        server._loading_timeout()
        result = server._dispatch({"cmd": "status"})

        self.assertEqual(result["state"], "error")
        self.assertIn("Loading timeout", result["error_reason"])


class TestSequentialConnections(_ServerTestCase):
    """The refactored accept loop must serve multiple connections."""

    def test_two_sequential_connections(self):
        from gdb_cli.client import GDBClient
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        sock_path = str(Path(self.temp_dir) / "seq.sock")
        server = GDBRPCServer(
            sock_path=sock_path,
            session_meta={"session_id": "seq", "mode": "core"},
            heartbeat_timeout=0,
        )
        server.set_ready()
        server.start()
        try:
            client = GDBClient(sock_path, timeout=10.0)
            first = client.call("ping")
            second = client.call("ping")
            self.assertTrue(first["pong"])
            self.assertTrue(second["pong"])
        finally:
            server.stop()

    def test_handler_error_is_wrapped_as_ok_false(self):
        from gdb_cli.client import GDBClient, GDBCommandError
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        sock_path = str(Path(self.temp_dir) / "err.sock")
        server = GDBRPCServer(
            sock_path=sock_path,
            session_meta={"session_id": "err", "mode": "core"},
            heartbeat_timeout=0,
        )
        server.set_ready()
        server._handlers["eval"] = Mock(return_value={"error": "handler boom"})
        server.start()
        try:
            client = GDBClient(sock_path, timeout=10.0)
            with self.assertRaisesRegex(GDBCommandError, "handler boom"):
                client.call("eval", expr="x")
        finally:
            server.stop()


class TestWaitStop(_ServerTestCase):
    """Long-poll stop notification: the worker blocks, the main thread never does."""

    @staticmethod
    def _fake_event(breakpoints=None, stop_signal=None):
        return types.SimpleNamespace(
            breakpoints=breakpoints or [],
            stop_signal=stop_signal,
        )

    def _setup_gdb_state(self, thread=None, frame=None):
        self.gdb.selected_thread = Mock(return_value=thread)
        self.gdb.selected_frame = Mock(return_value=frame)

    def test_wait_stop_handler_returns_marker_without_blocking(self):
        server = self.make_server()
        self._setup_gdb_state()
        result = server._handle_wait_stop(wait_timeout=30.0)
        self.assertTrue(result["__wait_stop__"])
        self.assertEqual(result["timeout"], 30.0)
        self.assertIsNotNone(result["queue"])
        # Registered so a stop event can reach it.
        self.assertEqual(len(server._stop_waiters), 1)

    def test_on_gdb_stop_notifies_waiter_with_breakpoint_info(self):
        server = self.make_server()
        thread = types.SimpleNamespace(num=2, global_num=7)
        frame = types.SimpleNamespace(
            name=lambda: "arch_cpu_idle",
            pc=lambda: 0x440B4,
            find_sal=lambda: types.SimpleNamespace(
                symtab=types.SimpleNamespace(filename="port.c"), line=81
            ),
        )
        self._setup_gdb_state(thread=thread, frame=frame)
        marker = server._handle_wait_stop(wait_timeout=30.0)
        bp = types.SimpleNamespace(number=1)
        server._on_gdb_stop(self._fake_event(breakpoints=[bp]))
        info = marker["queue"].get(timeout=1.0)
        self.assertTrue(info["stopped"])
        self.assertEqual(info["reason"], "breakpoint-hit")
        self.assertEqual(info["breakpoint_numbers"], [1])
        self.assertEqual(info["thread"], {"id": 2, "global_id": 7})
        self.assertEqual(info["frame"]["function"], "arch_cpu_idle")
        self.assertEqual(info["frame"]["address"], "0x440b4")
        self.assertEqual(info["frame"]["line"], 81)

    def test_build_stop_info_signal(self):
        server = self.make_server()
        self._setup_gdb_state()
        info = server._build_stop_info(self._fake_event(stop_signal="SIGINT"))
        self.assertTrue(info["stopped"])
        self.assertEqual(info["reason"], "signal")
        self.assertEqual(info["signal"], "SIGINT")

    def test_build_stop_info_plain_stop(self):
        server = self.make_server()
        self._setup_gdb_state()
        info = server._build_stop_info(self._fake_event())
        self.assertTrue(info["stopped"])
        self.assertEqual(info["reason"], "stopped")
        self.assertIsNone(info["thread"])
        self.assertIsNone(info["frame"])

    def test_multiple_waiters_all_notified(self):
        server = self.make_server()
        self._setup_gdb_state()
        m1 = server._handle_wait_stop(wait_timeout=30.0)
        m2 = server._handle_wait_stop(wait_timeout=30.0)
        server._on_gdb_stop(self._fake_event())
        self.assertTrue(m1["queue"].get(timeout=1.0)["stopped"])
        self.assertTrue(m2["queue"].get(timeout=1.0)["stopped"])

    def test_dispatch_wait_stop_times_out_and_unregisters(self):
        server = self.make_server()
        self._setup_gdb_state()
        result = server._dispatch({"cmd": "wait_stop", "wait_timeout": 0.05})
        self.assertFalse(result["stopped"])
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(len(server._stop_waiters), 0)

    def test_dispatch_wait_stop_returns_event(self):
        server = self.make_server()
        self._setup_gdb_state()

        def fire():
            time.sleep(0.1)
            server._on_gdb_stop(self._fake_event(breakpoints=[types.SimpleNamespace(number=3)]))

        timer = threading.Thread(target=fire)
        timer.start()
        try:
            result = server._dispatch({"cmd": "wait_stop", "wait_timeout": 5.0})
        finally:
            timer.join()
        self.assertTrue(result["stopped"])
        self.assertEqual(result["reason"], "breakpoint-hit")
        self.assertEqual(result["breakpoint_numbers"], [3])
        self.assertEqual(len(server._stop_waiters), 0)

    def test_shutdown_wakes_waiters(self):
        server = self.make_server()
        self._setup_gdb_state()
        marker = server._handle_wait_stop(wait_timeout=30.0)
        server._wake_stop_waiters()
        info = marker["queue"].get(timeout=1.0)
        self.assertFalse(info["stopped"])
        self.assertEqual(info["reason"], "shutdown")

    def test_wait_stop_returns_immediately_when_already_stopped(self):
        """A stop that happened BEFORE wait_stop must not wait for a lost event."""
        server = self.make_server()
        thread = types.SimpleNamespace(
            num=2, global_num=7,
            is_running=lambda: False, is_exited=lambda: False,
        )
        frame = types.SimpleNamespace(
            name=lambda: "arch_cpu_idle",
            pc=lambda: 0x440B4,
            find_sal=lambda: None,
        )
        self._setup_gdb_state(thread=thread, frame=frame)

        marker = server._handle_wait_stop(wait_timeout=30.0)

        info = marker["queue"].get(timeout=1.0)
        self.assertTrue(info["stopped"])
        self.assertEqual(info["reason"], "already-stopped")
        self.assertEqual(info["thread"], {"id": 2, "global_id": 7})
        self.assertEqual(info["frame"]["function"], "arch_cpu_idle")
        # The answer was already in hand: nothing was registered.
        self.assertEqual(len(server._stop_waiters), 0)

    def test_wait_stop_returns_immediately_when_target_exited(self):
        server = self.make_server()
        thread = types.SimpleNamespace(
            num=2, global_num=7,
            is_running=lambda: False, is_exited=lambda: True,
        )
        self._setup_gdb_state(thread=thread, frame=None)

        marker = server._handle_wait_stop(wait_timeout=30.0)

        info = marker["queue"].get(timeout=1.0)
        self.assertFalse(info["stopped"])
        self.assertEqual(info["reason"], "exited")
        self.assertEqual(len(server._stop_waiters), 0)

    def test_wait_stop_waits_when_target_running(self):
        server = self.make_server()
        thread = types.SimpleNamespace(
            num=2, global_num=7,
            is_running=lambda: True, is_exited=lambda: False,
        )
        self._setup_gdb_state(thread=thread, frame=None)

        marker = server._handle_wait_stop(wait_timeout=30.0)

        self.assertTrue(marker["queue"].empty())
        self.assertEqual(len(server._stop_waiters), 1)

    def test_main_thread_responsive_while_waiting(self):
        from gdb_cli.client import GDBClient
        from gdb_cli.gdb_server.gdb_rpc_server import GDBRPCServer

        sock_path = str(Path(self.temp_dir) / "waitstop.sock")
        server = GDBRPCServer(
            sock_path=sock_path,
            session_meta={"session_id": "ws", "mode": "target"},
            heartbeat_timeout=0,
        )
        # A live inferior so set_ready() does not mark the session as error.
        self.gdb.inferiors = Mock(return_value=[types.SimpleNamespace(pid=4242, num=1)])
        server.set_ready()
        self.gdb.selected_thread = Mock(return_value=None)
        self.gdb.selected_frame = Mock(return_value=None)
        server.start()
        self._servers.append(server)
        results = {}

        def waiter():
            client = GDBClient(sock_path, timeout=10.0)
            results["wait"] = client.call("wait_stop", wait_timeout=5.0)

        t = threading.Thread(target=waiter)
        t.start()
        try:
            time.sleep(0.2)  # let the waiter register
            # A concurrent ping must succeed while wait_stop is blocked: proof
            # the GDB main thread is not frozen by the long-poll.
            ping = GDBClient(sock_path, timeout=5.0).call("ping")
            self.assertTrue(ping["pong"])
            server._on_gdb_stop(self._fake_event())
            t.join(timeout=5.0)
            self.assertFalse(t.is_alive())
            self.assertTrue(results["wait"]["stopped"])
        finally:
            server.stop()
            t.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
