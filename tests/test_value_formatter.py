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


class _FakeMemoryError(Exception):
    pass


def _gdb_stub():
    return SimpleNamespace(
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
        MemoryError=_FakeMemoryError,
    )


class _AdvType:
    """Strict fake gdb.Type exposing only the real API surface."""

    def __init__(self, code, name=None, sizeof=None, target=None):
        self.code = code
        self.name = name
        self.sizeof = sizeof
        self._target = target

    def strip_typedefs(self):
        return self

    def target(self):
        return self._target

    def __str__(self):
        return self.name or "type_%s" % self.code


class _ScalarValue:
    def __init__(self, code, value, sizeof=None, name=None):
        self.type = _AdvType(code, name=name, sizeof=sizeof)
        self._value = value

    def __int__(self):
        return int(self._value)

    def __float__(self):
        return float(self._value)

    def __bool__(self):
        return bool(self._value)


class _PointerValue:
    """Strict fake pointer value tracking deref/string reads."""

    def __init__(self, addr, target_type, string_value=None, deref_value=None):
        self._addr = addr
        self._target = target_type
        self._string_value = string_value
        self._deref_value = deref_value
        self.deref_calls = 0
        self.string_calls = 0

    @property
    def type(self):
        return _AdvType(8, target=self._target)

    def __int__(self):
        return self._addr

    def string(self, encoding="utf-8", errors="replace", length=None):
        self.string_calls += 1
        return self._string_value

    def dereference(self):
        self.deref_calls += 1
        return self._deref_value


class _CharArrayValue:
    """Strict fake char array value."""

    def __init__(self, data, elem_code, elem_name, elem_size=1):
        self._data = data
        self._elem = _AdvType(elem_code, name=elem_name, sizeof=elem_size)
        self.string_calls = 0

    @property
    def type(self):
        return _AdvType(
            7, sizeof=len(self._data) * self._elem.sizeof, target=self._elem
        )

    def string(self, encoding="utf-8", errors="replace", length=None):
        self.string_calls += 1
        return self._data

    def __getitem__(self, index):
        return _ScalarValue(
            self._elem.code, ord(self._data[index]), sizeof=self._elem.sizeof
        )


class _FormatterTestBase(unittest.TestCase):
    def setUp(self):
        self.stub = _gdb_stub()
        self._original_gdb = value_formatter.gdb
        value_formatter.gdb = self.stub

    def tearDown(self):
        value_formatter.gdb = self._original_gdb


class TestNonFiniteFloats(_FormatterTestBase):
    def test_nan_and_inf_are_special(self):
        cases = [
            (float("nan"), {"special": "nan"}),
            (float("inf"), {"special": "inf"}),
            (float("-inf"), {"special": "-inf"}),
        ]
        for raw, expected in cases:
            with self.subTest(value=raw):
                result = value_formatter.format_gdb_value(
                    _ScalarValue(self.stub.TYPE_CODE_FLT, raw)
                )
                self.assertEqual(result, expected)


class TestAutoDeref(_FormatterTestBase):
    def test_auto_deref_false_does_not_dereference(self):
        target = _AdvType(self.stub.TYPE_CODE_STRUCT, name="Foo")
        deref_value = _ScalarValue(self.stub.TYPE_CODE_VOID, None)
        val = _PointerValue(0x1000, target, deref_value=deref_value)

        result = value_formatter.format_gdb_value(val, auto_deref=False)

        self.assertEqual(val.deref_calls, 0)
        self.assertNotIn("deref", result)
        self.assertEqual(result["type"], "pointer")
        self.assertEqual(result["address"], "0x1000")
        self.assertIn("target_type", result)

    def test_auto_deref_true_still_dereferences(self):
        target = _AdvType(self.stub.TYPE_CODE_STRUCT, name="Foo")
        deref_value = _ScalarValue(self.stub.TYPE_CODE_VOID, None)
        val = _PointerValue(0x1000, target, deref_value=deref_value)

        result = value_formatter.format_gdb_value(val, auto_deref=True)

        self.assertEqual(val.deref_calls, 1)
        self.assertIn("deref", result)

    def test_auto_deref_false_skips_char_star_string_read(self):
        target = _AdvType(self.stub.TYPE_CODE_CHAR, name="char", sizeof=1)
        val = _PointerValue(0x2000, target, string_value="secret")

        result = value_formatter.format_gdb_value(val, auto_deref=False)

        self.assertEqual(val.string_calls, 0)
        self.assertNotIn("string", result)

    def test_char_pointer_string_cut_at_nul(self):
        target = _AdvType(self.stub.TYPE_CODE_CHAR, name="char", sizeof=1)
        val = _PointerValue(0x2000, target, string_value="hi\x00zzz")

        result = value_formatter.format_gdb_value(val, auto_deref=True)

        self.assertEqual(result["string"], "hi")

    def test_c_char_int_pointer_formats_as_string(self):
        # Modern GDB reports C `char` with TYPE_CODE_INT, not CHAR.
        target = _AdvType(self.stub.TYPE_CODE_INT, name="char", sizeof=1)
        val = _PointerValue(0x2000, target, string_value="hi\x00zzz")

        result = value_formatter.format_gdb_value(val, auto_deref=True)

        self.assertEqual(result["string"], "hi")


class TestCharArrayCString(_FormatterTestBase):
    def test_c_char_int_array_formats_as_string(self):
        # Modern GDB reports C `char` with TYPE_CODE_INT (code 8), not CHAR.
        val = _CharArrayValue(
            "hi\x00zzz",
            elem_code=self.stub.TYPE_CODE_INT,
            elem_name="char",
            elem_size=1,
        )

        result = value_formatter.format_gdb_value(val)

        self.assertEqual(result, "hi")

    def test_non_char_int8_array_stays_array(self):
        val = _CharArrayValue(
            "\x01\x02",
            elem_code=self.stub.TYPE_CODE_INT,
            elem_name="int8_t",
            elem_size=1,
        )

        result = value_formatter.format_gdb_value(val)

        self.assertEqual(result["type"], "array")


if __name__ == "__main__":
    unittest.main()
