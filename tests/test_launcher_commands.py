"""Regression tests for GDB command construction in launcher.py.

GDB's `-ex` option does not perform shell quoting. Commands such as
`source`, `set sysroot` and `target extended-remote` consume the rest of
the line literally, so quoting them makes the quotes part of the value.
`file`, `core-file` and `directory`, on the other hand, do strip quotes.
"""

import ast
import unittest
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


if __name__ == "__main__":
    unittest.main()
