"""
Extract the static graph structure (nodes, edges, entry point) from a compiled
LangGraph, to be rendered by the UI.

LangGraph's compiled object exposes ``get_graph()``. The returned object has
evolved slightly across versions, so this module handles the common shapes
defensively rather than binding to one exact API.
"""

from __future__ import annotations

from typing import Any

START_IDS = {"__start__", "START", "start"}
END_IDS = {"__end__", "END", "end"}


def extract_structure(compiled_graph: Any) -> dict[str, Any]:
    """Return a JSON-serializable description of the graph."""
    try:
        g = compiled_graph.get_graph()
    except Exception as exc:
        return {
            "nodes": [],
            "edges": [],
            "entry_point": None,
            "error": f"Could not extract graph structure: {exc}",
        }

    nodes = _extract_nodes(g)
    edges = _extract_edges(g)
    entry = _find_entry(nodes, edges)

    return {
        "nodes": nodes,
        "edges": edges,
        "entry_point": entry,
    }


def _extract_nodes(g: Any) -> list[dict[str, Any]]:
    raw_nodes = getattr(g, "nodes", None)
    if raw_nodes is None:
        return []

    # `.nodes` is typically a dict {id: Node}. We also support list-of-Node.
    if isinstance(raw_nodes, dict):
        items = raw_nodes.items()
    else:
        items = [(getattr(n, "id", str(i)), n) for i, n in enumerate(raw_nodes)]

    out = []
    for node_id, node in items:
        nid = str(node_id)
        name = getattr(node, "name", None) or nid
        out.append(
            {
                "id": nid,
                "name": str(name),
                "type": _classify_node(nid),
            }
        )
    return out


def _extract_edges(g: Any) -> list[dict[str, Any]]:
    raw_edges = getattr(g, "edges", None)
    if raw_edges is None:
        return []

    out = []
    for e in raw_edges:
        source = getattr(e, "source", None)
        target = getattr(e, "target", None)
        if source is None or target is None:
            continue
        out.append(
            {
                "source": str(source),
                "target": str(target),
                "conditional": bool(getattr(e, "conditional", False)),
                "label": getattr(e, "data", None),
            }
        )
    return out


def _classify_node(node_id: str) -> str:
    if node_id in START_IDS:
        return "start"
    if node_id in END_IDS:
        return "end"
    return "node"


def _find_entry(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str | None:
    for n in nodes:
        if n["type"] == "start":
            return n["id"]
    # Fallback: the source of the first edge from a start-looking node.
    for e in edges:
        if e["source"] in START_IDS:
            return e["source"]
    return nodes[0]["id"] if nodes else None
