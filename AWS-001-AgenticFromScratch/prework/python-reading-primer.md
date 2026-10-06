# Pre-work — Python Reading Primer (60m)

In this workshop **Kiro writes the Python. You read it and approve it.** This primer teaches you
to *read* Python well enough to review Kiro's work. You will not write Python from scratch.

Every example comes from the workshop's own code (`solutions/mcp-server/`), so on Day 1 it will
already look familiar. If you know SQL, you already know more than you think: Python here mostly
wraps SQL you could write yourself.

| Part | Topic | Time |
|---|---|---|
| 1 | Reading a function: names, type hints, docstrings | 10m |
| 2 | Decorators and modules: how a function becomes an MCP tool | 8m |
| 3 | Data shapes: dict, list, None | 7m |
| 4 | f-strings vs parameterised SQL (the most important part) | 12m |
| 5 | Errors: exceptions and `ToolError` | 8m |
| 6 | Environment variables and `async` (recognise only) | 5m |
| 7 | Running tests and reading a failure | 5m |
| — | Self-check quiz and review checklist | 5m |

Tip: open `solutions/mcp-server/` in Kiro alongside this page and find each example.

---

## 1. Reading a function (10m)

From `tools/redshift_tools.py`:

```python
@mcp.tool()
def get_daily_branch_sales(branch_id: int, start_date: str, end_date: str) -> dict:
    """Daily order count, revenue (USD) and average ticket for one branch.

    Use for historical sales up to yesterday. For today's live sales use get_today_sales.
    If you only know the branch name, call find_branch first.

    Args:
        branch_id: Branch ID, e.g. 12.
        start_date: First day, YYYY-MM-DD, e.g. 2026-09-01.
        end_date: Last day inclusive, YYYY-MM-DD. Max 93 days after start_date.
    """
    branch_id, note = scoped_branch(branch_id)
    start, end = date_range(start_date, end_date)
    rows = run_query(
        """
        SELECT cal_date, branch_name, order_count, revenue, avg_ticket
        FROM mcp.v_daily_branch_sales
        WHERE branch_id = CAST(:branch_id AS INT)
          AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        ORDER BY cal_date
        LIMIT 100
        """,
        {"branch_id": branch_id, "start_date": start, "end_date": end},
    )
    return _result(rows, 100, note)
```

Read it top to bottom:

| Piece | Meaning | SQL analogy |
|---|---|---|
| `def get_daily_branch_sales(...)` | Defines a function: a named, reusable block | A stored procedure or saved query |
| `branch_id: int, start_date: str` | Inputs (parameters) with **type hints**: `int` = whole number, `str` = text | Column types |
| `-> dict` | What the function returns | The result set shape |
| `"""..."""` under `def` | **Docstring**: a description written in plain English | A comment block |
| Indentation | The function body is everything indented under `def`. Indentation *is* the structure in Python, there are no `BEGIN`/`END` | `BEGIN ... END` |
| `start, end = date_range(...)` | Call another function and store its two results | `SELECT ... INTO` |
| `return` | Send the result back and stop | The final `SELECT` |

**Why the docstring matters most to you:** for an MCP tool, the docstring *is* the tool description
the AI model reads to decide which tool to call. The type hints become the parameter schema. A
vague docstring means the model picks the wrong tool. Reviewing docstrings is an analyst job, not a
developer job. See `kiro/steering/mcp-tool-design.md`.

Also notice `_result(...)`. A leading underscore means "internal helper, not a tool".

---

## 2. Decorators and modules (8m)

### Decorators: `@mcp.tool()`

A line starting with `@` just above a `def` is a **decorator**. It wraps the function to add
behaviour. Here, `@mcp.tool()` registers the function as an MCP tool. Without that one line, the
function exists but no AI client can see it.

From `tools/hello.py`:

```python
@mcp.tool()
def ping(name: str) -> str:
    """Health check. Returns a greeting.

    Args:
        name: Who is saying hello, e.g. "Alex".
    """
    return f"Hello {name}, restaurant MCP is alive"
```

Review tip: when Kiro says "I added a tool", check for `@mcp.tool()`. When it adds a helper that
should *not* be visible to the model, check there is **no** decorator.

### Modules and imports

Each `.py` file is a **module**. `import` brings in code from another file or library. From
`app.py`:

```python
from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    "rst",
    instructions=("Tools for a quick-service restaurant chain. Money is in USD. ..."),
    ...
)
```

and at the top of every tool file:

```python
from app import mcp                      # the shared server object from app.py
from lib.redshift import run_query       # pre-built helper: lib/redshift.py
from lib.validation import date_range    # pre-built helper: lib/validation.py
```

`from lib.redshift import run_query` means "from file `lib/redshift.py`, use `run_query`". Read the
imports first: they tell you what a file depends on.

