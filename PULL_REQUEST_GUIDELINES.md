# Pull Request Guidelines

> *"Like crafting fine glass, a great pull request requires clarity, precision, and careful handling."*

---

## The Glass Standard

Every pull request to AgentGlass should embody the qualities of glass itself:

| Quality | In Code |
|---------|---------|
| **Transparent** | Clear intent, obvious changes, no hidden complexity |
| **Polished** | Clean code, passing tests, proper formatting |
| **Focused** | Single purpose, minimal scope, no unrelated changes |
| **Resilient** | Well-tested, handles edge cases, doesn't break existing behavior |

---

## Before You Begin

### 1. Check the Foundation

Ensure your local environment is set up correctly:

```bash
# Sync with the latest main branch
git fetch origin
git checkout master
git pull origin master

# Create a fresh branch
git checkout -b your-branch-name
```

### 2. Understand the Scope

Ask yourself:

- [ ] Does this solve **one** problem clearly?
- [ ] Have I read the related issue (if any)?
- [ ] Do I understand which component(s) this affects?

---

## Crafting Your Changes

### The Single Pane Principle

Each PR should be like a single pane of glass — **one clear view, one purpose**.

**Good:**
```
fix: resolve tool calls not displaying in inspector
```

**Avoid:**
```
fix: resolve tool calls + refactor store + update docs + add new feature
```

If you find yourself wanting to add "and also...", that's a sign to split into multiple PRs.

### Branch Naming

Use clear, descriptive branch names:

```
feat/state-diff-view          # New feature
fix/websocket-reconnection    # Bug fix
docs/api-examples             # Documentation
refactor/extract-llm-helpers  # Code improvement
test/serialization-edge-cases # Test additions
```

### Commit Messages

Write commits that tell a story. Each commit should be a complete, logical unit.

**Format:**
```
<type>: <short description>

<longer explanation if needed>

<references>
```

**Types:**
- `feat` — New feature
- `fix` — Bug fix
- `docs` — Documentation
- `refactor` — Code restructuring
- `test` — Test additions/changes
- `chore` — Build, CI, dependencies

**Example:**
```
feat: add token cost estimation to inspector

Calculate and display estimated API costs based on model
and token counts. Supports OpenAI, Anthropic, and Google
pricing.

- Add cost calculation utility
- Display cost badge on LLM call rows
- Include tooltip with pricing breakdown

Closes #47
```

---

## The Polish Phase

Before submitting, ensure your code is crystal clear:

### 1. Run the Test Suite

```bash
# All tests must pass
uv run pytest tests/ -v

# Check coverage for your changes
uv run pytest tests/ --cov=agentglass --cov-report=term-missing
```

### 2. Lint and Format

```bash
# Check for issues
uv run ruff check .

# Auto-fix what can be fixed
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### 3. Type Check

```bash
uv run mypy src/agentglass/
```

### 4. Manual Testing

```bash
# Always test with the mock agent
uv run examples/mock_agent.py

# If your changes affect real agent tracing, test that too
```

### 5. Self-Review Checklist

Before clicking "Create Pull Request":

- [ ] I've read through my own diff
- [ ] Variable and function names are clear
- [ ] No commented-out code or debug statements
- [ ] No unnecessary whitespace changes
- [ ] Tests cover the new/changed behavior
- [ ] Documentation updated if needed

---

## The Pull Request

### Title

Write a clear, descriptive title:

```
feat: add state diff view to inspector panel
fix: prevent WebSocket disconnection on large payloads
docs: add troubleshooting section for common errors
```

### Description Template

Use this template to ensure clarity:

```markdown
## Summary

A brief, clear description of what this PR does (1-3 sentences).

## Motivation

Why is this change needed? Link to issue if applicable.

Closes #123

## Changes

- Specific change 1
- Specific change 2
- Specific change 3

## Component Impact

Which parts of AgentGlass does this affect?

