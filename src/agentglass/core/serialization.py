"""
Safe serialization of arbitrary agent state for transmission to the UI.

Agent state can contain Pydantic models, LangChain Message objects, dataclasses,
bytes, PIL images, numpy arrays, and more. Naive json.dumps will crash on all of
these. This module provides a defensive serializer that:

  1. Recognizes common rich-object types and converts them to plain dicts.
  2. Falls back to repr() for truly unknown objects, wrapped so the UI can render
     them as "non-JSON" values.
  3. Caps any single value at ~50KB, keeping the head and tail so truncation is
     obvious but the value is still inspectable.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from typing import Any

# Per-field size cap. Values longer than this (after serialization) are
# truncated. The UI can request the full value on demand.
MAX_FIELD_BYTES = 50_000
HEAD_BYTES = 40_000
TAIL_BYTES = 10_000


def _to_plain(value: Any, _depth: int = 0) -> Any:
    """Recursively convert ``value`` into something json.dumps can handle."""
    # Prevent runaway recursion on cyclic structures.
    if _depth > 12:
        return {"__truncated__": "max depth exceeded", "repr": _safe_repr(value)}

    # Primitives pass through.
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    # Bytes — show a short preview, not raw bytes the JSON can't hold.
    if isinstance(value, (bytes, bytearray)):
        return {
            "__type__": "bytes",
            "length": len(value),
            "preview": value[:64].hex(),
        }

    # datetime objects.
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()

    # Pydantic v2.
    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return _to_plain(value.model_dump(), _depth + 1)
        except Exception:
            pass

    # Pydantic v1 / LangChain messages (which expose .dict()).
    if hasattr(value, "dict") and callable(value.dict) and not isinstance(value, dict):
        try:
            return _to_plain(value.dict(), _depth + 1)
        except Exception:
            pass

    # Dataclasses.
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        try:
            return _to_plain(dataclasses.asdict(value), _depth + 1)
        except Exception:
            pass

    # Dict / mapping.
    if isinstance(value, dict):
        return {str(k): _to_plain(v, _depth + 1) for k, v in value.items()}

    # List / tuple / set.
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_plain(v, _depth + 1) for v in value]

    # Numpy arrays / torch tensors — summarize instead of dumping.
    if _looks_like_ndarray(value):
        return {
            "__type__": type(value).__name__,
            "shape": getattr(value, "shape", None) and list(value.shape),
            "dtype": str(getattr(value, "dtype", "")),
        }

    # Fallback: repr, clearly marked as non-JSON.
    return {"__repr__": _safe_repr(value), "__class__": type(value).__name__}


def _looks_like_ndarray(value: Any) -> bool:
    return (
        hasattr(value, "shape")
        and hasattr(value, "dtype")
        and not isinstance(value, (dict, list, tuple, str, bytes))
    )


def _safe_repr(value: Any) -> str:
    try:
        r = repr(value)
    except Exception as exc:
        r = f"<unreprable: {type(value).__name__}: {exc}>"
    if len(r) > 2000:
        r = r[:2000] + "…"
    return r


def serialize(value: Any) -> Any:
    """Public entrypoint: convert arbitrary Python state into JSON-safe data.

    Also applies a size cap to the top-level structure's string representation —
    individual string leaves that are enormous get truncated with head+tail
    preserved so the shape of the value is still clear.
    """
    plain = _to_plain(value)
    return _cap_strings(plain)


def _cap_strings(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_FIELD_BYTES:
        head = value[:HEAD_BYTES]
        tail = value[-TAIL_BYTES:]
        return (
            head
            + f"\n\n… [truncated {len(value) - HEAD_BYTES - TAIL_BYTES} chars] …\n\n"
            + tail
        )
    if isinstance(value, dict):
        return {k: _cap_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_cap_strings(v) for v in value]
    return value
