"""Tests for graph structure extraction."""

import pytest

from agentglass.graph.graph_extract import (
    extract_structure,
    _classify_node,
    _extract_nodes,
    _extract_edges,
    _find_entry,
    START_IDS,
    END_IDS,
)


class MockNode:
    """Mock node object for testing."""

    def __init__(self, id: str, name: str | None = None):
        self.id = id
        self.name = name or id


class MockEdge:
    """Mock edge object for testing."""

    def __init__(self, source: str, target: str, conditional: bool = False, data=None):
        self.source = source
        self.target = target
        self.conditional = conditional
        self.data = data


class MockGraph:
    """Mock compiled graph for testing."""

    def __init__(self, nodes: dict | list = None, edges: list = None):
        self._nodes = nodes or {}
        self._edges = edges or []

    @property
    def nodes(self):
        return self._nodes

    @property
    def edges(self):
        return self._edges


class MockCompiledGraph:
    """Mock compiled LangGraph object."""

    def __init__(self, graph: MockGraph):
        self._graph = graph

    def get_graph(self):
        return self._graph


class TestClassifyNode:
    """Tests for node classification."""

    def test_start_nodes(self):
        for start_id in START_IDS:
            assert _classify_node(start_id) == "start"

    def test_end_nodes(self):
        for end_id in END_IDS:
            assert _classify_node(end_id) == "end"

    def test_regular_nodes(self):
        assert _classify_node("agent") == "node"
        assert _classify_node("tools") == "node"
        assert _classify_node("my_custom_node") == "node"


class TestExtractNodes:
    """Tests for node extraction."""

    def test_dict_nodes(self):
        """Nodes from a dict are extracted correctly."""
        graph = MockGraph(
            nodes={
                "__start__": MockNode("__start__"),
                "agent": MockNode("agent", "Agent Node"),
                "__end__": MockNode("__end__"),
            }
        )

        nodes = _extract_nodes(graph)
        assert len(nodes) == 3

        node_ids = {n["id"] for n in nodes}
        assert node_ids == {"__start__", "agent", "__end__"}

        agent = next(n for n in nodes if n["id"] == "agent")
        assert agent["name"] == "Agent Node"
        assert agent["type"] == "node"

    def test_list_nodes(self):
        """Nodes from a list are extracted correctly."""
        graph = MockGraph(nodes=[MockNode("node1"), MockNode("node2")])

        nodes = _extract_nodes(graph)
        assert len(nodes) == 2

    def test_none_nodes(self):
        """Missing nodes attribute returns empty list."""
        graph = MockGraph()
        graph._nodes = None
        nodes = _extract_nodes(graph)
        assert nodes == []

    def test_node_without_name_uses_id(self):
        """Nodes without a name attribute use their id."""
        node = MockNode("agent")
        node.name = None
        graph = MockGraph(nodes={"agent": node})

        nodes = _extract_nodes(graph)
        assert nodes[0]["name"] == "agent"


class TestExtractEdges:
    """Tests for edge extraction."""

    def test_basic_edges(self):
        """Edges are extracted correctly."""
        graph = MockGraph(
            edges=[
                MockEdge("__start__", "agent"),
                MockEdge("agent", "tools"),
                MockEdge("tools", "__end__"),
            ]
        )

        edges = _extract_edges(graph)
        assert len(edges) == 3

        assert edges[0]["source"] == "__start__"
        assert edges[0]["target"] == "agent"

    def test_conditional_edges(self):
        """Conditional edges are marked correctly."""
        graph = MockGraph(
            edges=[
                MockEdge("agent", "tools", conditional=True),
                MockEdge("agent", "__end__", conditional=True),
            ]
        )

        edges = _extract_edges(graph)
        assert all(e["conditional"] for e in edges)

    def test_edge_with_label(self):
        """Edge labels are preserved."""
        graph = MockGraph(edges=[MockEdge("a", "b", data="my_label")])

        edges = _extract_edges(graph)
        assert edges[0]["label"] == "my_label"

    def test_none_edges(self):
        """Missing edges attribute returns empty list."""
        graph = MockGraph()
        graph._edges = None
        edges = _extract_edges(graph)
        assert edges == []

    def test_edge_missing_source_or_target(self):
        """Edges without source or target are skipped."""

        class PartialEdge:
            source = "a"
            target = None

        graph = MockGraph(edges=[PartialEdge()])
        edges = _extract_edges(graph)
        assert edges == []


class TestFindEntry:
    """Tests for finding the entry point."""

    def test_finds_start_node(self):
        """Entry point is the node with type 'start'."""
        nodes = [
            {"id": "__start__", "type": "start"},
            {"id": "agent", "type": "node"},
        ]
        edges = []

        entry = _find_entry(nodes, edges)
        assert entry == "__start__"

    def test_fallback_to_edge_source(self):
        """Falls back to source of first edge from START-like node."""
        nodes = [{"id": "agent", "type": "node"}]
        edges = [{"source": "__start__", "target": "agent"}]

        entry = _find_entry(nodes, edges)
        assert entry == "__start__"

    def test_fallback_to_first_node(self):
        """Falls back to first node if no start found."""
        nodes = [{"id": "agent", "type": "node"}]
        edges = []

        entry = _find_entry(nodes, edges)
        assert entry == "agent"

    def test_empty_graph(self):
        """Empty graph returns None."""
        entry = _find_entry([], [])
        assert entry is None


class TestExtractStructure:
    """Integration tests for full structure extraction."""

    def test_basic_graph(self):
        """Full graph structure is extracted correctly."""
        graph = MockGraph(
            nodes={
                "__start__": MockNode("__start__"),
                "agent": MockNode("agent"),
                "__end__": MockNode("__end__"),
            },
            edges=[
                MockEdge("__start__", "agent"),
                MockEdge("agent", "__end__"),
            ],
        )
        compiled = MockCompiledGraph(graph)

        structure = extract_structure(compiled)

        assert len(structure["nodes"]) == 3
        assert len(structure["edges"]) == 2
        assert structure["entry_point"] == "__start__"
        assert "error" not in structure

    def test_graph_extraction_failure(self):
        """Errors during extraction are captured."""

        class BrokenGraph:
            def get_graph(self):
                raise RuntimeError("Graph not available")

        structure = extract_structure(BrokenGraph())

        assert structure["nodes"] == []
        assert structure["edges"] == []
        assert structure["entry_point"] is None
        assert "error" in structure
        assert "Graph not available" in structure["error"]
