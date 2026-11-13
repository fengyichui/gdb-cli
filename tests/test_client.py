"""Tests for GDB client module.

Tests client.py: Unix Domain Socket client, JSON-RPC communication.
"""

import json
import socket
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gdb_cli.client import GDBClient, GDBClientError, GDBCommandError


class TestGDBClientInit(unittest.TestCase):
    """Test GDBClient initialization."""

    def test_init_with_sock_path(self):
        """Test client creation with socket path."""
        client = GDBClient("/tmp/test.sock")
        self.assertEqual(client.sock_path, Path("/tmp/test.sock"))
        self.assertFalse(client.is_connected())

    def test_init_default_timeout(self):
        """Test client has default timeout."""
        client = GDBClient("/tmp/test.sock")
        self.assertIsNotNone(client.timeout)


class TestGDBClientCall(unittest.TestCase):
    """Test JSON-RPC call method."""

    def setUp(self):
        self.client = GDBClient("/tmp/test.sock")

    @patch("socket.socket")
    @patch("pathlib.Path.exists", return_value=True)
    def test_call_sends_json_rpc_request(self, mock_exists, mock_socket_class):
        """Test call sends proper JSON-RPC request and returns data."""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock

        response = {"ok": True, "data": {"result": "ok"}}
        mock_sock.recv.side_effect = [
            json.dumps(response).encode(),
            b"",  # EOF
        ]

        result = self.client.call("eval", expr="x")
        self.assertEqual(result, {"result": "ok"})
        mock_sock.connect.assert_called_once()

    @patch("socket.socket")
    @patch("pathlib.Path.exists", return_value=True)
    def test_call_handles_error_response(self, mock_exists, mock_socket_class):
        """Test call raises GDBCommandError on error response."""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock

        response = {"ok": False, "error": "Cannot access memory at 0x0"}
        mock_sock.recv.side_effect = [
            json.dumps(response).encode(),
            b"",
        ]

        with self.assertRaises(GDBCommandError) as ctx:
            self.client.call("eval", expr="invalid_ptr")
        self.assertIn("Cannot access memory", str(ctx.exception))

    @patch("socket.socket")
    @patch("pathlib.Path.exists", return_value=True)
    def test_call_connection_refused(self, mock_exists, mock_socket_class):
        """Test call handles connection refused."""
        mock_sock = Mock()
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")
        mock_socket_class.return_value = mock_sock

        with self.assertRaises(GDBClientError):
            self.client.call("status")

    @patch("socket.socket")
    @patch("pathlib.Path.exists", return_value=True)
    def test_call_timeout(self, mock_exists, mock_socket_class):
        """Test call handles socket timeout."""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = socket.timeout("timed out")

        with self.assertRaises(GDBClientError):
            self.client.call("status")

    def test_call_when_socket_not_found(self):
        """Test call when socket path doesn't exist."""
        client = GDBClient("/tmp/nonexistent-sock-xyz.sock", timeout=0.1)
        with self.assertRaises(GDBClientError):
            client.call("status")


class TestGDBClientExecCmd(unittest.TestCase):
    """Test exec_cmd convenience method (no longer sends safety_level)."""

    @patch("socket.socket")
    @patch("pathlib.Path.exists", return_value=True)
    def test_exec_cmd_sends_exec_request(self, mock_exists, mock_socket_class):
        """exec_cmd sends 'exec' command WITHOUT safety_level (Issue #3 fix)."""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock

        response = {"ok": True, "data": {"command": "bt", "output": "#0 main"}}
        mock_sock.recv.side_effect = [
            json.dumps(response).encode(),
            b"",
        ]

        client = GDBClient("/tmp/test.sock")
        result = client.exec_cmd("bt")
        self.assertIn("command", result)

        # Verify request didn't include safety_level (removed in Issue #3 fix)
        sent_data = mock_sock.sendall.call_args[0][0]
        request = json.loads(sent_data)
        self.assertEqual(request["cmd"], "exec")
        self.assertEqual(request["command"], "bt")
        self.assertNotIn("safety_level", request)


class TestGDBClientContextManager(unittest.TestCase):
    """Test GDBClient as context manager."""

    @patch("socket.socket")
    @patch("pathlib.Path.exists", return_value=True)
    def test_context_manager_connects_and_closes(self, mock_exists, mock_socket_class):
        """Test client connects on enter and closes on exit."""
        mock_sock = Mock()
        mock_socket_class.return_value = mock_sock

        with GDBClient("/tmp/test.sock") as client:
            self.assertTrue(client.is_connected())
            mock_sock.connect.assert_called_once()

        mock_sock.close.assert_called_once()


class TestGDBClientConvenienceMethods(unittest.TestCase):
    """The CLI/e2e surface relies on these convenience wrappers."""

    def setUp(self):
        self.client = GDBClient("/tmp/test.sock")

    def test_ptype_sends_ptype_command(self):
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.ptype("struct foo")

        mock_call.assert_called_once_with("ptype", expr="struct foo")

    def test_sharedlibs_sends_sharedlibs_command(self):
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.sharedlibs()

        mock_call.assert_called_once_with("sharedlibs")

    def test_disasm_sends_expected_params(self):
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.disasm(start="main", count=5, thread_id=2, frame=1)

        mock_call.assert_called_once_with(
            "disasm", start="main", count=5, frame=1, thread_id=2
        )

    def test_disasm_omits_none_start_and_thread(self):
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.disasm()

        mock_call.assert_called_once_with("disasm", count=20, frame=0)

    def test_eval_forwards_deref(self):
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.eval("ptr", deref=True)

        mock_call.assert_called_once_with(
            "eval",
            expr="ptr",
            max_depth=3,
            max_elements=50,
            deref=True,
        )

    def test_wait_stop_socket_timeout_exceeds_server_wait(self):
        """The server's clean timeout must win over a socket timeout."""
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.wait_stop(timeout=30.0)

        mock_call.assert_called_once_with(
            "wait_stop", timeout=35.0, wait_timeout=30.0
        )

    def test_wait_stop_custom_timeout(self):
        with patch.object(GDBClient, "call", return_value={}) as mock_call:
            self.client.wait_stop(timeout=2.0)

        mock_call.assert_called_once_with(
            "wait_stop", timeout=7.0, wait_timeout=2.0
        )


class TestGDBCommandError(unittest.TestCase):
    """Test GDBCommandError class."""

    def test_error_creation(self):
        """Test GDBCommandError stores message and command."""
        error = GDBCommandError("something went wrong", "test command")
        self.assertEqual(str(error), "something went wrong")
        self.assertEqual(error.command, "test command")


class TestGDBClientError(unittest.TestCase):
    """Test GDBClientError class."""

    def test_error_creation(self):
        """Test GDBClientError can be created."""
        error = GDBClientError("Connection failed")
        self.assertEqual(str(error), "Connection failed")


if __name__ == "__main__":
    unittest.main()
