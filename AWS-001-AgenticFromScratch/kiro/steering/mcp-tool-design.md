---
inclusion: always
---

# MCP tool design conventions

## Naming
- `verb_noun` in snake_case: `get_daily_branch_sales`, `list_low_stock_items`, `find_branch`.
- One business question per tool. Do not create one tool per API endpoint by default; combine or skip endpoints when that serves the user better.
- Write tools (refund, transfer) start with an action verb (`issue_refund`, `request_stock_transfer`) and say "This changes data" in the description.

## Descriptions (the model chooses tools from these)
Every tool description must state:

1. What business question it answers, in plain language.
2. When to use it vs similar tools (e.g. "Use for historical data. For today's live numbers use get_today_sales").
3. Units and currency (USD), date format (YYYY-MM-DD), and limits (max range, max rows).

Every parameter needs a description with an example value.

Example:

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
```

## Data source choice
- Historical / analytical → Redshift `mcp` views.
- Real-time / operational (current stock, open orders, today's sales) → Operations API.

## Errors
- Return a clear message the model can act on: "start_date must be YYYY-MM-DD", "branch 99 not found, call find_branch".
- Never return stack traces, SQL text, credentials, or internal hostnames.

## Secrets
- Never hard-code API keys, passwords, or tokens. Read from environment variables populated from AWS Secrets Manager.
