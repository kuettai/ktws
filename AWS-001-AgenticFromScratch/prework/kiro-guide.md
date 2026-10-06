# Pre-work — Reviewing Kiro: Specs, Steering and Hooks (25m)

Kiro writes the code in this workshop. Your job is to **direct and review it**. Kiro gives you
three ways to do that:

| Feature | What it is | Your role |
|---|---|---|
| **Specs** | Kiro writes a plan (requirements → design → tasks) before coding | Approve each phase before Kiro moves on |
| **Steering** | Markdown rules Kiro always follows in this project | Write and maintain the rules (e.g. SQL safety) |
| **Hooks** | Automatic actions on events (file saved, tool about to run) | Turn on automatic checks so you don't rely on memory |

Read with Kiro open. Kiro changes often; if a screen differs from this guide, check
[kiro.dev/docs](https://kiro.dev/docs/).

**What you need to do: read only.** You don't create any `.kiro` files for this pre-work.

| File | Where it comes from | When |
|---|---|---|
| Steering rules (`sql-rules.md`, `mcp-tool-design.md`) | Ready-made in the repo, in `kiro/steering/` | You copy them into `.kiro/steering/` in Day 1 M01 step 6 |
| MCP server config (`mcp.json`) | `kiro/mcp.json.example` in the repo | You copy it into `.kiro/settings/mcp.json` in Day 1 M01 step 5 |
| Specs (`requirements.md`, `design.md`, `tasks.md`) | **Kiro writes them** | Day 1 M03 Exercise A. You review and approve them |
| Hooks | Examples in this guide only | Optional. Not used in the labs |

The repo keeps these under `kiro/` (no dot) on purpose: Kiro reads `.kiro/` automatically, so copying
them in M01 is the moment the rules take effect.

---

## 1. Specs (10m)

For anything bigger than a one-line change, ask Kiro for a **spec** instead of jumping to code.
In the Kiro panel choose **Specs → +**, or pick **Spec** in chat. Kiro stores the spec under
`.kiro/specs/<name>/` as three files. There is an approval step between each phase. That
step is your review.

### `requirements.md` — *what* will be built

Written as user stories with acceptance criteria in EARS format:

```
WHEN a branch manager asks for waste by item
THE SYSTEM SHALL return waste quantity and cost (USD) for their own branch only
```

Check:

- [ ] Matches the business question you actually asked. Analysts are the experts here.
- [ ] Data scope is stated: which branches, which date range, which role sees what.
- [ ] Edge cases: no data, branch not found, range too long, wrong role.
- [ ] Nothing extra you didn't ask for (new write actions, new data sources).
- [ ] Each criterion is testable: you could write the expected answer with SQL.

### `design.md` — *how* it will be built

Check:

- [ ] Data source is right: Redshift `mcp` views for history, Operations API for live data.
- [ ] Views and columns exist in `docs/data-dictionary.md`. Query matches a pattern in `docs/sample-queries.md`.
- [ ] Tool names, descriptions and parameters follow `kiro/steering/mcp-tool-design.md`.
- [ ] Reuses `lib/` helpers (`run_query`, `date_range`, `scoped_branch`) instead of new ones.
- [ ] No new credentials, IAM permissions or infrastructure unless you expected them.

### `tasks.md` — the step-by-step plan

Check:

- [ ] Small, ordered tasks. Each says which file it changes.
- [ ] Includes a test task (`uv run pytest`) and an MCP Inspector check.
- [ ] Nothing touches files outside the tool you are building (e.g. `lib/auth.py`, `infra/`).

Run tasks one at a time at first, and review the diff after each. Reject and re-prompt rather
than fixing Kiro's code by hand. The fix then stays in the spec.

---

## 2. Steering (8m)

Steering files are markdown rules Kiro includes in its context, so you don't repeat them in
every prompt.

| Scope | Location | Use for |
|---|---|---|
| Workspace | `.kiro/steering/` in the project | Project rules (this workshop's SQL and tool rules) |
| Global | `~/.kiro/steering/` in your home folder | Personal preferences across all projects |

If they conflict, workspace rules win. Kiro also reads an `AGENTS.md` file in the project root
(always included).

### Worked example 1: `kiro/steering/sql-rules.md`

Open the file. It starts with front matter:

```yaml
---
inclusion: always
---
```

`always` means the rules load on every request. Other modes:

- `fileMatch` with `fileMatchPattern: "tools/**/*.py"`: only when matching files are involved
- `manual`: only when you type `#sql-rules` in chat
- `auto`: when the request matches a `description`

The front matter must be the very first thing in the file.

Notice how the rules are written:

- **Specific and checkable:** "Always end with `LIMIT n`, n <= 1000", not "keep queries small".
- **Points at sources of truth** with file references: `#[[file:docs/data-dictionary.md]]` pulls
    the allowed views into context, so Kiro can't invent columns.

- **Says what to do when stuck:** "If no pattern fits, stop and ask the user."

### Worked example 2: `kiro/steering/mcp-tool-design.md`

This file encodes the analyst skill: naming (`verb_noun`), descriptions (question, when to use,
units), errors, and a full example tool. Kiro copies the example's style, so **a good example in
steering is worth ten rules**.

### Steering is guidance, not enforcement

On Day 1 M02 you will remove steering and watch Kiro write a `DELETE` tool. The database grants
still block it. Steering makes Kiro *likely* to do the right thing. Grants, tests and your review
make sure it does.

Check when reviewing or writing steering:

- [ ] Each rule is concrete enough that you could check the code against it.
- [ ] Files that set scope (data dictionary, sample queries) are referenced, not copied.
- [ ] When a Kiro mistake comes up twice, add a rule for it.

---

## 3. Hooks (7m)

> **Optional.** The labs don't use hooks. The two examples below are for trying after the
> workshop, or on Day 1 if you finish early: create the file in `.kiro/hooks/` yourself.

Hooks run something automatically when an event happens, for example when a file is saved or
before Kiro calls a tool. Each hook is a JSON file in `.kiro/hooks/` (any descriptive name, e.g.
`test-on-save.json`). Hooks turn on automatically when a session starts.

A hook has a **trigger** (when), an optional **matcher** (regex on file path or tool name), and an
**action**:

- `command` — run a shell command in the project root
- `agent` — send a prompt to Kiro

### Example A: run tests whenever a tool file is saved

`.kiro/hooks/test-on-save.json`:

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "Run tests on tool save",
      "trigger": "PostFileSave",
      "matcher": "tools/.*\\.py$",
      "action": { "type": "command", "command": "uv run pytest -q" }
    }
  ]
}
```

On success, the output goes back to Kiro. On failure (non-zero exit), Kiro is told the hook failed
and sees the error, so it can fix the problem.

### Example B: ask Kiro to check SQL against the rules

```json
{
  "version": "v1",
  "hooks": [
    {
      "name": "SQL rules check",
      "trigger": "PostFileSave",
      "matcher": "tools/.*\\.py$",
      "action": {
        "type": "agent",
        "prompt": "Review the SQL in the file just saved against .kiro/steering/sql-rules.md. List any rule broken (f-string values, non-mcp schema, SELECT *, missing LIMIT, unbounded date range) and fix it."
      }
    }
  ]
}
```

Example A is deterministic: tests pass or fail. Example B relies on the model and can miss things.
Use both. Treat B as a second reviewer, not as a guarantee.

A `PreToolUse` hook can also check or block a tool call before it runs. On Day 3 you will see the
same idea inside an agent: pause before a data-changing action and ask a person to approve it.

Check:

- [ ] The `matcher` targets only the files you mean (an over-broad matcher runs on every save).
- [ ] Command hooks are quick (the default timeout is 60s).
- [ ] You know which hooks are on. Check `.kiro/hooks/` when something runs unexpectedly.

---

## Summary

| | Specs | Steering | Hooks |
|---|---|---|---|
| Lives in | `.kiro/specs/<name>/` | `.kiro/steering/` | `.kiro/hooks/` |
| Answers | What and how, for this change | Rules for every change | Checks that run every time |
| Your review | Approve each phase | Keep rules concrete and current | Keep them targeted and fast |

Together with the code checklist in the [Python reading primer](python-reading-primer.md#checklist-reviewing-kiros-code),
this is how you stay in control of AI-written code.
</content>
</invoke>
