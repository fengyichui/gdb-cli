"""Regression tests for GDB command construction in launcher.py.

GDB's `-ex` option does not perform shell quoting. Commands such as
`source`, `set sysroot` and `target extended-remote` consume the rest of
the line literally, so quoting them makes the quotes part of the value.
`file`, `core-file` and `directory`, on the other hand, do strip quotes.
"""

import ast
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gdb_cli.session import SessionMeta


def _extract_commands(mock_start):
    """Return the -ex command strings passed to _start_gdb_process."""
    args = mock_start.call_args.args[0]
    return [args[i + 1] for i, value in enumerate(args[:-1]) if value == "-ex"]


def _make_session(**kwargs):
    session = SessionMeta(
        session_id="test1234",
        sock_path="/tmp/test.sock",
        heartbeat_timeout=30,
        **kwargs,
    )
    session._gdb_process = Mock(pid=1234)
    return session


class TestLaunchTargetCommands(unittest.TestCase):
    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_remote_and_source_are_not_quoted(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_target

        mock_create_session.return_value = _make_session(
            mode="target", remote="127.0.0.1:2331"
        )

        launch_target(remote="127.0.0.1:2331", binary="/tmp/a.out")

        commands = _extract_commands(mock_start)
        self.assertIn("target extended-remote 127.0.0.1:2331", commands)
        # file/core-file strip quotes, so quoting is correct there.
        self.assertIn("file '/tmp/a.out'", commands)

        source_cmd = next(cmd for cmd in commands if cmd.startswith("source "))
        self.assertNotIn("'", source_cmd)

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_python_env_commands_are_valid_literals(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_target

        mock_create_session.return_value = _make_session(
            mode="target", remote="127.0.0.1:2331"
        )

        launch_target(
            remote="127.0.0.1:2331",
            binary="/tmp/a.out",
            gdb_path="/opt/arm-none-eabi-gdb/bin/arm-none-eabi-gdb",
        )

        commands = _extract_commands(mock_start)
        env_commands = [
            cmd for cmd in commands
            if cmd.startswith("python os.environ['GDB_CLI_")
        ]
        self.assertTrue(env_commands)

        for cmd in env_commands:
            tree = ast.parse(cmd[len("python "):])
            assign = tree.body[0]
            # Raises ValueError if the emitted literal is not valid Python.
            value = ast.literal_eval(assign.value)
            self.assertIsInstance(value, str)


class TestLaunchCoreCommands(unittest.TestCase):
    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_sysroot_and_solib_prefix_are_not_quoted(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_core

        mock_create_session.return_value = _make_session(
            mode="core", binary="/tmp/a.out", core="/tmp/core.1"
        )

        launch_core(
            binary="/tmp/a.out",
            core="/tmp/core.1",
            sysroot="/opt/sysroot",
            solib_prefix="/opt/sysroot/lib",
            source_dir="/src/project",
        )

        commands = _extract_commands(mock_start)
        self.assertIn("set sysroot /opt/sysroot", commands)
        self.assertIn("set solib-absolute-prefix /opt/sysroot/lib", commands)
        # directory strips quotes, so quoting is correct here.
        self.assertIn("directory '/src/project'", commands)
        self.assertIn("file '/tmp/a.out'", commands)
        self.assertIn("core-file '/tmp/core.1'", commands)


class TestQuoteHelpers(unittest.TestCase):
    def test_filename_quoting_handles_single_quote(self):
        from gdb_cli.launcher import _quote_gdb_filename

        self.assertEqual(
            _quote_gdb_filename("/tmp/it's.bin"),
            "'/tmp/it'\\''s.bin'",
        )

    def test_rest_of_line_passes_through_unchanged(self):
        from gdb_cli.launcher import _gdb_rest_of_line

        self.assertEqual(
            _gdb_rest_of_line("/tmp/with space/file"),
            "/tmp/with space/file",
        )


def _server_meta_from_commands(commands):
    """Parse the session_meta dict literal passed to start_server()."""
    cmd = next(c for c in commands if c.startswith("python start_server("))
    tree = ast.parse(cmd[len("python "):])
    call = tree.body[0].value
    return ast.literal_eval(call.args[1])


def _env_meta_from_commands(commands):
    cmd = next(
        c for c in commands
        if c.startswith("python os.environ['GDB_CLI_SESSION_META']")
    )
    value = ast.parse(cmd[len("python "):]).body[0].value
    return json.loads(ast.literal_eval(value))


class TestSafetyLevelPropagation(unittest.TestCase):
    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_server_meta_contains_safety_level(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_target

        for level in ("readonly", "readwrite", "full"):
            with self.subTest(level=level):
                mock_start.reset_mock()
                mock_create_session.return_value = _make_session(
                    mode="target", remote="127.0.0.1:1234", safety_level=level
                )

                launch_target(remote="127.0.0.1:1234")

                commands = _extract_commands(mock_start)
                self.assertEqual(
                    _server_meta_from_commands(commands)["safety_level"], level
                )
                self.assertEqual(
                    _env_meta_from_commands(commands)["safety_level"], level
                )


class TestSafetyCommands(unittest.TestCase):
    EXPECTED = {
        "readonly": [
            "set may-write-memory off",
            "set may-write-registers off",
            "set may-call-functions off",
        ],
        "readwrite": [
            "set may-write-memory on",
            "set may-write-registers on",
            "set may-call-functions off",
        ],
        "full": [
            "set may-write-memory on",
            "set may-write-registers on",
            "set may-call-functions on",
        ],
    }

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_target_injects_safety_commands_by_level(
        self, mock_create_session, mock_start
    ):
        from gdb_cli.launcher import launch_target

        for level, expected in self.EXPECTED.items():
            with self.subTest(level=level):
                mock_start.reset_mock()
                mock_create_session.return_value = _make_session(
                    mode="target", remote="127.0.0.1:1234", safety_level=level
                )

                launch_target(remote="127.0.0.1:1234")

                commands = _extract_commands(mock_start)
                # Injected directly after the initial pagination/print/confirm.
                self.assertEqual(
                    commands[:3],
                    [
                        "set pagination off",
                        "set print elements 0",
                        "set confirm off",
                    ],
                )
                self.assertEqual(commands[3:6], expected)

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_attach_injects_safety_commands(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_attach

        mock_create_session.return_value = _make_session(
            mode="attach", pid=4242, safety_level="readwrite"
        )

        with patch("gdb_cli.launcher._check_process_exists", return_value=True):
            launch_attach(pid=4242)

        commands = _extract_commands(mock_start)
        self.assertEqual(commands[3:6], self.EXPECTED["readwrite"])

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_core_always_forces_readonly(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_core

        # Even if the session somehow claims full access, a core is read-only.
        mock_create_session.return_value = _make_session(
            mode="core", binary="/tmp/a.out", core="/tmp/core.1",
            safety_level="full",
        )

        launch_core(binary="/tmp/a.out", core="/tmp/core.1")

        commands = _extract_commands(mock_start)
        self.assertEqual(commands[3:6], self.EXPECTED["readonly"])


class TestTargetOptions(unittest.TestCase):
    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_remote_mode_selects_target_command(
        self, mock_create_session, mock_start
    ):
        from gdb_cli.launcher import launch_target

        cases = [
            ("remote", "target remote host:1234"),
            ("extended-remote", "target extended-remote host:1234"),
            ("bogus-mode", "target extended-remote host:1234"),
        ]
        for mode, expected in cases:
            with self.subTest(mode=mode):
                mock_start.reset_mock()
                mock_create_session.return_value = _make_session(
                    mode="target", remote="host:1234"
                )

                launch_target(remote="host:1234", remote_mode=mode)

                commands = _extract_commands(mock_start)
                self.assertIn(expected, commands)

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_scheduler_locking_defaults_off(self, mock_create_session, mock_start):
        from gdb_cli.launcher import launch_target

        mock_create_session.return_value = _make_session(
            mode="target", remote="host:1234"
        )

        launch_target(remote="host:1234")

        commands = _extract_commands(mock_start)
        self.assertNotIn("set scheduler-locking on", commands)

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_scheduler_locking_can_be_enabled(
        self, mock_create_session, mock_start
    ):
        from gdb_cli.launcher import launch_target

        mock_create_session.return_value = _make_session(
            mode="target", remote="host:1234"
        )

        launch_target(remote="host:1234", scheduler_locking=True)

        commands = _extract_commands(mock_start)
        self.assertIn("set scheduler-locking on", commands)


class TestStartProcess(unittest.TestCase):
    def _run_start(self, tmp, process, wait_side_effect=None,
                   starttime="98765"):
        """Invoke _start_gdb_process against a temporary session directory."""
        from gdb_cli import launcher

        session = SessionMeta(
            session_id="test1234",
            mode="target",
            sock_path=str(Path(tmp) / "gdb.sock"),
            heartbeat_timeout=600,
        )
        popen_patch = patch(
            "gdb_cli.launcher.subprocess.Popen", return_value=process
        )
        patches = [
            popen_patch,
            patch("gdb_cli.session._write_meta"),
            patch("gdb_cli.session._read_proc_starttime",
                  return_value=starttime),
        ]
        if wait_side_effect is None:
            patches.append(
                patch("gdb_cli.launcher._wait_for_socket", return_value=None)
            )
        else:
            patches.append(
                patch(
                    "gdb_cli.launcher._wait_for_socket",
                    side_effect=wait_side_effect,
                )
            )

        for p in patches[1:]:
            p.start()
        popen_mock = popen_patch.start()
        try:
            result = launcher._start_gdb_process(["gdb", "-nx"], session)
        finally:
            popen_patch.stop()
            for p in reversed(patches[1:]):
                p.stop()

        return launcher, session, result, popen_mock

    def test_start_failure_terminates_and_kills_process(self):
        from gdb_cli import launcher

        process = Mock(pid=12345)
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired("gdb", 5.0),
            None,
        ]

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(launcher.GDBLauncherError):
                self._run_start(
                    tmp, process,
                    wait_side_effect=launcher.GDBLauncherError("no socket"),
                )

            process.terminate.assert_called_once()
            process.kill.assert_called_once()
            self.assertFalse((Path(tmp) / "gdb.stdin").exists())

    def test_stdout_and_stderr_share_log_file(self):
        process = Mock(pid=12345)
        process.poll.return_value = None

        with tempfile.TemporaryDirectory() as tmp:
            launcher, session, result, popen_patch = self._run_start(
                tmp, process
            )

            self.assertIs(result, process)
            kwargs = popen_patch.call_args.kwargs
            self.assertIsNot(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stdout"], kwargs["stderr"])
            self.assertEqual(
                kwargs["stdout"].name, str(Path(tmp) / "gdb.log")
            )
            self.assertEqual(session.gdb_pid, 12345)
            self.assertEqual(session.gdb_start_time, "98765")

    @patch("gdb_cli.launcher._start_gdb_process")
    @patch("gdb_cli.launcher.create_session")
    def test_launch_uses_socket_wait_timeout_not_heartbeat(
        self, mock_create_session, mock_start
    ):
        from gdb_cli import launcher
        from gdb_cli.launcher import launch_target

        mock_create_session.return_value = _make_session(
            mode="target", remote="host:1234"
        )

        # Heartbeat is 600s; the socket wait must stay bounded.
        launch_target(remote="host:1234", timeout=600)

        self.assertEqual(
            mock_start.call_args.kwargs["timeout"],
            launcher.SOCKET_WAIT_TIMEOUT,
        )


if __name__ == "__main__":
    unittest.main()
