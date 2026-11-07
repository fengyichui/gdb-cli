"""Tests for value_formatter.py type-code handling."""

import sys
import unittest
from types import SimpleNamespace

# Mock gdb before importing the formatter (it requires the GDB Python API).
sys.modules.setdefault("gdb", SimpleNamespace())

from gdb_cli.gdb_server import value_formatter  # noqa: E402


class _FakeType:
    def __init__(self, code):
        self.code = code

    def strip_typedefs(self):
        return self


class _FakeValue:
    def __init__(self, code, value):
        self.type = _FakeType(code)
        self._value = value

    def __float__(self):
        return self._value


class TestFloatFormatting(unittest.TestCase):
    def test_float_type_uses_type_code_flt(self):
        """gdb.TYPE_CODE_FLT is the real API name (not TYPE_CODE_FLOAT)."""
        stub = SimpleNamespace(
            TYPE_CODE_INT=1,
            TYPE_CODE_BOOL=2,
            TYPE_CODE_FLT=3,
            TYPE_CODE_VOID=4,
            TYPE_CODE_ENUM=5,
            TYPE_CODE_CHAR=6,
            TYPE_CODE_ARRAY=7,
            TYPE_CODE_PTR=8,
            TYPE_CODE_REF=9,
            TYPE_CODE_STRUCT=10,
            TYPE_CODE_UNION=11,
            TYPE_CODE_TYPEDEF=12,
            TYPE_CODE_FUNC=13,
        )

        original_gdb = value_formatter.gdb
        value_formatter.gdb = stub
        try:
            self.assertEqual(
                value_formatter.format_gdb_value(_FakeValue(stub.TYPE_CODE_FLT, 1.5)),
                1.5,
            )
        finally:
            value_formatter.gdb = original_gdb


if __name__ == "__main__":
    unittest.main()