> **Note:** this workshop uses **MCP Python SDK v2**, where the server class is `MCPServer`
> (`from mcp.server.mcpserver import MCPServer`). Many blog posts and older examples use
> `FastMCP`, which is the v1 name. If Kiro writes `FastMCP`, ask it to use `MCPServer`.

`server.py` imports each tool file once (`import tools.redshift_tools`). That import is what runs
the `@mcp.tool()` lines and registers the tools. A new tool file that isn't imported in `server.py`
won't show up.

---

## 3. Data shapes: dict, list, None (7m)

| Python | Looks like | SQL analogy |
|---|---|---|
| `dict` | `{"branch_id": 12, "revenue": 1830.5}` | One row: column name → value |
| `list` | `[1, 2, 3]` or `[{...}, {...}]` | A result set: many rows |
| `None` | `None` | `NULL` |
| `True` / `False` | | Boolean |

`run_query` returns a **list of dicts**, exactly like a query result:

```python
[
    {"cal_date": "2026-09-01", "branch_name": "Branch Harbor Point", "order_count": 412, "revenue": 18304.5},
    {"cal_date": "2026-09-02", "branch_name": "Branch Harbor Point", "order_count": 398, "revenue": 17650.0},
]
```

The tool then wraps it in a dict with extra fields (`_result` in `tools/redshift_tools.py`):

```python
result = {"rows": rows, "row_count": len(rows), "truncated": len(rows) >= limit}
```

`len(rows)` = number of rows, like `COUNT(*)`. `truncated` tells the model "there may be more".

Optional parameters use `| None` and a default. From `tools/ops_tools.py`:

```python
def get_current_stock(branch_id: int, item_id: int | None = None) -> dict:
    branch_id, note = scoped_branch(branch_id)
    if item_id is None:
        return _with_note({"items": _get(f"/inventory/{branch_id}/stock")}, note)
```

Read `item_id: int | None = None` as: "a whole number, or nothing; if not given, nothing".
`if item_id is None:` is the branch for "all items".

The `return` line packs several calls together. Read it **inside out**, like a nested SQL subquery:

1. `f"/inventory/{branch_id}/stock"` builds the web address, e.g. `/inventory/12/stock`. (An f-string is fine here: it is a URL, not SQL, and `branch_id` is a checked whole number.)
2. `_get(...)` calls the Ops API at that address and returns its answer, a list of stock rows. If the API fails, `_get` raises a message the model can read.
3. `{"items": ...}` puts that list in a dict under the key `items`.
4. `_with_note(result, note)` adds a `"note"` key only if there is one. The note comes from `scoped_branch` on the line above: a branch 12 manager who asks for branch 5 gets branch 12, plus a note saying so.

In plain words: *get live stock for this branch, label it `items`, attach a note if the user was limited to their own branch, and return it.*

---

## 4. f-strings vs parameterised SQL (12m) — the most important part

An **f-string** is text with `f` in front and values in `{}`:

```python
f"Hello {name}, restaurant MCP is alive"      # name="Alex" gives "Hello Alex, restaurant MCP is alive"
```

That's fine for messages. **It is dangerous for SQL.** Here is the "whiteboard idea" you will
review on Day 1:

```python
# WRONG: never do this
sql = f"SELECT SUM(revenue) FROM mcp.v_daily_branch_sales WHERE branch_name = '{branch_name}'"
```

The model (or a user) controls `branch_name`. If it sends `x' OR '1'='1`, the SQL becomes:

```sql
SELECT SUM(revenue) FROM mcp.v_daily_branch_sales WHERE branch_name = 'x' OR '1'='1'
```

That returns *every* branch, bypassing branch scoping. This is **SQL injection**: the input is
treated as SQL, not as a value.

**The safe pattern** in this repo: put `:name` placeholders in the SQL and pass the values
separately. The database treats them only as values, never as SQL. From
`get_daily_branch_sales` above:

```python
rows = run_query(
    """
    SELECT ... FROM mcp.v_daily_branch_sales
    WHERE branch_id = CAST(:branch_id AS INT)
      AND cal_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
    """,
    {"branch_id": branch_id, "start_date": start, "end_date": end},   # values go here
)
```

`lib/redshift.py` says it at the top: *"Never build SQL with f-strings: pass values in params and
reference them in SQL as :name."* Values arrive as text, which is why the SQL uses `CAST(... AS INT)`.

### The one allowed exception, and why it's safe

`LIMIT` can't take a placeholder. From `get_top_branches`:

```python
top_n = bounded_int(top_n, "top_n", 1, 50)       # must be a whole number from 1 to 50
rows = run_query(
    f"""
    SELECT ...
    LIMIT {top_n}
    """,  # top_n is a validated int; LIMIT does not accept bind parameters
    {"start_date": start, "end_date": end},
)
```

