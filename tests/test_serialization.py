"""Tests for the serialization module."""

import dataclasses
import datetime
import json
import pytest

from agentglass.core.serialization import serialize, MAX_FIELD_BYTES


class TestSerializePrimitives:
    """Tests for primitive type serialization."""

    def test_none(self):
        assert serialize(None) is None

    def test_bool(self):
        assert serialize(True) is True
        assert serialize(False) is False

    def test_int(self):
        assert serialize(42) == 42

    def test_float(self):
        assert serialize(3.14) == 3.14

    def test_string(self):
        assert serialize("hello") == "hello"


class TestSerializeCollections:
    """Tests for collection type serialization."""

    def test_list(self):
        result = serialize([1, 2, 3])
        assert result == [1, 2, 3]

    def test_nested_list(self):
        result = serialize([[1, 2], [3, 4]])
        assert result == [[1, 2], [3, 4]]

    def test_tuple(self):
        result = serialize((1, 2, 3))
        assert result == [1, 2, 3]

    def test_set(self):
        result = serialize({1, 2, 3})
        assert sorted(result) == [1, 2, 3]

    def test_dict(self):
        result = serialize({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_nested_dict(self):
        result = serialize({"outer": {"inner": "value"}})
        assert result == {"outer": {"inner": "value"}}

    def test_dict_with_non_string_keys(self):
        """Non-string dict keys are converted to strings."""
        result = serialize({1: "one", 2: "two"})
        assert result == {"1": "one", "2": "two"}


class TestSerializeBytes:
    """Tests for bytes serialization."""

    def test_bytes(self):
        data = b"hello world"
        result = serialize(data)
        assert result["__type__"] == "bytes"
        assert result["length"] == len(data)
        assert "preview" in result

    def test_bytearray(self):
        data = bytearray(b"hello")
        result = serialize(data)
        assert result["__type__"] == "bytes"
        assert result["length"] == 5

    def test_bytes_preview_is_hex(self):
        data = b"\x00\x01\x02\xff"
        result = serialize(data)
        assert result["preview"] == "000102ff"


class TestSerializeDatetime:
    """Tests for datetime serialization."""

    def test_datetime(self):
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0)
        result = serialize(dt)
        assert result == "2024-01-15T10:30:00"

    def test_date(self):
        d = datetime.date(2024, 1, 15)
        result = serialize(d)
        assert result == "2024-01-15"

    def test_time(self):
        t = datetime.time(10, 30, 0)
        result = serialize(t)
        assert result == "10:30:00"


class TestSerializeDataclass:
    """Tests for dataclass serialization."""

    def test_simple_dataclass(self):
        @dataclasses.dataclass
        class Point:
            x: int
            y: int

        result = serialize(Point(10, 20))
        assert result == {"x": 10, "y": 20}

    def test_nested_dataclass(self):
        @dataclasses.dataclass
        class Inner:
            value: str

        @dataclasses.dataclass
        class Outer:
            inner: Inner

        result = serialize(Outer(Inner("test")))
        assert result == {"inner": {"value": "test"}}


class TestSerializePydantic:
    """Tests for Pydantic model serialization."""

    def test_pydantic_v2_model(self):
        """Test serialization of object with model_dump method."""

        class FakeModel:
            def model_dump(self):
                return {"field": "value"}

        result = serialize(FakeModel())
        assert result == {"field": "value"}

    def test_pydantic_v1_model(self):
        """Test serialization of object with dict method."""

        class FakeModel:
            def dict(self):
                return {"field": "value"}

        result = serialize(FakeModel())
        assert result == {"field": "value"}


class TestSerializeNdarray:
    """Tests for array-like object serialization."""

    def test_ndarray_like(self):
        """Objects with shape and dtype are summarized."""

        class FakeArray:
            shape = (10, 20)
            dtype = "float32"

        result = serialize(FakeArray())
        assert result["__type__"] == "FakeArray"
        assert result["shape"] == [10, 20]
        assert result["dtype"] == "float32"


class TestSerializeFallback:
    """Tests for fallback serialization of unknown objects."""

    def test_unknown_object(self):
        """Unknown objects are serialized as repr."""

        class Custom:
            def __repr__(self):
                return "Custom()"

        result = serialize(Custom())
        assert "__repr__" in result
        assert result["__repr__"] == "Custom()"
        assert result["__class__"] == "Custom"

    def test_unreprable_object(self):
        """Objects that fail repr are handled gracefully."""

        class Broken:
            def __repr__(self):
                raise ValueError("broken")

        result = serialize(Broken())
        assert "__repr__" in result
        assert "unreprable" in result["__repr__"]


class TestSerializeDepthLimit:
    """Tests for recursion depth limiting."""

    def test_deep_nesting_truncates(self):
        """Deeply nested structures are truncated."""
        deep = {"level": 0}
        current = deep
        for i in range(20):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = serialize(deep)
        # Should not raise, should truncate somewhere
        json.dumps(result)  # Must be JSON-serializable


class TestSerializeStringCapping:
    """Tests for large string truncation."""

    def test_large_string_is_truncated(self):
        """Strings larger than MAX_FIELD_BYTES are truncated."""
        large_string = "x" * (MAX_FIELD_BYTES + 10000)
        result = serialize(large_string)

        assert len(result) < len(large_string)
        assert "truncated" in result

    def test_small_string_not_truncated(self):
        """Strings smaller than limit are unchanged."""
        small_string = "hello world"
        result = serialize(small_string)
        assert result == small_string

    def test_nested_large_strings_truncated(self):
        """Large strings inside dicts/lists are also truncated."""
        large = "x" * (MAX_FIELD_BYTES + 1000)
        data = {"key": large, "list": [large]}
        result = serialize(data)

        assert "truncated" in result["key"]
        assert "truncated" in result["list"][0]


class TestSerializeJsonSafe:
    """Tests that serialized output is always JSON-safe."""

    @pytest.mark.parametrize(
        "value",
        [
            None,
            True,
            42,
            3.14,
            "string",
            [1, 2, 3],
            {"a": 1},
            b"bytes",
            datetime.datetime.now(),
            {"nested": {"deep": {"value": [1, 2, 3]}}},
        ],
    )
    def test_json_serializable(self, value):
        """All serialized values should be JSON-serializable."""
        result = serialize(value)
        json.dumps(result)  # Should not raise
