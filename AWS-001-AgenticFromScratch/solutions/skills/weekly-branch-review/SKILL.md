---
name: weekly-branch-review
description: Weekly performance review for one restaurant branch - last week's sales, best sellers, waste and anything low on stock right now, as a short report for the branch manager. Use when someone asks for a weekly review, weekly report or "how did my branch do last week".
---

# Weekly branch review

Produce a one-page weekly review for a single branch, using the restaurant MCP server's tools.
Every number must come from a tool call. Never estimate or invent figures.

## 1. Work out the branch and the week

- If the user says "my branch" or names no branch, call `who_am_i` and use its `branch_id`. If they give a branch name, call `find_branch` to get the ID.
- "Last week" means the last full Monday-to-Sunday week before today. State the exact dates you used (YYYY-MM-DD) at the top of the report.

## 2. Collect the facts

Call these tools for that branch and week:

1. `get_daily_branch_sales` - orders, revenue and average ticket per day.
2. `get_top_items` with `top_n` 5 - the best sellers.
3. `get_waste_by_item` - what was wasted and what it cost.
4. `list_low_stock_items` - what is low **right now** (live data, not last week).

If a tool returns a note that it limited the data to the user's own branch, say so in the report.
If a tool fails, say which part is missing; do not fill the gap with guesses.

## 3. Write the report

Use exactly these sections, short and in plain words:

**Week of <start> to <end> - <branch name>**

1. **Headline** - one sentence: total revenue and orders for the week, and the best day.
2. **Sales by day** - a small table: date, orders, revenue (USD), average ticket.
3. **Best sellers** - the top 5 items with quantity sold.
4. **Waste** - the top 3 wasted items with quantity and cost (USD), and the week's total waste cost.
5. **Watch now** - items low on stock right now, with on-hand vs par level. If an item is both a best seller and low on stock, put it first and say so.
6. **One suggestion** - one practical action for next week, based only on the facts above.

Money is in USD with two decimals. Keep the whole report under 250 words.