There *is* an f-string here, but only for `top_n`, and only **after** `bounded_int` guarantees it
is a number between 1 and 50. A number can't contain `' OR '1'='1`. When you review: **every
`{...}` inside SQL must be a validated number**. Anything else is a defect.

### Validation happens first

Every tool validates inputs before touching SQL, using `lib/validation.py`:

```python
def bounded_int(value: int, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolInputError(f"{field} must be a whole number")
    if not low <= value <= high:
        raise ToolInputError(f"{field} must be between {low} and {high}")
    return value
```

Read it as: "if it's not a whole number, reject it; if it's out of range, reject it; otherwise
return it." `date_range` does the same for dates (format, order, max 93 days) and `one_of` for
allowed values such as categories.

---

## 5. Errors: exceptions and `ToolError` (8m)

`raise` stops the function and reports an error, called an **exception**. What the AI model sees
depends on the *type* of exception:

| Raised | What the model sees |
|---|---|
| `ToolError` or a subclass (`ToolInputError`, `QueryError` in this repo) | **Your message**, e.g. `top_n must be between 1 and 50` |
| Anything else (`ValueError`, `KeyError`, a crash) | Only `Error executing tool <name>`, with no detail |

From `lib/validation.py`:

```python
class ToolInputError(ToolError, ValueError):
    """Invalid tool input. The message is shown to the model so it can correct the call.

    Any other exception is treated as a crash: the model only sees "Error executing tool <name>".
    """
```

`class ToolInputError(ToolError, ...)` means "a kind of `ToolError`". So its message reaches the
model, and the model can fix its call and try again. That makes good error messages part of tool
design.

The other side: **messages must not leak internals**. From `lib/redshift.py`:

```python
if status in ("FAILED", "ABORTED"):
    log.error("Query %s %s: %s", statement_id, status, desc.get("Error"))     # details to the log
    raise QueryError("The query failed. Check the parameters and try again.")  # safe message to model
```

The real database error goes to the **log** (for engineers). The model gets a generic message, with
no SQL text, table names or hostnames.

You will also see `try: ... except ...:` blocks, which mean "try this; if that specific error
happens, do this instead". From `tools/ops_tools.py`:

```python
try:
    response = httpx.get(...)
except httpx.HTTPError as e:
    log.error("Operations API unreachable: %s", e)
    raise ToolInputError("The operations system is unavailable. Try again shortly.") from None
```

---

## 6. Environment variables and `async` (5m)

### Environment variables

Settings and secrets come from the environment, never from code. From `lib/redshift.py` and
`tools/ops_tools.py`:

```python
target = {"Database": os.environ["REDSHIFT_DATABASE"]}               # required: fails if missing
if workgroup := os.environ.get("REDSHIFT_WORKGROUP"):                # optional: None if missing
    ...
headers={"X-API-Key": os.environ["OPS_API_KEY"]}
```

`os.environ["X"]` is required; `os.environ.get("X")` is optional. Locally these come from `.env`;
on ECS, from Secrets Manager. **If you see an API key, password or token typed into a `.py` file,
reject the change.**

### `async` / `await` (recognise only)

You will see these in `server.py` and `lib/auth.py`:

```python
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

`async def` / `await` let the server wait for slow things (network, token checks) without blocking
other requests. You don't need to understand more than that. Our tools are plain `def`, which works
fine.

---

## 7. Running tests and reading a failure (5m)

Tests are small functions that check the code does what it should. From
`tests/test_validation.py`:

```python
def test_bounded_int():
    assert bounded_int(5, "top_n", 1, 50) == 5
    for bad in (0, 51, True, "5", 5.0):
        with pytest.raises(ToolInputError):
            bounded_int(bad, "top_n", 1, 50)
```

`assert X == Y` means "this must be true". `pytest.raises(ToolInputError)` means "this call must be
rejected". Note the test feeds injection-style input elsewhere (`"2026-09-01'; DROP TABLE x;--"`)
and expects rejection.

Run all tests from the server folder:

```bash
cd solutions/mcp-server
uv run pytest
```

```powershell
cd solutions/mcp-server
uv run pytest
```

A pass ends with a line such as `N passed in 1.2s`. Here is a real failure, from a test that wrongly
expects `top_n=100` to be allowed:

```
    def test_top_n_allows_100():
>       assert bounded_int(100, "top_n", 1, 50) == 100

value = 100, field = 'top_n', low = 1, high = 50
...
>           raise ToolInputError(f"{field} must be between {low} and {high}")
E           lib.validation.ToolInputError: top_n must be between 1 and 50

