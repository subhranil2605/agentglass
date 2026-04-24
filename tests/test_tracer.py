"""Tests for the AgentGlass tracer."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from agentglass.core.store import EventStore
from agentglass.core.tracer import (
    AgentGlassTracer,
    _extract_tool_calls,
    _extract_token_usage,
    _extract_model_name,
    _now_iso,
)


class TestNowIso:
    """Tests for timestamp generation."""

    def test_returns_iso_format(self):
        result = _now_iso()
        # Should be ISO format with timezone
        assert "T" in result
        assert result.endswith("+00:00") or result.endswith("Z")


class TestExtractToolCalls:
    """Tests for tool call extraction from LLM responses."""

    def test_empty_response(self):
        """Empty response returns no tool calls."""
        response = MagicMock()
        response.generations = []
        assert _extract_tool_calls(response) == []

    def test_tool_calls_from_message(self):
        """Tool calls are extracted from message.tool_calls."""
        msg = MagicMock()
        msg.tool_calls = [
            {"name": "get_weather", "args": {"city": "Tokyo"}, "id": "call_1"}
        ]
        msg.additional_kwargs = {}

        gen = MagicMock()
        gen.message = msg

        response = MagicMock()
        response.generations = [[gen]]

        calls = _extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_weather"
        assert calls[0]["args"] == {"city": "Tokyo"}

    def test_function_call_from_additional_kwargs(self):
        """Legacy function_call format is also extracted."""
        msg = MagicMock()
        msg.tool_calls = []
        msg.additional_kwargs = {
            "function_call": {"name": "search", "arguments": {"query": "test"}}
        }

        gen = MagicMock()
        gen.message = msg

        response = MagicMock()
        response.generations = [[gen]]

        calls = _extract_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "search"


class TestExtractTokenUsage:
    """Tests for token usage extraction."""

    def test_usage_from_llm_output(self):
        """Token usage from llm_output.token_usage."""
        response = MagicMock()
        response.llm_output = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }
        response.generations = []

        usage = _extract_token_usage(response)
        assert usage["input"] == 100
        assert usage["output"] == 50
        assert usage["total"] == 150

    def test_usage_from_usage_key(self):
        """Token usage from llm_output.usage (alternative key)."""
        response = MagicMock()
        response.llm_output = {
            "usage": {
                "input_tokens": 200,
                "output_tokens": 100,
            }
        }
        response.generations = []

        usage = _extract_token_usage(response)
        assert usage["input"] == 200
        assert usage["output"] == 100
        assert usage["total"] == 300  # Calculated

    def test_usage_from_message_metadata(self):
        """Token usage from message.usage_metadata."""
        response = MagicMock()
        response.llm_output = {}
        response.generations = [[MagicMock()]]

        gen = response.generations[0][0]
        gen.message = MagicMock()
        gen.message.usage_metadata = {
            "input_tokens": 50,
            "output_tokens": 25,
            "total_tokens": 75,
        }

        usage = _extract_token_usage(response)
        assert usage["input"] == 50
        assert usage["output"] == 25
        assert usage["total"] == 75

    def test_no_usage_available(self):
        """Missing usage returns None values."""
        response = MagicMock()
        response.llm_output = {}
        response.generations = []

        usage = _extract_token_usage(response)
        assert usage["input"] is None
        assert usage["output"] is None
        assert usage["total"] is None


class TestExtractModelName:
    """Tests for model name extraction."""

    def test_model_from_response(self):
        """Model name from response.llm_output."""
        response = MagicMock()
        response.llm_output = {"model_name": "gpt-4"}

        name = _extract_model_name({}, response)
        assert name == "gpt-4"

    def test_model_from_serialized(self):
        """Model name from serialized config."""
        serialized = {"model_name": "gemini-pro"}

        name = _extract_model_name(serialized, None)
        assert name == "gemini-pro"

    def test_model_from_kwargs(self):
        """Model name from serialized.kwargs."""
        serialized = {"kwargs": {"model": "claude-3"}}

        name = _extract_model_name(serialized, None)
        assert name == "claude-3"

    def test_no_model_name(self):
        """Missing model name returns None."""
        name = _extract_model_name({}, None)
        assert name is None


class TestAgentGlassTracer:
    """Tests for the tracer callback handler."""

    @pytest.fixture
    def store(self):
        return EventStore()

    @pytest.fixture
    def tracer(self, store):
        return AgentGlassTracer(store, node_ids={"agent", "tools"})

    def test_is_node_run_with_step_tag(self, tracer):
        """Runs with graph:step: tag are node runs."""
        assert tracer._is_node_run("agent", ["graph:step:agent"], {})

    def test_is_node_run_with_langgraph_tag(self, tracer):
        """Runs with langgraph:node: tag are node runs."""
        assert tracer._is_node_run("agent", ["langgraph:node:agent"], {})

    def test_is_node_run_false_without_tag(self, tracer):
        """Runs without step tags are not node runs."""
        assert not tracer._is_node_run("agent", [], {})

    def test_is_node_run_checks_metadata(self, tracer):
        """Node name must match metadata if present."""
        assert tracer._is_node_run(
            "agent", ["graph:step:agent"], {"langgraph_node": "agent"}
        )
        assert not tracer._is_node_run(
            "wrong", ["graph:step:wrong"], {"langgraph_node": "agent"}
        )

    def test_node_name_from_metadata(self, tracer):
        """Node name is extracted from metadata first."""
        name = tracer._node_name("run", [], {"langgraph_node": "agent"}, {})
        assert name == "agent"

    def test_node_name_from_tags(self, tracer):
        """Node name is extracted from tags if no metadata."""
        name = tracer._node_name("run", ["graph:step:tools"], {}, {})
        assert name == "tools"

    def test_on_chain_start_creates_event(self, tracer, store):
        """on_chain_start creates a node_start event for node runs."""
        tracer.on_chain_start(
            serialized={},
            inputs={"messages": []},
            run_id="run-123",
            tags=["graph:step:agent"],
            metadata={"langgraph_node": "agent"},
            name="agent",
        )

        events = store.all_events()
        assert len(events) == 1
        assert events[0]["type"] == "node_start"
        assert events[0]["node"] == "agent"
        assert "execution_id" in events[0]

    def test_on_chain_start_ignores_non_node_runs(self, tracer, store):
        """on_chain_start ignores runs that aren't node executions."""
        tracer.on_chain_start(
            serialized={},
            inputs={},
            run_id="run-456",
            tags=[],
            metadata={},
            name="some_internal_chain",
        )

        assert store.all_events() == []

    def test_on_chain_end_creates_event(self, tracer, store):
        """on_chain_end creates a node_end event."""
        # First start a node
        tracer.on_chain_start(
            serialized={},
            inputs={},
            run_id="run-123",
            tags=["graph:step:agent"],
            metadata={"langgraph_node": "agent"},
            name="agent",
        )

        # Then end it
        tracer.on_chain_end(outputs={"result": "done"}, run_id="run-123")

        events = store.all_events()
        assert len(events) == 2
        assert events[1]["type"] == "node_end"
        assert events[1]["node"] == "agent"
        assert "duration_ms" in events[1]

    def test_on_chain_error_creates_event(self, tracer, store):
        """on_chain_error creates a node_error event."""
        tracer.on_chain_start(
            serialized={},
            inputs={},
            run_id="run-123",
            tags=["graph:step:agent"],
            metadata={"langgraph_node": "agent"},
            name="agent",
        )

        error = ValueError("Something went wrong")
        tracer.on_chain_error(error=error, run_id="run-123")

        events = store.all_events()
        assert len(events) == 2
        assert events[1]["type"] == "node_error"
        assert events[1]["error"]["type"] == "ValueError"
        assert "Something went wrong" in events[1]["error"]["message"]

    def test_llm_info_attached_to_node(self, tracer, store):
        """LLM call info is attached to the parent node's end event."""
        # Start a node
        tracer.on_chain_start(
            serialized={},
            inputs={},
            run_id="node-run",
            tags=["graph:step:agent"],
            metadata={"langgraph_node": "agent"},
            name="agent",
        )

        # LLM call starts
        tracer.on_chat_model_start(
            serialized={"model_name": "gpt-4"},
            messages=[],
            run_id="llm-run",
            parent_run_id="node-run",
        )

        # LLM call ends
        response = MagicMock()
        response.llm_output = {"model_name": "gpt-4", "token_usage": {"total_tokens": 100}}
        response.generations = []

        tracer.on_llm_end(response=response, run_id="llm-run", parent_run_id="node-run")

        # End the node
        tracer.on_chain_end(outputs={}, run_id="node-run")

        events = store.all_events()
        end_event = events[-1]
        assert end_event["type"] == "node_end"
        assert len(end_event["llm_calls"]) == 1
        assert end_event["llm_calls"][0]["model"] == "gpt-4"
