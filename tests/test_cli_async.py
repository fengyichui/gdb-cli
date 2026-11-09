"""Tests for CLI async load/status behavior without requiring Click at runtime."""

import importlib
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch


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


class TestCLIAsyncBehavior(unittest.TestCase):
    """Verify CLI surface behavior for async load/status."""

    @classmethod
    def setUpClass(cls):
        sys.modules["click"] = _FakeClick()
        cls.cli = importlib.import_module("gdb_cli.cli")

    def test_load_reports_loading_status(self):
        fake_process = Mock()
        fake_process.pid = 12345
        fake_process.session = types.SimpleNamespace(
            session_id="abc12345",
            mode="core",
            binary="/tmp/a.out",
            core="/tmp/core.1",
            sock_path="/tmp/test.sock",
        )

        with patch.object(self.cli, "find_session_by_core", return_value=None), \
             patch.object(self.cli, "launch_core", return_value=fake_process), \
             patch.object(self.cli, "print_json") as mock_print_json:
            self.cli.load("/tmp/a.out", "/tmp/core.1", None, None, None, 600, "gdb")

        payload = mock_print_json.call_args.args[0]
        self.assertEqual(payload["status"], "loading")
        self.assertEqual(payload["session_id"], "abc12345")

    def test_status_reports_unresponsive_for_old_session(self):
        meta = types.SimpleNamespace(gdb_pid=12345, started_at=time.time() - 150)

        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("socket not ready")), \
             patch.object(self.cli, "get_session", return_value=meta), \
             patch.object(self.cli.os, "kill", return_value=None), \
             patch.object(self.cli, "print_json") as mock_print_json:
            self.cli.status("abc12345")

        payload = mock_print_json.call_args.args[0]
        self.assertEqual(payload["state"], "unresponsive")
        self.assertEqual(payload["session_id"], "abc12345")
        self.assertIn("socket not ready", payload["error"])

    def test_status_reports_loading_for_young_session(self):
        meta = types.SimpleNamespace(gdb_pid=12345, started_at=time.time() - 5)

        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("socket not ready")), \
             patch.object(self.cli, "get_session", return_value=meta), \
             patch.object(self.cli.os, "kill", return_value=None), \
             patch.object(self.cli, "print_json") as mock_print_json:
            self.cli.status("abc12345")

        payload = mock_print_json.call_args.args[0]
        self.assertEqual(payload["state"], "loading")

    def test_stop_reports_graceful_detach(self):
        fake_client = Mock()
        fake_client.__enter__ = Mock(return_value=fake_client)
        fake_client.__exit__ = Mock(return_value=False)
        fake_client.call.return_value = {"detached": True, "errors": []}
        meta = types.SimpleNamespace(gdb_pid=4242, started_at=time.time())

        with patch.object(self.cli, "get_client", return_value=fake_client), \
             patch.object(self.cli, "get_session", return_value=meta), \
             patch.object(self.cli.os, "kill", side_effect=OSError()), \
             patch("gdb_cli.session.cleanup_session", return_value=True) as mock_cleanup, \
             patch.object(self.cli, "print_json") as mock_print_json:
            self.cli.stop("abc12345", "monitor go", False)

        fake_client.call.assert_called_once_with("stop", before_detach="monitor go")
        mock_cleanup.assert_called_once_with("abc12345")
        payload = mock_print_json.call_args.args[0]
        self.assertEqual(payload["status"], "stopped")
        self.assertTrue(payload["detached"])

    def test_stop_waits_for_process_exit_before_cleanup(self):
        fake_client = Mock()
        fake_client.__enter__ = Mock(return_value=fake_client)
        fake_client.__exit__ = Mock(return_value=False)
        fake_client.call.return_value = {"detached": True, "errors": []}
        meta = types.SimpleNamespace(gdb_pid=4242, started_at=time.time())

        with patch.object(self.cli, "get_client", return_value=fake_client), \
             patch.object(self.cli, "get_session", return_value=meta), \
             patch.object(self.cli.os, "kill", side_effect=[None, OSError()]) as mock_kill, \
             patch.object(self.cli.time, "sleep") as mock_sleep, \
             patch("gdb_cli.session.cleanup_session", return_value=True) as mock_cleanup, \
             patch.object(self.cli, "print_json"):
            self.cli.stop("abc12345", None, False)

        # Polled twice: alive on the first check, gone on the second.
        self.assertEqual(mock_kill.call_count, 2)
        mock_sleep.assert_called_once()
        mock_cleanup.assert_called_once_with("abc12345")

    def test_stop_rpc_failure_without_force_exits_without_cleanup(self):
        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("dead")), \
             patch("gdb_cli.session.cleanup_session") as mock_cleanup, \
             patch.object(self.cli, "print_error") as mock_print_error:
            with self.assertRaises(self.cli.click.exceptions.Exit) as ctx:
                self.cli.stop("abc12345", None, False)

        self.assertEqual(ctx.exception.exit_code, 1)
        mock_cleanup.assert_not_called()
        mock_print_error.assert_called_once()

    def test_stop_rpc_failure_with_force_cleans_up(self):
        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("dead")), \
             patch("gdb_cli.session.cleanup_session", return_value=True) as mock_cleanup, \
             patch.object(self.cli, "print_json") as mock_print_json:
            self.cli.stop("abc12345", None, True)

        mock_cleanup.assert_called_once_with("abc12345")
        payload = mock_print_json.call_args.args[0]
        self.assertEqual(payload["status"], "force_stopped")

    def test_stop_force_cleanup_failure_exits(self):
        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("dead")), \
             patch("gdb_cli.session.cleanup_session", return_value=False), \
             patch.object(self.cli, "print_error") as mock_print_error:
            with self.assertRaises(self.cli.click.exceptions.Exit) as ctx:
                self.cli.stop("abc12345", None, True)

        self.assertEqual(ctx.exception.exit_code, 1)
        mock_print_error.assert_called_once()

    def test_eval_command_error_exits_with_code_1(self):
        fake_client = Mock()
        fake_client.__enter__ = Mock(return_value=fake_client)
        fake_client.__exit__ = Mock(return_value=False)
        fake_client.eval.side_effect = self.cli.GDBCommandError("bad expression")

        with patch.object(self.cli, "get_client", return_value=fake_client), \
             patch.object(self.cli, "print_error") as mock_print_error:
            with self.assertRaises(self.cli.click.exceptions.Exit) as ctx:
                self.cli.eval_cmd("abc", "x", 3, 50, False)

        self.assertEqual(ctx.exception.exit_code, 1)
        mock_print_error.assert_called_once()

    def test_eval_deref_flag_is_forwarded(self):
        fake_client = Mock()
        fake_client.__enter__ = Mock(return_value=fake_client)
        fake_client.__exit__ = Mock(return_value=False)
        fake_client.eval.return_value = {}

        with patch.object(self.cli, "get_client", return_value=fake_client), \
             patch.object(self.cli, "print_json"):
            self.cli.eval_cmd("abc", "ptr", 3, 50, True)

        fake_client.eval.assert_called_once_with(
            "ptr", max_depth=3, max_elements=50, deref=True
        )

    def test_target_accepts_bracketed_ipv6_and_passes_remote_mode(self):
        fake_process = Mock()
        fake_process.pid = 1
        fake_process.session = types.SimpleNamespace(
            session_id="abc",
            mode="target",
            remote="[::1]:2331",
            binary=None,
            sock_path="/tmp/x.sock",
            safety_level="readonly",
        )

        with patch.object(self.cli, "find_session_by_remote", return_value=None), \
             patch.object(self.cli, "launch_target", return_value=fake_process) as mock_launch, \
             patch.object(self.cli, "print_json"):
            self.cli.target(
                remote="[::1]:2331",
                binary=None,
                remote_mode="remote",
                scheduler_locking=False,
                non_stop=False,
                timeout=600,
                allow_write=False,
                allow_call=False,
                safety=False,
                gdb_path="gdb",
            )

        kwargs = mock_launch.call_args.kwargs
        self.assertEqual(kwargs["remote_mode"], "remote")
        self.assertFalse(kwargs["scheduler_locking"])

    def test_target_rejects_invalid_endpoint(self):
        with patch.object(self.cli, "print_error") as mock_print_error:
            with self.assertRaises(self.cli.click.exceptions.Exit) as ctx:
                self.cli.target(
                    remote="not-an-address",
                    binary=None,
                    remote_mode="extended-remote",
                    scheduler_locking=False,
                    non_stop=False,
                    timeout=600,
                    allow_write=False,
                    allow_call=False,
                    safety=False,
                    gdb_path="gdb",
                )

        self.assertEqual(ctx.exception.exit_code, 1)
        mock_print_error.assert_called_once()

    def test_every_cli_translation_key_exists_in_english_catalog(self):
        import ast
        from pathlib import Path

        from gdb_cli.locales.en import ENGLISH_CATALOG

        tree = ast.parse(Path(self.cli.__file__).read_text(encoding="utf-8"))
        keys = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)

        missing = sorted(key for key in keys if key not in ENGLISH_CATALOG)
        self.assertEqual(missing, [])

    def test_status_errors_when_session_dead(self):
        meta = types.SimpleNamespace(gdb_pid=12345)

        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("socket not ready")), \
             patch.object(self.cli, "get_session", return_value=meta), \
             patch.object(self.cli.os, "kill", side_effect=OSError()), \
             patch.object(self.cli, "print_error") as mock_print_error:
            with self.assertRaises(self.cli.click.exceptions.Exit):
                self.cli.status("abc12345")

        mock_print_error.assert_called_once()

    def test_status_errors_when_session_missing(self):
        with patch.object(self.cli, "get_client", side_effect=self.cli.GDBClientError("socket not ready")), \
             patch.object(self.cli, "get_session", return_value=None), \
             patch.object(self.cli, "print_error") as mock_print_error:
            with self.assertRaises(self.cli.click.exceptions.Exit):
                self.cli.status("missing")

        mock_print_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