- [ ] `core/tracer.py` — Callback handling
- [ ] `core/store.py` — Event storage
- [ ] `core/serialization.py` — Data serialization
- [ ] `api/server.py` — API endpoints
- [ ] `graph/graph_extract.py` — Graph structure
- [ ] `api/static/index.html` — UI

## Testing

How did you verify this works?

- [ ] Added/updated unit tests
- [ ] Tested with mock agent
- [ ] Tested with real LangGraph agent
- [ ] Manual UI testing

## Screenshots

(Required for UI changes)

**Before:**
[screenshot]

**After:**
[screenshot]

## Notes for Reviewers

Any specific areas you'd like feedback on, or context that helps review.
```

---

## During Review

### Responding to Feedback

- **Be receptive** — Feedback improves the code
- **Ask questions** — If feedback is unclear, seek clarification
- **Explain your reasoning** — If you disagree, discuss constructively
- **Update promptly** — Address feedback in a timely manner

### Making Changes

When updating your PR based on feedback:

```bash
# Make your changes
git add .
git commit -m "address review feedback: clarify variable names"

# Push to update the PR
git push origin your-branch-name
```

For small fixes, you can amend:
```bash
git add .
git commit --amend --no-edit
git push --force-with-lease origin your-branch-name
```

### Review Etiquette

- Respond to all comments, even if just with a checkmark
- Mark conversations as resolved when addressed
- Re-request review when ready for another look

---

## Special Cases

### Breaking Changes

If your PR introduces breaking changes:

1. **Document clearly** in the PR description
2. **Explain migration path** for users
3. **Consider backwards compatibility** — can it be avoided?
4. **Update version** appropriately (major version bump)

### Large PRs

If your PR is necessarily large:

1. **Add a detailed description** explaining the structure
2. **Consider splitting** into stacked PRs if possible
3. **Offer to walk through** the changes with a reviewer
4. **Add inline comments** on complex sections

### UI Changes

For changes to `api/static/index.html`:

1. **Include screenshots** — before and after
2. **Test across browsers** — Chrome, Firefox, Safari
3. **Check responsiveness** — different window sizes
4. **Verify accessibility** — keyboard navigation, screen readers

### Event Schema Changes

For changes to the event format in `core/store.py` or `core/tracer.py`:

1. **Document the schema change** clearly
2. **Update UI rendering** in `index.html`
3. **Consider backwards compatibility** — can old events still render?
4. **Add migration notes** if needed

---

## After Merge

### Celebrate

Your code is now part of AgentGlass!

### Clean Up

```bash
# Delete your local branch
git checkout master
git pull origin master
git branch -d your-branch-name

# Delete remote branch (GitHub usually does this automatically)
git push origin --delete your-branch-name
```

### Follow Up

- Monitor for any issues reported
- Be available to help if questions arise
- Consider writing documentation for significant features

---

## Quick Reference

### PR Checklist

```markdown
## Checklist

- [ ] Tests pass locally (`uv run pytest tests/ -v`)
- [ ] Code is formatted (`uv run ruff format .`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Self-reviewed my changes
- [ ] Added tests for new functionality
- [ ] Updated documentation if needed
- [ ] PR title follows convention (`type: description`)
- [ ] PR description explains the "why"
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Tests failing in CI | Run `uv run pytest tests/ -v` locally first |
| Merge conflicts | Rebase on latest master: `git rebase origin/master` |
| Linting errors | Run `uv run ruff check . --fix` |
| Large diff | Consider splitting into smaller PRs |

---

## The Glass Philosophy

Remember: AgentGlass is about **transparency** — making the invisible visible, the complex understandable, the opaque clear.

Your pull request should embody this same principle. When someone reads your code, they should see through to your intent immediately, like looking through perfectly clear glass.

*Thank you for contributing to AgentGlass.*

---

<p align="center">
  <em>Clarity in code. Transparency in debugging.</em>
</p>
