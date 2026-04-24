# Contributing to AgentGlass

Welcome to the AgentGlass project. We're building a transparent debugging experience for AI agents — and like glass itself, we value **clarity**, **precision**, and **craftsmanship**.

Whether you're fixing a bug, proposing a feature, or improving documentation, your contribution helps make agent debugging clearer for everyone.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Issues](#reporting-issues)
- [Proposing Features](#proposing-features)
- [Release Process](#release-process)

---

## Code of Conduct

We maintain a welcoming environment for all contributors. By participating, you agree to:

- Be respectful and inclusive in all interactions
- Provide constructive feedback focused on the work, not the person
- Accept constructive criticism gracefully
- Focus on what's best for the community and project

---

## Getting Started

### Prerequisites

- **Python 3.12+** — AgentGlass uses modern Python features
- **[uv](https://docs.astral.sh/uv/)** — Fast Python package manager (recommended)
- **Git** — For version control

### Quick Start

```bash
# Clone the repository
git clone https://github.com/subhranil2605/agentglass.git
cd agentglass

# Install dependencies (including dev tools)
uv sync

# Verify installation
uv run pytest tests/ -v

# Run the mock agent to test the UI
uv run examples/mock_agent.py
```

---

## Development Setup

### Project Structure

```
agentglass/
├── src/agentglass/
│   ├── __init__.py          # Public API exports
│   ├── api/
│   │   ├── server.py        # FastAPI server + WebSocket
│   │   └── static/
│   │       └── index.html   # Single-file UI
│   ├── core/
│   │   ├── tracer.py        # LangChain callback handler
│   │   ├── store.py         # Thread-safe event buffer
│   │   └── serialization.py # Safe JSON serialization
│   └── graph/
│       └── graph_extract.py # Graph structure extraction
├── tests/                   # Pytest test suite
├── examples/                # Example agents
└── pyproject.toml           # Project configuration
```

### Development Dependencies

The project uses these development tools:

| Tool | Purpose |
|------|---------|
| `pytest` | Testing framework |
| `pytest-asyncio` | Async test support |
| `ruff` | Linting and formatting |
| `mypy` | Static type checking |

### Editor Setup

**VS Code** (recommended):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  }
}
```

---

## Architecture Overview

AgentGlass follows a **clear separation of concerns** — each component has a single responsibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Agent Code                          │
│                    compiled.invoke(state)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AgentGlassTracer                             │
│              (core/tracer.py)                                   │
│                                                                 │
│  • Hooks into LangChain callbacks                               │
│  • Captures node I/O, LLM calls, tool executions                │
│  • Extracts token counts, model names                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EventStore                                 │
│              (core/store.py)                                    │
│                                                                 │
│  • Thread-safe event buffer                                     │
│  • Pub/sub for real-time streaming                              │
│  • Indexed by node for fast lookup                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AgentGlassServer                              │
│              (api/server.py)                                    │
│                                                                 │
│  • FastAPI REST endpoints                                       │
│  • WebSocket for live updates                                   │
│  • Serves static UI                                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Browser UI                                  │
│              (api/static/index.html)                            │
│                                                                 │
│  • Single-file vanilla JS application                           │
│  • Graph visualization with D3.js                               │
│  • Step-through debugger controls                               │
└─────────────────────────────────────────────────────────────────┘
```

### Component Guidelines

| Component | File | When to Modify |
|-----------|------|----------------|
| **Tracer** | `core/tracer.py` | Callback bugs, new event types, token extraction |
| **Store** | `core/store.py` | Event schema changes, persistence, indexing |
| **Serialization** | `core/serialization.py` | New object types, size limits |
| **Server** | `api/server.py` | API endpoints, WebSocket handling |
| **Graph Extract** | `graph/graph_extract.py` | LangGraph API changes, subgraph support |
| **UI** | `api/static/index.html` | Visual changes, new inspector features |

---

## Making Changes

### Branch Naming

Use descriptive branch names:

```
fix/tool-calls-not-showing
feat/state-diff-view
docs/update-quickstart
refactor/extract-llm-helpers
```

### Commit Messages

Write clear, concise commit messages:

```
feat: add token cost badges to node inspector

- Display input/output token counts
- Calculate estimated cost based on model
- Add tooltip with detailed breakdown

Closes #42
```

**Format:**
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation only
- `refactor:` — Code change that neither fixes a bug nor adds a feature
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks

### What Makes a Good Change

**Do:**
- Keep changes focused — one logical change per PR
- Update tests when changing behavior
- Maintain backward compatibility when possible
- Add comments for non-obvious logic

**Avoid:**
- Mixing unrelated changes in one PR
- Breaking the event schema without migration
- Adding dependencies without discussion
- Over-engineering for hypothetical use cases

---

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_store.py -v

# Run tests matching a pattern
uv run pytest tests/ -k "test_serialize" -v

# Run with coverage
uv run pytest tests/ --cov=agentglass --cov-report=term-missing
```

### Test Structure

Tests are organized by module:

```
tests/
├── test_store.py          # EventStore tests
├── test_serialization.py  # Serialization tests
├── test_graph_extract.py  # Graph extraction tests
└── test_tracer.py         # Tracer callback tests
```

### Writing Tests

Follow these conventions:

```python
"""Tests for the EventStore class."""

import pytest
from agentglass.core.store import EventStore


class TestEventStore:
    """Group related tests in a class."""

    def test_push_and_retrieve(self):
        """Use descriptive test names that explain the behavior."""
        store = EventStore()
        event = {"node": "agent", "type": "node_start"}

        store.push(event)

        assert store.all_events() == [event]

    @pytest.mark.asyncio
    async def test_async_subscription(self):
        """Mark async tests with pytest.mark.asyncio."""
        # ...
```

### Test Requirements

- All new features must include tests
- Bug fixes should include a test that would have caught the bug
- Aim for meaningful coverage, not 100% line coverage
- Tests should be deterministic — no flaky tests

---

## Code Style

### Formatting

We use **Ruff** for linting and formatting:

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Type Hints

Use type hints for function signatures:

```python
def events_for_node(
    self,
    node: str,
    run_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return events for a specific node."""
    ...
```

### Type Checking

```bash
uv run mypy src/agentglass/
```

### Documentation

- Add docstrings to public functions and classes
- Use imperative mood: "Return events" not "Returns events"
- Include examples for complex functionality

```python
def serialize(value: Any) -> Any:
    """Convert arbitrary Python state into JSON-safe data.

    Handles Pydantic models, dataclasses, numpy arrays, and more.
    Falls back to repr() for unknown types.

    Example:
        >>> serialize({"messages": [HumanMessage(content="hi")]})
        {"messages": [{"content": "hi", "type": "human"}]}
    """
```

---

## Submitting a Pull Request

### Before Submitting

1. **Sync with main:**
   ```bash
   git fetch origin
   git rebase origin/master
   ```

2. **Run the full test suite:**
   ```bash
   uv run pytest tests/ -v
   ```

3. **Check linting:**
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```

4. **Test manually:**
   ```bash
   uv run examples/mock_agent.py
   ```

### PR Description Template

```markdown
## Summary

Brief description of changes (1-3 sentences).

## Changes

- Bullet point list of specific changes
- Include file names when helpful

## Testing

- How you tested the changes
- Any edge cases considered

## Screenshots

(If UI changes, include before/after screenshots)

## Related Issues

Closes #123
```

### Review Process

1. **Automated checks** — CI runs tests, linting, and type checking
2. **Code review** — A maintainer will review your changes
3. **Feedback** — Address any requested changes
4. **Merge** — Once approved, your PR will be merged

### After Merging

- Delete your branch
- Celebrate your contribution

---

## Reporting Issues

### Bug Reports

A good bug report includes:

1. **Environment:**
   ```
   AgentGlass version: (uv pip show agentglass)
   Python version: (python --version)
   LangGraph version: (uv pip show langgraph)
   OS: macOS/Linux/Windows
   ```

2. **Minimal reproduction** — A self-contained script, ideally using the mock agent

3. **Expected vs actual behavior** — What should happen vs what happens

4. **Screenshots/logs** — Browser console errors, terminal output

### Example Bug Report

```markdown
## Bug: Tool calls not showing in inspector

### Environment
- AgentGlass 0.1.1
- Python 3.12.1
- LangGraph 0.2.0
- macOS 14.0

### Reproduction
```python
# Minimal script that reproduces the issue
from agentglass import trace
# ...
```

### Expected
Tool calls should appear in the inspector panel when clicking an agent node.

### Actual
Inspector shows empty tool_calls array even when tools were called.

### Screenshots
[Screenshot of inspector panel]
```

---

## Proposing Features

### Before Proposing

1. **Search existing issues** — Your idea may already be discussed
2. **Consider scope** — Does it fit AgentGlass's mission?
3. **Think through implementation** — Which components would change?

### Feature Proposal Template

```markdown
## Feature: State diff view

### Problem
When debugging, it's hard to see what changed between consecutive
visits to the same node.

### Proposed Solution
Add a "diff" tab in the inspector that highlights changed keys
between the current and previous execution of the same node.

### Components Affected
- `api/static/index.html` — New diff tab UI
- `core/store.py` — May need to track previous states

### Alternatives Considered
- Side-by-side view (more screen space needed)
- Console diff output (less visual)

### Additional Context
Similar to how Redux DevTools shows state diffs.
```

---

## Release Process

Releases are managed by maintainers. The process:

1. **Version bump** — Update version in `pyproject.toml`
2. **Changelog** — Document changes since last release
3. **Tag** — Create a git tag (`v0.1.1`)
4. **Publish** — Push to PyPI

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0) — Breaking changes to the public API
- **MINOR** (0.2.0) — New features, backward compatible
- **PATCH** (0.1.1) — Bug fixes, backward compatible

---

## Recognition

Contributors are recognized in:

- GitHub's contributor graph
- Release notes for significant contributions
- The project README for major features

---

## Questions?

- **GitHub Issues** — For bugs and feature discussions
- **GitHub Discussions** — For questions and ideas

---

*Thank you for contributing to AgentGlass. Together, we're making AI agent debugging transparent.*
