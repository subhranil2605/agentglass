"""Tests for the EventStore class."""

import asyncio
import threading
import pytest

from agentglass.core.store import EventStore


class TestEventStore:
    """Tests for EventStore basic operations."""

    def test_push_and_all_events(self):
        """Events pushed to the store can be retrieved."""
        store = EventStore()
        event1 = {"node": "agent", "type": "node_start"}
        event2 = {"node": "tools", "type": "node_start"}

        store.push(event1)
        store.push(event2)

        events = store.all_events()
        assert len(events) == 2
        assert events[0] == event1
        assert events[1] == event2

    def test_push_event_without_node(self):
        """Events without a node key are stored chronologically only."""
        store = EventStore()
        event = {"type": "run_start", "run_id": "123"}

        store.push(event)

        assert store.all_events() == [event]
        assert store.events_for_node("any") == []

    def test_events_for_node(self):
        """Events can be filtered by node name."""
        store = EventStore()
        store.push({"node": "agent", "type": "node_start", "id": 1})
        store.push({"node": "tools", "type": "node_start", "id": 2})
        store.push({"node": "agent", "type": "node_end", "id": 3})

        agent_events = store.events_for_node("agent")
        assert len(agent_events) == 2
        assert agent_events[0]["id"] == 1
        assert agent_events[1]["id"] == 3

        tools_events = store.events_for_node("tools")
        assert len(tools_events) == 1
        assert tools_events[0]["id"] == 2

    def test_events_for_node_with_run_id_filter(self):
        """Events can be filtered by node and run_id."""
        store = EventStore()
        store.push({"node": "agent", "run_id": "run1", "id": 1})
        store.push({"node": "agent", "run_id": "run2", "id": 2})
        store.push({"node": "agent", "run_id": "run1", "id": 3})

        run1_events = store.events_for_node("agent", run_id="run1")
        assert len(run1_events) == 2
        assert run1_events[0]["id"] == 1
        assert run1_events[1]["id"] == 3

    def test_events_for_node_with_limit(self):
        """Limit returns the most recent events."""
        store = EventStore()
        for i in range(5):
            store.push({"node": "agent", "id": i})

        limited = store.events_for_node("agent", limit=2)
        assert len(limited) == 2
        assert limited[0]["id"] == 3
        assert limited[1]["id"] == 4

    def test_clear(self):
        """Clear removes all events."""
        store = EventStore()
        store.push({"node": "agent", "type": "node_start"})
        store.push({"node": "tools", "type": "node_start"})

        store.clear()

        assert store.all_events() == []
        assert store.events_for_node("agent") == []

    def test_thread_safety(self):
        """Store handles concurrent pushes safely."""
        store = EventStore()
        num_threads = 10
        events_per_thread = 100

        def push_events(thread_id):
            for i in range(events_per_thread):
                store.push({"node": "agent", "thread": thread_id, "i": i})

        threads = [threading.Thread(target=push_events, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(store.all_events()) == num_threads * events_per_thread


class TestEventStorePubSub:
    """Tests for EventStore pub/sub functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_receives_new_events(self):
        """Subscribers receive events pushed after subscribing."""
        store = EventStore()
        loop = asyncio.get_running_loop()
        queue = store.subscribe(loop)

        event = {"node": "agent", "type": "node_start"}
        store.push(event)

        # Give the event loop a chance to process
        await asyncio.sleep(0.01)

        assert not queue.empty()
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received == event

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Unsubscribed queues no longer receive events."""
        store = EventStore()
        loop = asyncio.get_running_loop()
        queue = store.subscribe(loop)

        store.unsubscribe(queue)
        store.push({"node": "agent", "type": "node_start"})

        await asyncio.sleep(0.01)
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Multiple subscribers each receive the same events."""
        store = EventStore()
        loop = asyncio.get_running_loop()
        q1 = store.subscribe(loop)
        q2 = store.subscribe(loop)

        event = {"node": "agent", "type": "node_start"}
        store.push(event)

        await asyncio.sleep(0.01)

        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1 == event
        assert r2 == event

    def test_unsubscribe_nonexistent_queue(self):
        """Unsubscribing a non-existent queue doesn't raise."""
        store = EventStore()
        fake_queue = asyncio.Queue()
        store.unsubscribe(fake_queue)  # Should not raise
