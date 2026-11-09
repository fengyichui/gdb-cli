"""Tests for command handlers module.

Tests handlers.py: command handlers with mocked gdb module.
"""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

# Mock gdb module before any imports that depend on it
sys.modules['gdb'] = MagicMock()

# Set up the server directory for value_formatter import
_server_dir = str(Path(__file__).parent.parent / "src" / "gdb_cli" / "gdb_server")
os.environ["GDB_CLI_SERVER_DIR"] = _server_dir


class TestHandleExec(unittest.TestCase):
    """Test raw command execution handler with safety filtering."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_exec_allowed_read_command(self):
        """exec of a read command should be allowed."""
        # Make gdb.post_event call the function directly
        sys.modules['gdb'].post_event = lambda fn: fn()
        sys.modules['gdb'].execute = Mock(return_value="#0 main at foo.c:10")

        result = self.handlers.handle_exec("bt", safety_level="readonly")
        self.assertIn("command", result)
        self.assertEqual(result["command"], "bt")

    def test_exec_shell_blocked(self):
        """exec of 'shell' must be blocked."""
        result = self.handlers.handle_exec("shell ls", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_python_blocked(self):
        """exec of 'python' must be blocked (Issue #1 fix)."""
        result = self.handlers.handle_exec("python import os; os.system('id')", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_python_interactive_blocked(self):
        """exec of 'python-interactive' must be blocked."""
        result = self.handlers.handle_exec("python-interactive", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_quit_blocked(self):
        """exec of 'quit' must be blocked."""
        result = self.handlers.handle_exec("quit", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_kill_blocked(self):
        """exec of 'kill' must be blocked."""
        result = self.handlers.handle_exec("kill", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_signal_blocked(self):
        """exec of 'signal' must be blocked."""
        result = self.handlers.handle_exec("signal 9", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_set_blocked_in_readonly(self):
        """exec of 'set' must be blocked in readonly mode."""
        result = self.handlers.handle_exec("set variable x=42", safety_level="readonly")
        self.assertIn("error", result)

    def test_exec_set_allowed_in_full(self):
        """exec of 'set' must be allowed in full mode."""
        # Make gdb.post_event call the function directly
        sys.modules['gdb'].post_event = lambda fn: fn()
        sys.modules['gdb'].execute = Mock(return_value="")

        result = self.handlers.handle_exec("set variable x=42", safety_level="full")
        self.assertNotIn("error", result)

    def test_exec_attach_blocked(self):
        """exec of 'attach' must be blocked."""
        result = self.handlers.handle_exec("attach 12345", safety_level="full")
        self.assertIn("error", result)

    def test_exec_detach_blocked(self):
        """exec of 'detach' must be blocked."""
        result = self.handlers.handle_exec("detach", safety_level="full")
        self.assertIn("error", result)

    def test_exec_target_blocked(self):
        """exec of 'target' must be blocked."""
        result = self.handlers.handle_exec("target extended-remote :3333", safety_level="full")
        self.assertIn("error", result)

    def test_exec_everything_allowed_in_off(self):
        """off disables the filter entirely (default sessions)."""
        sys.modules['gdb'].post_event = lambda fn: fn()
        sys.modules['gdb'].execute = Mock(return_value="")

        for command in (
            "source /tmp/x.gdb",
            "python import os",
            "python-interactive",
            "shell ls",
            "quit",
            "kill",
            "attach 12345",
            "detach",
            "target extended-remote :3333",
            "bt\npython print(1)",
        ):
            with self.subTest(command=command):
                result = self.handlers.handle_exec(
                    command, safety_level="off"
                )
                self.assertNotIn("error", result)


class TestHandleThreadApply(unittest.TestCase):
    """Test thread_apply handler with safety filtering."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_thread_apply_shell_blocked(self):
        """thread-apply with 'shell' must be blocked (Issue #2 fix)."""
        # Mock inferior threads
        mock_thread = Mock()
        mock_thread.num = 1
        mock_inferior = Mock()
        mock_inferior.threads.return_value = [mock_thread]
        sys.modules['gdb'].selected_inferior = Mock(return_value=mock_inferior)
        sys.modules['gdb'].selected_thread = Mock(return_value=mock_thread)

        result = self.handlers.handle_thread_apply(
            command="shell ls",
            all_threads=True,
            safety_level="readonly",
        )
        self.assertIn("error", result)

    def test_thread_apply_python_blocked(self):
        """thread-apply with 'python' must be blocked (Issue #2 fix)."""
        mock_thread = Mock()
        mock_thread.num = 1
        mock_inferior = Mock()
        mock_inferior.threads.return_value = [mock_thread]
        sys.modules['gdb'].selected_inferior = Mock(return_value=mock_inferior)
        sys.modules['gdb'].selected_thread = Mock(return_value=mock_thread)

        result = self.handlers.handle_thread_apply(
            command="python import os",
            all_threads=True,
            safety_level="readonly",
        )
        self.assertIn("error", result)

    def test_thread_apply_quit_blocked(self):
        """thread-apply with 'quit' must be blocked."""
        mock_thread = Mock()
        mock_thread.num = 1
        mock_inferior = Mock()
        mock_inferior.threads.return_value = [mock_thread]
        sys.modules['gdb'].selected_inferior = Mock(return_value=mock_inferior)
        sys.modules['gdb'].selected_thread = Mock(return_value=mock_thread)

        result = self.handlers.handle_thread_apply(
            command="quit",
            all_threads=True,
            safety_level="readonly",
        )
        self.assertIn("error", result)

    def test_thread_apply_allowed_read_command(self):
        """thread-apply with 'bt' should be allowed."""
        mock_thread = Mock()
        mock_thread.num = 1
        mock_inferior = Mock()
        mock_inferior.threads.return_value = [mock_thread]
        sys.modules['gdb'].selected_inferior = Mock(return_value=mock_inferior)
        sys.modules['gdb'].selected_thread = Mock(return_value=mock_thread)
        sys.modules['gdb'].execute = Mock(return_value="#0 main at foo.c:10")

        result = self.handlers.handle_thread_apply(
            command="bt",
            all_threads=True,
            safety_level="readonly",
        )
        self.assertNotIn("error", result)
        self.assertIn("results", result)


class TestHandleEval(unittest.TestCase):
    """Test eval expression handler."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_eval_simple_expression(self):
        """Test eval simple expression returns expression key."""
        mock_val = Mock()
        mock_val.type.name = "int"
        mock_val.type.code = 1
        mock_val.__str__ = Mock(return_value="42")
        sys.modules['gdb'].parse_and_eval = Mock(return_value=mock_val)

        result = self.handlers.handle_eval("42")
        self.assertIn("expression", result)
        self.assertEqual(result["expression"], "42")

    def test_eval_variable(self):
        """Test eval variable expression."""
        mock_val = Mock()
        mock_val.type.name = "int"
        mock_val.type.code = 1
        mock_val.__str__ = Mock(return_value="7")
        sys.modules['gdb'].parse_and_eval = Mock(return_value=mock_val)

        result = self.handlers.handle_eval("x")
        self.assertIn("expression", result)
        self.assertEqual(result["expression"], "x")


class TestHandleThreads(unittest.TestCase):
    """Test threads listing handler."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_threads_basic(self):
        """Test basic threads listing."""
        t1 = Mock()
        t1.num = 1
        t1.ptid = (1, 1, 0)
        t1.name = "Thread 1"
        t1.is_running.return_value = False
        t1.is_stopped.return_value = True

        mock_inferior = Mock()
        mock_inferior.threads.return_value = [t1]
        sys.modules['gdb'].selected_inferior = Mock(return_value=mock_inferior)

        result = self.handlers.handle_threads()
        self.assertIn("threads", result)
        self.assertGreaterEqual(len(result["threads"]), 1)


class TestHandleExecThreading(unittest.TestCase):
    """handle_exec must not post a nested event (it already runs on the GDB main thread)."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod
        self.gdb = sys.modules['gdb']
        self.gdb.execute = Mock(return_value="ok")

    def test_exec_does_not_post_nested_event(self):
        self.gdb.post_event = Mock()

        result = self.handlers.handle_exec("info registers", safety_level="readonly")

        self.gdb.post_event.assert_not_called()
        self.assertEqual(result["output"], "ok")


class TestDefaultRegisterNames(unittest.TestCase):
    """Default register list must follow the target architecture."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    @staticmethod
    def _frame_with_arch(name):
        frame = Mock()
        frame.architecture.return_value.name.return_value = name
        return frame

    def test_arm_registers(self):
        names = self.handlers._default_register_names(self._frame_with_arch("arm"))
        self.assertIn("r0", names)
        self.assertIn("pc", names)
        self.assertIn("xpsr", names)
        self.assertNotIn("rax", names)

    def test_aarch64_registers(self):
        names = self.handlers._default_register_names(self._frame_with_arch("aarch64"))
        self.assertIn("x0", names)
        self.assertIn("pc", names)
        self.assertNotIn("rax", names)

    def test_x86_registers(self):
        names = self.handlers._default_register_names(
            self._frame_with_arch("i386:x86-64")
        )
        self.assertIn("rax", names)
        self.assertIn("rip", names)


class TestHandleStatus(unittest.TestCase):
    """Test session status handler."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_status_returns_session_meta(self):
        """Test status returns session metadata."""
        session_meta = {"mode": "core", "binary": "./myapp", "core": "./core.1234"}
        result = self.handlers.handle_status(_session_meta=session_meta)
        self.assertIn("mode", result)
        self.assertEqual(result["mode"], "core")

    def test_status_honors_server_state(self):
        result = self.handlers.handle_status(_server_state="busy")
        self.assertEqual(result["state"], "busy")

    def test_status_defaults_to_ready(self):
        result = self.handlers.handle_status()
        self.assertEqual(result["state"], "ready")


# --- Strict API-shape fakes -------------------------------------------------
# MagicMock hid the frame.sal() bug because it fabricates any attribute.  The
# fakes below expose only real GDB API methods.

class _Symtab:
    filename = "foo.c"


class _Sal:
    symtab = _Symtab()
    line = 42


class _StrictFrame:
    """Exposes only the real frame API used by _format_frame()."""

    def __init__(self, sal=None):
        self._sal = sal

    def name(self):
        return "main"

    def pc(self):
        return 0x1000

    def find_sal(self):
        return self._sal

    def block(self):
        return None


class _OldFrame:
    """Old-GDB shape: no find_sal() method at all."""

    def name(self):
        return "main"

    def pc(self):
        return 0x1000

    def block(self):
        return None


class _Reg:
    def __init__(self, name):
        self.name = name


class _Arch:
    def __init__(self, name, regs=None, insns=None):
        self._name = name
        self._regs = regs or []
        self._insns = insns or []

    def name(self):
        return self._name

    def registers(self):
        return iter(self._regs)

    def disassemble(self, start, count=None):
        return self._insns[:count] if count else self._insns


class _ArchFrame:
    def __init__(self, arch):
        self._arch = arch

    def architecture(self):
        return self._arch

    def name(self):
        return "main"

    def pc(self):
        return 0x1000


class _RegisterFrame:
    def __init__(self, arch):
        self._arch = arch

    def architecture(self):
        return self._arch

    def read_register(self, name):
        raise RuntimeError("register unavailable: %s" % name)


class _DisasmFrame:
    def __init__(self, arch):
        self._arch = arch

    def architecture(self):
        return self._arch

    def name(self):
        return "main"

    def pc(self):
        return 0x1000


class TestFindSal(unittest.TestCase):
    """frame.find_sal() must be used; frame.sal() does not exist."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_format_frame_uses_find_sal(self):
        result = self.handlers._format_frame(_StrictFrame(sal=_Sal()))
        self.assertEqual(result["file"], "foo.c")
        self.assertEqual(result["line"], 42)

    def test_format_frame_omits_location_without_find_sal(self):
        result = self.handlers._format_frame(_OldFrame())
        self.assertNotIn("file", result)
        self.assertNotIn("line", result)
        self.assertEqual(result["function"], "main")


class TestThreadRestore(unittest.TestCase):
    """Selection must be restored in a finally block even on errors."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod
        self.gdb = sys.modules["gdb"]
        # A real exception class is needed for `except gdb.error`.
        self.gdb.error = RuntimeError

    def test_locals_restores_selection_on_exception(self):
        orig_thread = Mock()
        orig_frame = Mock()
        target_thread = Mock()
        target_thread.num = 7
        inferior = Mock()
        inferior.threads.return_value = [target_thread]
        self.gdb.selected_thread = Mock(return_value=orig_thread)
        self.gdb.selected_frame = Mock(return_value=orig_frame)
        self.gdb.selected_inferior = Mock(return_value=inferior)

        self.handlers._select_frame_by_number = Mock(
            side_effect=RuntimeError("boom")
        )

        result = self.handlers.handle_locals(thread_id=7)

        self.assertIn("error", result)
        orig_thread.switch.assert_called()
        orig_frame.select.assert_called()


class TestDefaultRegisterArchVariants(unittest.TestCase):
    """ARM arch names are variant strings, not exactly 'arm'."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod

    def test_armv7e_m_uses_arm_list(self):
        names = self.handlers._default_register_names(
            _ArchFrame(_Arch("armv7e-m"))
        )
        self.assertIn("r0", names)
        self.assertIn("xpsr", names)
        self.assertNotIn("rax", names)

    def test_armv8_m_main_uses_arm_list(self):
        names = self.handlers._default_register_names(
            _ArchFrame(_Arch("armv8-m.main"))
        )
        self.assertIn("r0", names)
        self.assertIn("pc", names)
        self.assertNotIn("rax", names)

    def test_unknown_arch_enumerates_registers(self):
        arch = _Arch("riscv:rv32", regs=[_Reg("pc"), _Reg("ra"), _Reg("sp")])
        names = self.handlers._default_register_names(_ArchFrame(arch))
        self.assertEqual(names, ["pc", "ra", "sp"])


class TestRegistersNoReadable(unittest.TestCase):
    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod
        self.gdb = sys.modules["gdb"]
        self.gdb.error = RuntimeError

    def test_all_failed_reads_surface_top_level_error(self):
        arch = _Arch("armv7e-m")
        self.gdb.selected_thread = Mock(return_value=Mock())
        self.gdb.selected_frame = Mock(return_value=Mock())
        self.handlers._select_frame_by_number = Mock(
            return_value=_RegisterFrame(arch)
        )

        result = self.handlers.handle_registers()

        self.assertIn("error", result)
        self.assertIn("no readable registers", result["error"])
        self.assertIn("armv7e-m", result["error"])


class TestDisasm(unittest.TestCase):
    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod
        self.gdb = sys.modules["gdb"]
        self.gdb.error = RuntimeError
        self.gdb.selected_thread = Mock(return_value=Mock())
        self.gdb.selected_frame = Mock(return_value=Mock())

    def _arch(self):
        return _Arch(
            "armv7e-m",
            insns=[
                {"addr": 0x1000, "asm": "nop", "length": 2},
                {"addr": 0x1002, "asm": "nop", "length": 2},
            ],
        )

    def test_hint_uses_addr_plus_length(self):
        self.handlers._select_frame_by_number = Mock(
            return_value=_DisasmFrame(self._arch())
        )
        result = self.handlers.handle_disasm(start="0x1000", count=2)
        self.assertIn("hint", result)
        self.assertIn("0x1004", result["hint"])
        self.assertNotIn("0x1003", result["hint"])

    def test_non_positive_count_rejected(self):
        for bad in (0, -1):
            with self.subTest(count=bad):
                result = self.handlers.handle_disasm(start="0x1000", count=bad)
                self.assertEqual(result["error"], "count must be positive")

    def test_explicit_start_without_frame(self):
        # Simulate: no selected frame, but inferior architecture available.
        self.handlers._select_frame_by_number = Mock(
            side_effect=RuntimeError("No frame is currently selected.")
        )
        self.gdb.selected_frame = Mock(return_value=None)
        self.gdb.selected_inferior = Mock(
            return_value=SimpleNamespace(architecture=lambda: self._arch())
        )

        result = self.handlers.handle_disasm(start="0x1000", count=2)

        self.assertIn("instructions", result)
        self.assertEqual(result["function"], "??")
        self.assertEqual(result["count"], 2)


class TestSafetyFailClosed(unittest.TestCase):
    """Handlers must refuse commands when the safety module is unavailable."""

    def setUp(self):
        import importlib

        import gdb_cli.gdb_server.handlers as handlers_mod
        importlib.reload(handlers_mod)
        self.handlers = handlers_mod
        self.handlers.SAFETY_AVAILABLE = False

    def test_exec_fails_closed(self):
        sys.modules["gdb"].execute = Mock(return_value="ran")
        result = self.handlers.handle_exec("bt")
        self.assertIn("error", result)
        self.assertIn("safety module unavailable", result["error"])
        sys.modules["gdb"].execute.assert_not_called()

    def test_thread_apply_fails_closed(self):
        result = self.handlers.handle_thread_apply(
            command="bt", all_threads=True
        )
        self.assertIn("error", result)
        self.assertIn("safety module unavailable", result["error"])


if __name__ == "__main__":
    unittest.main()
