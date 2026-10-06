"""Hooks that make the agent's work visible and keep a person in charge of changes.

ToolCallRecorder  records every tool call (step, name, input, status) and prints a trace.
ApprovalHook      pauses before any tool in WRITE_TOOLS until a person approves or declines.

Both use Strands hook events: BeforeToolCallEvent fires just before a tool runs,
AfterToolCallEvent fires once it has finished (or was cancelled).
"""
import json
from collections.abc import Callable
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

# Tools that change data. Everything else on the restaurant MCP server is read-only.
# issueRefund / requestStockTransfer are the same actions when AgentCore Gateway exposes the
# Ops API straight from its OpenAPI contract (tool name = operationId).
WRITE_TOOLS = frozenset({"issue_refund", "request_stock_transfer", "issueRefund", "requestStockTransfer"})

# AgentCore Gateway names tools "<target>___<tool>", e.g. "rst-ops___issue_refund".
GATEWAY_SEPARATOR = "___"


def base_tool_name(name: str) -> str:
    """Tool name without the Gateway target prefix: "rst-ops___issue_refund" -> "issue_refund"."""
    return name.rsplit(GATEWAY_SEPARATOR, 1)[-1]


def is_write_tool(name: str, write_tools: frozenset[str] = WRITE_TOOLS) -> bool:
    """True if the tool changes data, whether called directly or through Gateway."""
    return base_tool_name(name) in write_tools

# An approver decides whether a write tool may run: (tool_name, tool_input) -> True to approve.
Approver = Callable[[str, dict[str, Any]], bool]

APPROVED = "approved"
DECLINED = "declined"


def _short(value: Any, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


class ToolCallRecorder(HookProvider):
    """Stores each tool call in `.calls` and prints it as it happens.

    Each call is a dict: {"step", "name", "input", "status"}.
    status is "running" while the tool runs, then "success", "error" or "cancelled".
    """

    def __init__(self, printer: Callable[[str], None] | None = print):
        self.calls: list[dict[str, Any]] = []
        self._printer = printer
        self._by_id: dict[str, dict[str, Any]] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before)
        registry.add_callback(AfterToolCallEvent, self._after)

    def reset(self) -> None:
        self.calls.clear()
        self._by_id.clear()

    @property
    def tool_names(self) -> list[str]:
        return [c["name"] for c in self.calls]

    def _print(self, line: str) -> None:
        if self._printer:
            self._printer(line)

    def _before(self, event: BeforeToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        if tool_use_id in self._by_id:  # same call fires again when resuming after an approval pause
            return
        call = {
            "step": len(self.calls) + 1,
            "name": event.tool_use["name"],
            "input": dict(event.tool_use.get("input") or {}),
            "status": "running",
        }
        self.calls.append(call)
        self._by_id[tool_use_id] = call
        self._print(f"[step {call['step']}] calling {call['name']} {_short(call['input'])}")

    def _after(self, event: AfterToolCallEvent) -> None:
        call = self._by_id.get(event.tool_use["toolUseId"])
        if call is None:
            return
        if event.cancel_message:
            call["status"] = "cancelled"
            detail = event.cancel_message
        elif isinstance(event.result, Exception):
            call["status"] = "error"
            detail = str(event.result)
        else:
            call["status"] = event.result.get("status", "success")
            detail = " ".join(c.get("text", "") for c in event.result.get("content", []) if "text" in c)
        self._print(f"[step {call['step']}] {call['name']} {call['status']}: {_short(detail, 200)}")


class ApprovalHook(HookProvider):
    """A person must approve every call to a tool in `write_tools` before it runs.

    Uses Strands interrupts (`event.interrupt`):

    - With an `approver` (for example console_approver), the person is asked straight away
      and the agent carries on with their answer.
    - Without one, the agent stops with stop_reason "interrupt". The caller shows the request
      to a person and resumes the agent with their answer. `ask()` does this for you.

    A declined call is cancelled. The model sees the cancel message as the tool result.
    `.decisions` keeps a record: {"name", "input", "decision"}.
    """

    def __init__(self, approver: Approver | None = None, write_tools: frozenset[str] = WRITE_TOOLS):
        self.approver = approver
        self.write_tools = write_tools
        self.decisions: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before)

    def _before(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        if not is_write_tool(name, self.write_tools):
            return
        tool_input = dict(event.tool_use.get("input") or {})
        reason = {"tool": name, "input": tool_input, "message": f"Approve {name}?"}
        if self.approver is not None:
            preset = APPROVED if self.approver(name, tool_input) else DECLINED
            answer = event.interrupt(f"approve_{name}", reason=reason, response=preset)
        else:
            answer = event.interrupt(f"approve_{name}", reason=reason)  # pauses the agent
        decision = APPROVED if answer == APPROVED else DECLINED
        self.decisions.append({"name": name, "input": tool_input, "decision": decision})
        if decision == DECLINED:
            event.cancel_tool = (
                f"A person declined this action ({name}). It was NOT done. "
                "Do not retry. Tell the user it was not carried out."
            )


def console_approver(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Ask in the terminal. Only 'y' or 'yes' approves."""
    print(f"\n  APPROVAL NEEDED: {tool_name}")
    for key, value in tool_input.items():
        print(f"    {key}: {value}")
    return input("  Approve? [y/N] ").strip().lower() in ("y", "yes")


def auto_approver(approve: bool) -> Approver:
    """Always approve or always decline. For tests and automated evaluation runs."""
    return lambda tool_name, tool_input: approve
