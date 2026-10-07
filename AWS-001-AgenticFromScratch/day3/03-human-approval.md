# D3 M03 — Human Approval (60m)

## Objectives
- Make the agent stop before any action that changes data, until a person approves or declines.
- Use both approval modes: ask straight away, or pause and resume.
- Explain why approval and policy are different controls, and why we need both.

## Two controls, two questions

| | Policy (Day 2 M05, Cedar on Gateway; checks in `write_tools.py`) | Human approval (today) |
|---|---|---|
| Question it answers | **Is this caller allowed** to do this at all? | **Does a person want this** specific action now? |
| Decided by | Rules written in advance | A person, each time |
| Example | Staff can never refund. A manager can refund only at their own branch | Manager confirms: refund order 202610010120060, USD 12.90, "cold food" |
| Without it | Anyone can do anything | The model acts on a misread request, wrong order or wrong amount |

A person approving does **not** grant permission. A declined call never runs. An approved call still goes through the server checks and policy, which can still refuse it.

## Pre-built
- `WRITE_TOOLS = {"issue_refund", "request_stock_transfer"}` in `src/rst_agent/hooks.py`. Both tool docstrings start with "CHANGES DATA".
- `console_approver` (asks `Approve? [y/N]` in the terminal) and `auto_approver(True/False)`.
- `ask(agent, question, approver)` in `agent.py`: resolves pauses. With no approver it declines.

## Steps
1. **Without approval (5m, instructor demo).** In `solutions/agent`, comment out `hooks.append(ApprovalHook(approver))` in `build_agent()` and ask as manager 12: *Refund my most recent completed order, the customer complained.* The refund happens with no question asked. Restore the line.

2. **Approval hook with Kiro (25m).** In `agent/src/rst_agent/hooks.py`, `ApprovalHook._before`. Prompt Kiro with:
    > Complete the TODO in `ApprovalHook._before` using Strands interrupts (`event.interrupt`). Follow the numbered comments. Make `tests/test_lab3_approval.py` pass without changing the tests.

    Review, check:

    - Tools not in `self.write_tools` return straight away. Every tool in it asks.
    - Only the exact answer `APPROVED` counts. Anything else is `DECLINED`.
    - Declined → `event.cancel_tool` is set, and the message says it was NOT done and must not be retried.
    - With an approver, `response=` is passed so the agent doesn't stop. Without one, no `response`, so the agent pauses.
    - Each decision is appended to `self.decisions`.

    ```bash
    uv run pytest tests/test_lab3_approval.py
    uv run pytest                                # Lab 1 + Lab 3 together
    ```

    ```powershell
    uv run pytest tests/test_lab3_approval.py
    uv run pytest                                # Lab 1 + Lab 3 together
    ```

3. **Mode 1: ask straight away (10m).** The terminal chat passes `console_approver`:

    ```bash
    uv run python -m rst_agent --role manager --branch 12
    ```

    ```powershell
    uv run python -m rst_agent --role manager --branch 12
    ```
    > List today's completed orders, then refund the latest one: cold food.
    ```text
    [step 1] calling list_orders_today {"branch_id": 12, "status": "completed"}
    [step 2] calling issue_refund {"branch_id": 12, "order_id": ..., "reason": "cold food"}

      APPROVAL NEEDED: issue_refund
        branch_id: 12
        order_id: ...
        reason: cold food
      Approve? [y/N]
    ```

    - Answer `n`. The recorder shows `cancelled`. Ask *what is the status of that order?* (`get_order`): not refunded.
    - Ask again and answer `y`. A refund ID `RF-...` comes back, and the order status is now `refunded`.

4. **Mode 2: pause and resume (10m).** This is what a web app or AgentCore Runtime (M05) uses: no one is at a terminal, so the agent stops and hands the decision back. Read the `ask()` loop in `agent.py` with the instructor:

    ```python
    result = agent("Transfer 20 Original Chicken 2pc from branch 12 to branch 5")
    if result.stop_reason == "interrupt":
        pending = result.interrupts[0]   # pending.reason = {"tool", "input", "message"}
        answer = "approved" if person_says_yes(pending.reason) else "declined"
        result = agent([{"interruptResponse": {"interruptId": pending.id, "response": answer}}])
    ```
    `test_without_approver_agent_pauses_for_a_person` checks exactly this. Discuss: where would `person_says_yes` live in Quick, a Slack bot or a web form?

5. **Approval doesn't override policy (10m).** Start the chat as different users and approve every time:

    | User | Request | Approve? | Expected |
    |---|---|---|---|
    | `--role manager --branch 12` | Refund an order at branch 12 | `y` | Refund created |
    | `--role manager --branch 12` | Refund an order at branch 5 | `y` | Refused by the server: "You can only issue refunds for branch 12, not branch 5." |
    | `--role manager --branch 12` | Transfer 20 of item 1 from branch 5 to branch 12 | `y` | Refused: a manager can only send stock from their own branch |
    | `--role staff --branch 12` | Refund an order at branch 12 | `y` | Refused: "Only managers and HQ users can issue refunds." |

    On Gateway (Day 2 M05) the Cedar policy refuses the same calls before they reach the API. The person approved, and the rule still won.

## Checkpoint
The agent stops before `issue_refund`. Deny → no refund in the mock API; approve → refund created. A non-manager is still refused by policy.

## Instructor notes
- Timing: 60m = 5 + 25 + 10 + 10 + 10.
- The mock API keeps refunds in memory. `docker compose restart mock-api` resets them. Refunding the same order twice gives "is refunded and cannot be refunded". This is a good extra test.
- The server also refuses write tools for service-to-service tokens (no person to confirm). Quick's service login can read but can't refund.
- Kiro asks before running MCP tools unless they are auto-approved. Whether Quick shows a confirmation for write tools is not verified. The point here is control **in our agent**, so it works whatever the front end does.

## Learn more
- Strands docs: strandsagents.com → User guide → Interrupts.
- `BeforeToolCallEvent` cancel pattern adapted from the *AWS Building with Amazon Bedrock* workshop ("Event hooks").