lib/validation.py:41: ToolInputError
=========================== short test summary info ============================
FAILED test_primer_demo.py::test_top_n_allows_100
1 failed in 0.56s
```

How to read it:

1. **Bottom first:** `FAILED ...::test_top_n_allows_100` tells you which test.
2. **`>` lines** show the exact line that failed.
3. **`E` lines** show the error: `top_n must be between 1 and 50`.
4. **`file.py:41`** is where to look.

Then decide: is the **code** wrong, or is the **test** wrong? Here the test is wrong (50 is the
agreed maximum). This judgement call is yours. Don't let Kiro "fix" a failing test by weakening it
without checking.

---

## Self-check quiz

1. In `def get_top_items(branch_id: int, start_date: str, ...) -> dict:`, what type is `start_date`, and what does the function return?
2. Why does the docstring of an MCP tool matter more than a normal code comment?
3. Kiro adds a function `calculate_waste_cost` but you can't see it in MCP Inspector. What one line is probably missing?
4. What is the SQL equivalent of a Python `dict`? Of a list of dicts?
5. Is this safe? `run_query(f"SELECT ... WHERE category = '{category}' LIMIT 10")`. Why or why not?
6. Is this safe? `top_n = bounded_int(top_n, "top_n", 1, 50)` followed by `f"... LIMIT {top_n}"`. Why?
7. A tool raises `ValueError("branch 99 not found")`. What does the model see? What should it raise instead?
8. Why does `lib/redshift.py` log the real database error but send the model a generic message?
9. What's the difference between `os.environ["OPS_API_KEY"]` and `os.environ.get("OPS_API_KEY")`?
10. A test fails with `E  ToolInputError: Date range is limited to 93 days`. Where do you look first, and what question do you ask before letting Kiro change anything?

<details>
<summary>Answers</summary>

1. `start_date` is text (`str`), e.g. `"2026-09-01"`. It returns a `dict`.
2. For MCP tools the docstring is the tool description the AI model reads to choose the tool and fill its parameters. Bad description, wrong tool choice.
3. `@mcp.tool()` above the `def` (or the file isn't imported in `server.py`).
4. A dict is one row (column → value). A list of dicts is a result set.
5. **Not safe.** `category` goes straight into the SQL text, so input like `x' OR '1'='1` changes the query (SQL injection). Use `:category` in SQL with the value in `params`, and validate it with `one_of`.
6. **Safe.** `bounded_int` guarantees a whole number from 1 to 50 before it's inserted. `LIMIT` can't take a placeholder, so this is the one allowed exception.
7. Only `Error executing tool <name>`. Raise `ToolInputError("branch 99 not found, call find_branch")` so the model can correct itself.
8. The real error can contain SQL, table names or internal details. Those go to the log for engineers. The model gets a safe message it can act on.
9. `["..."]` is required: the program fails if it's missing. `.get(...)` is optional: it returns `None` if missing.
10. Read the `>` and `E` lines and the `file.py:line`. Then ask: is the code wrong, or is the test wrong? Don't accept a "fix" that just loosens the rule (e.g. raising the 93-day limit) unless that was agreed.

</details>

---

## Checklist: reviewing Kiro's code

Use this on every change Kiro makes on Day 1.

**SQL safety**

- [ ] No f-string, `%`, `.format()` or `+` putting values into SQL. Values go through `:name` placeholders and `params`.
- [ ] Any `{...}` inside SQL is a number already checked by `bounded_int`.
- [ ] Only `mcp.` views. No `rst.` schema, no `SELECT *`, always a `LIMIT`.
- [ ] Every input validated first (`date_range`, `bounded_int`, `positive_int`, `one_of`).

**Tool design**

- [ ] Has `@mcp.tool()` if it should be a tool, and no decorator if it's a helper.
- [ ] Docstring says what question it answers, when to use it vs similar tools, units (USD) and formats (YYYY-MM-DD).
- [ ] Every parameter in `Args:` has an example value.
- [ ] Name is `verb_noun`, one business question per tool.

**Access and errors**

- [ ] Branch-level tools call `scoped_branch(...)`. Cross-branch tools call `require_hq(...)`.
- [ ] Errors for the model are `ToolInputError` with a message that helps it fix the call.
- [ ] No SQL text, stack traces, hostnames or secrets in messages.
- [ ] No keys or passwords in code. Settings come from `os.environ`.

**Scope**

- [ ] Only the files you expected changed (no surprise edits to `lib/auth.py`, `infra/`, tests).
- [ ] `MCPServer`, not `FastMCP`.
- [ ] `uv run pytest` passes, and no test was weakened to make it pass.

Next: [Reviewing Kiro: specs, steering and hooks](kiro-guide.md).
</content>
</invoke>
