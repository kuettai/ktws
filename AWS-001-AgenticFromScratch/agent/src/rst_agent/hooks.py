"""Hooks that make the agent's work visible and keep a person in charge of changes.

ToolCallRecorder  records every tool call (step, name, input, status) and prints a trace.   (Lab 1)
ApprovalHook      pauses before any tool in WRITE_TOOLS until a person approves or declines. (Lab 3)

Both use Strands hook events: BeforeToolCallEvent fires just before a tool runs,
AfterToolCallEvent fires once it has finished (or was cancelled).
Docs: strandsagents.com, "Hooks" and "Interrupts" pages. A worked interrupt example is in the
installed package: .venv/lib/python3.12/site-packages/strands/types/interrupt.py

The TODOs below are yours to complete with Kiro. Describe what you want, let Kiro write it,
then review the code and run `uv run pytest` to check. The tests describe the expected behaviour.
"""
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


class ToolCallRecorder(HookProvider):
    """Stores each tool call in `.calls` and prints it as it happens.

    Each call is a dict: {"step", "name", "input", "status"}.
    status is "running" while the tool runs, then "success", "error" or "cancelled".
    """

    def __init__(self, printer: Callable[[str], None] | None = print):
        self.calls: list[dict[str, Any]] = []
        self._printer = printer

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before)
        registry.add_callback(AfterToolCallEvent, self._after)

    def reset(self) -> None:
        self.calls.clear()

    @property
    def tool_names(self) -> list[str]:
        return [c["name"] for c in self.calls]

    def _before(self, event: BeforeToolCallEvent) -> None:
        # TODO (Lab 1): append a call record and print "[step N] calling <name> <input>".
        #   event.tool_use has "toolUseId", "name" and "input".
        #   The same toolUseId can arrive twice when the agent resumes after an approval
        #   pause (Lab 3). Record it only once.
        pass

    def _after(self, event: AfterToolCallEvent) -> None:
        # TODO (Lab 1): find the record for event.tool_use["toolUseId"] and set its status:
        #   "cancelled" if event.cancel_message is set,
        #   "error" if event.result is an Exception,
        #   otherwise event.result["status"] ("success" or "error").
        #   Print "[step N] <name> <status>: <short result>".
        pass


class ApprovalHook(HookProvider):
    """A person must approve every call to a tool in `write_tools` before it runs.

    With an `approver`, ask straight away. Without one, pause the agent with an interrupt
    so the caller can ask a person and resume. A declined call is cancelled.
    `.decisions` keeps a record: {"name", "input", "decision"}.
    """

    def __init__(self, approver: Approver | None = None, write_tools: frozenset[str] = WRITE_TOOLS):
        self.approver = approver
        self.write_tools = write_tools
        self.decisions: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._before)

    def _before(self, event: BeforeToolCallEvent) -> None:
        # TODO (Lab 3):
        #   1. Ignore read-only tools. Use is_write_tool(name, self.write_tools), not a plain
        #      `in` check: through Gateway the name is "rst-ops___issue_refund".
        #   2. Build reason = {"tool": name, "input": tool_input, "message": f"Approve {name}?"}.
        #   3. Get the answer with event.interrupt(f"approve_{name}", reason=reason, ...):
        #        - with self.approver: pass response=APPROVED or DECLINED from the approver,
        #          so the agent does not stop;
        #        - without: call it with no response. The agent pauses until resumed.
        #   4. Append to self.decisions.
        #   5. If declined, set event.cancel_tool to a message telling the model it was
        #      declined, was NOT done, and must not be retried.
        pass


def console_approver(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Ask in the terminal. Only 'y' or 'yes' approves."""
    print(f"\n  APPROVAL NEEDED: {tool_name}")
    for key, value in tool_input.items():
        print(f"    {key}: {value}")
    return input("  Approve? [y/N] ").strip().lower() in ("y", "yes")


def auto_approver(approve: bool) -> Approver:
    """Always approve or always decline. For tests and automated evaluation runs."""
    return lambda tool_name, tool_input: approve
