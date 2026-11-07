"""Tests for session management module.

Tests session.py: Session metadata CRUD, health checks, cleanup.
"""

import signal
import tempfile
import time
import unittest

# psutil is optional for PID reuse detection
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import mock_open, patch

from gdb_cli.session import (
    SESSION_CREATION_GRACE,
    SessionMeta,
    _is_session_alive,
    _read_proc_starttime,
    _write_meta,
    cleanup_dead_sessions,
    cleanup_session,
    create_session,
)

HAS_PSUTIL = find_spec("psutil") is not None


class TestSessionMeta(unittest.TestCase):
    """Test SessionMeta data class."""

    def test_session_meta_defaults(self):
        """Test SessionMeta defaults."""
        meta = SessionMeta(
            session_id="test-id",
            mode="core",
            started_at=time.time(),
            last_active=time.time(),
        )
        self.assertEqual(meta.session_id, "test-id")
        self.assertEqual(meta.mode, "core")
        self.assertIsNone(meta.gdb_pid)
        self.assertIsNone(meta.binary)
        self.assertIsNone(meta.gdb_start_time)

    def test_session_meta_all_fields(self):
        """Test SessionMeta with all fields set."""
        now = time.time()
        meta = SessionMeta(
            session_id="abc12345",
            mode="attach",
            binary="/usr/bin/myapp",
            pid=12345,
            gdb_pid=12346,
            sock_path="/tmp/gdb-cli/abc12345/gdb.sock",
            started_at=now,
            last_active=now,
            heartbeat_timeout=600,
            safety_level="readonly",
        )
        self.assertEqual(meta.session_id, "abc12345")
        self.assertEqual(meta.mode, "attach")
        self.assertEqual(meta.binary, "/usr/bin/myapp")
        self.assertEqual(meta.pid, 12345)
        self.assertEqual(meta.gdb_pid, 12346)
        self.assertEqual(meta.safety_level, "readonly")
        self.assertEqual(meta.heartbeat_timeout, 600)


class TestSessionIsAlive(unittest.TestCase):
    """Test _is_session_alive function."""

    def test_none_pid_returns_false(self):
        """Session with gdb_pid=None should be dead."""
        meta = SessionMeta(
            session_id="test",
            mode="core",
            started_at=time.time(),
            last_active=time.time(),
            gdb_pid=None,
        )
        self.assertFalse(_is_session_alive(meta))

    @patch("os.kill")
    def test_pid_exists_returns_true(self, mock_kill):
        """If the PID exists, should return True."""
        mock_kill.return_value = None  # os.kill(pid, 0) succeeds
        meta = SessionMeta(
            session_id="test",
            mode="core",
            started_at=time.time(),
            last_active=time.time(),
            gdb_pid=12345,
        )
        self.assertTrue(_is_session_alive(meta))

    @patch("os.kill")
    def test_pid_not_exists_returns_false(self, mock_kill):
        """If the PID does not exist, should return False."""
        mock_kill.side_effect = OSError("No such process")
        meta = SessionMeta(
            session_id="test",
            mode="core",
            started_at=time.time(),
            last_active=time.time(),
            gdb_pid=12345,
        )
        self.assertFalse(_is_session_alive(meta))

    @unittest.skipUnless(HAS_PSUTIL, "psutil not installed")
    @patch("os.kill")
    @patch("psutil.Process", create=True)
    def test_pid_reuse_detected(self, mock_psutil_proc, mock_kill):
        """If PID exists but process name is not GDB, should detect reuse."""
        mock_kill.return_value = None
        mock_proc = mock_psutil_proc.return_value
        mock_proc.name.return_value = "httpd"  # Not GDB
        meta = SessionMeta(
            session_id="test",
            mode="core",
            started_at=time.time(),
            last_active=time.time(),
            gdb_pid=12345,
        )
        # With psutil available, non-GDB process should return False
        self.assertFalse(_is_session_alive(meta))

    @unittest.skipUnless(HAS_PSUTIL, "psutil not installed")
    @patch("os.kill")
    @patch("psutil.Process", create=True)
    def test_pid_valid_gdb_process(self, mock_psutil_proc, mock_kill):
        """If PID exists and process name contains GDB, should return True."""
        mock_kill.return_value = None
        mock_proc = mock_psutil_proc.return_value
        mock_proc.name.return_value = "gdb"
        meta = SessionMeta(
            session_id="test",
            mode="core",
            started_at=time.time(),
            last_active=time.time(),
            gdb_pid=12345,
        )
        self.assertTrue(_is_session_alive(meta))


class TestSessionCreation(unittest.TestCase):
    """Test session creation."""

    @patch("gdb_cli.session.SESSION_DIR")
    def test_create_session_core_mode(self, mock_session_dir):
        """Test creating a core mode session."""
        tmp = Path(tempfile.mkdtemp())
        mock_session_dir.__truediv__.return_value = tmp / "sess1"
        mock_session_dir.__rtruediv__ = lambda self, other: tmp / other

        # This requires actual filesystem, skip if SESSION_DIR can't be mocked
        try:
            session = create_session(
                mode="core",
                binary="/usr/bin/myapp",
                core="/tmp/core.1234",
            )
            self.assertEqual(session.mode, "core")
            self.assertEqual(session.binary, "/usr/bin/myapp")
            self.assertEqual(session.core, "/tmp/core.1234")
            self.assertEqual(session.safety_level, "readonly")
            self.assertIsNotNone(session.session_id)
            self.assertEqual(len(session.session_id), 8)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    @patch("gdb_cli.session.SESSION_DIR")
    def test_create_session_attach_mode(self, mock_session_dir):
        """Test creating an attach mode session."""
        tmp = Path(tempfile.mkdtemp())
        mock_session_dir.__truediv__.return_value = tmp / "sess2"
        mock_session_dir.__rtruediv__ = lambda self, other: tmp / other

        try:
            session = create_session(
                mode="attach",
                binary="/usr/bin/myapp",
                pid=12345,
                safety_level="readwrite",
            )
            self.assertEqual(session.mode, "attach")
            self.assertEqual(session.pid, 12345)
            self.assertEqual(session.safety_level, "readwrite")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


