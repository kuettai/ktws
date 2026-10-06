---
inclusion: always
---

# SQL rules for MCP tools

These rules apply to every MCP tool that queries Redshift. Follow them exactly.

## Allowed scope
- Query only views in schema `mcp`. Never reference schema `rst` or any other schema.
- Allowed views are listed in #[[file:docs/data-dictionary.md]]. Do not invent columns or views.
- `SELECT` only. Never generate `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `COPY`, `UNLOAD`, or `CALL`.

## Query shape
- Base every query on a pattern in #[[file:docs/sample-queries.md]]. If no pattern fits, stop and ask the user.
- Explicit column list. Never `SELECT *`.
- Always end with `LIMIT n`, n <= 1000. `LIMIT` must be a literal integer; if the user controls it (e.g. `top_n`), validate it in Python as an int within an allowed range before inserting it.
- Every query on a daily view must filter on `cal_date` with a bounded range. Default max range: 93 days. Validate in Python.
- Every aggregate query must have a matching `GROUP BY`.

## Parameters
- Execute through `run_query(sql, params)` from `lib/redshift.py`. Never call boto3 directly.
- Pass every user-supplied value as a Data API named parameter (`:name`). Never use f-strings, `%`, `.format()`, or concatenation to put values into SQL.
- Data API parameter values are strings. Cast in SQL: `CAST(:branch_id AS INT)`, `CAST(:start_date AS DATE)`.
- Validate in Python before calling, using `lib/validation.py`: `date_range`, `bounded_int`, `positive_int`, `one_of`.
- Raise `ToolInputError` for bad input (the model sees the message). Do not raise plain `ValueError`.

## Branch scoping (after Day 1 M06)
- Get the caller with `current_caller()` from `lib/auth.py` (`role`, `branch_id`; from access token claims `role` / `branch_id`).
- If role is `manager` or `staff`, force `branch_id` to the caller's branch. Ignore any other branch_id the model passes, and say so in a `note` field.
- `hq` may query any branch. Cross-branch rankings are `hq` only.

## Output
- Return rows as a list of objects with column names as keys.
- Include `row_count` and, if the result hit the LIMIT, `truncated: true`.
- Do not return raw Data API response structures.