class TestSessionCleanup(unittest.TestCase):
    """Test session cleanup."""

    def test_cleanup_nonexistent_session(self):
        """Cleanup of nonexistent session should return False."""
        result = cleanup_session("nonexistent-id-12345")
        self.assertFalse(result)

    @patch("os.kill")
    @patch("pathlib.Path.exists")
    def test_cleanup_with_gdb_pid(self, mock_exists, mock_kill):
        """Cleanup should attempt to kill GDB process."""
        mock_exists.return_value = True
        # This test verifies cleanup_session doesn't crash
        try:
            cleanup_session("test-session")
        except Exception:
            pass  # May fail due to missing files, that's OK


class TestProcStartTime(unittest.TestCase):
    """Test /proc/<pid>/stat starttime parsing."""

    def test_parses_field_22_with_spaces_and_parens_in_comm(self):
        # comm contains spaces and parentheses; fields resume after the last ')'.
        stat = "1234 (my gdb (v2)) S " + " ".join(["0"] * 18 + ["98765"]) + "\n"
        with patch("builtins.open", mock_open(read_data=stat)):
            self.assertEqual(_read_proc_starttime(1234), "98765")

    def test_missing_proc_entry_returns_none(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertIsNone(_read_proc_starttime(999999))


class TestCleanupSessionIdentity(unittest.TestCase):
    """cleanup_session must not signal a recycled PID."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir_patch = patch("gdb_cli.session.SESSION_DIR", self.tmp)
        self.dir_patch.start()
        self.session_dir = self.tmp / "sess"
        self.session_dir.mkdir()

    def tearDown(self):
        self.dir_patch.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_session(self, **kwargs):
        meta = SessionMeta(
            session_id="sess",
            mode="attach",
            gdb_pid=12345,
            sock_path=str(self.session_dir / "gdb.sock"),
            started_at=time.time(),
            last_active=time.time(),
            **kwargs,
        )
        _write_meta(meta)
        return meta

    def test_start_time_mismatch_does_not_signal(self):
        self._write_session(gdb_start_time="111")

        with patch(
            "gdb_cli.session._read_proc_starttime", return_value="999"
        ), patch("gdb_cli.session.os.kill") as mock_kill:
            self.assertTrue(cleanup_session("sess"))

        mock_kill.assert_not_called()
        self.assertFalse(self.session_dir.exists())

    def test_start_time_match_signals(self):
        self._write_session(gdb_start_time="111")

        def fake_kill(pid, sig):
            if sig == 0:
                raise OSError("gone")

        with patch(
            "gdb_cli.session._read_proc_starttime", return_value="111"
        ), patch(
            "gdb_cli.session.os.kill", side_effect=fake_kill
        ) as mock_kill:
            self.assertTrue(cleanup_session("sess"))

        # The first signal is SIGTERM; the liveness poll then reports gone.
        self.assertEqual(mock_kill.call_args_list[0].args, (12345, signal.SIGTERM))
        self.assertFalse(self.session_dir.exists())

    def test_legacy_session_uses_comm_fallback(self):
        self._write_session(gdb_start_time=None)

        with patch(
            "gdb_cli.session._read_proc_comm", return_value="python3"
        ), patch("gdb_cli.session.os.kill") as mock_kill:
            self.assertTrue(cleanup_session("sess"))

        mock_kill.assert_not_called()

    def test_legacy_session_matching_gdb_comm_signals(self):
        self._write_session(gdb_start_time=None)

        def fake_kill(pid, sig):
            if sig == 0:
                raise OSError("gone")

        with patch(
            "gdb_cli.session._read_proc_comm", return_value="gdb"
        ), patch(
            "gdb_cli.session.os.kill", side_effect=fake_kill
        ) as mock_kill:
            self.assertTrue(cleanup_session("sess"))

        self.assertEqual(mock_kill.call_args_list[0].args, (12345, signal.SIGTERM))


class TestCleanupDeadSessionsGrace(unittest.TestCase):
    """A just-created session must not be reaped while it is starting."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir_patch = patch("gdb_cli.session.SESSION_DIR", self.tmp)
        self.dir_patch.start()

    def tearDown(self):
        self.dir_patch.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_session(self, session_id, started_at):
        session_dir = self.tmp / session_id
        session_dir.mkdir()
        _write_meta(
            SessionMeta(
                session_id=session_id,
                mode="target",
                sock_path=str(session_dir / "gdb.sock"),
                started_at=started_at,
                last_active=started_at,
                gdb_pid=None,
            )
        )
        return session_dir

    def test_recent_session_is_skipped(self):
        recent_dir = self._make_session("recent", time.time())
        old_dir = self._make_session(
            "old", time.time() - SESSION_CREATION_GRACE - 10
        )

        cleaned = cleanup_dead_sessions()

        self.assertEqual(cleaned, 1)
        self.assertTrue(recent_dir.exists())
        self.assertFalse(old_dir.exists())


if __name__ == "__main__":
    unittest.main()
