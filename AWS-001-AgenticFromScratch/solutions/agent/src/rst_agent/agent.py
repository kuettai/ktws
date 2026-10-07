"""Build the restaurant agent and run questions through it."""
import os
from collections.abc import Sequence
from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.models import BedrockModel, Model

from rst_agent.hooks import APPROVED, DECLINED, ApprovalHook, Approver, ToolCallRecorder

# Cross-region inference profile. Override with BEDROCK_MODEL_ID, for example a "us." profile
# if "global." is not enabled in your account.
DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-5-5"

SYSTEM_PROMPT = """\
You are an analyst assistant for a quick-service restaurant chain with about 30 branches.
You help HQ analysts and branch managers answer questions about sales, menu items, stock and waste.

How to work:
1. Plan first. Work out which facts you need and which tool gives each one, then call the tools.
2. Use tools for every number. Never guess, estimate or invent figures. If a tool cannot give
   the answer, say so plainly.
3. History up to yesterday comes from the Redshift tools (get_*_sales, get_top_*, get_waste_*,
   get_peak_hours, get_channel_mix, compare_weekend_weekday). Live, today-only data comes from
   the operations tools (get_current_stock, list_low_stock_items, get_today_sales,
   list_orders_today, get_order).
4. If you only know a branch name, call find_branch first to get its ID.
5. Dates are YYYY-MM-DD. Resolve relative dates ("last month", "this week") to exact dates and
   state the range you used.
6. issue_refund and request_stock_transfer change data. Only call them when the user clearly asks
   for that action, with all the details. A person must approve each one. If it is declined,
   do not retry.
7. If a tool returns a note that it limited the data to your own branch, tell the user.
8. If the request is unclear, ask one short clarifying question instead of guessing.

Answer briefly: the figures first, then one or two lines of explanation. Money is in USD.
"""


def default_model(model_id: str | None = None) -> BedrockModel:
    # Sonnet 5.5 rejects `temperature` ("deprecated for this model"), so only send it when asked,
    # e.g. BEDROCK_TEMPERATURE=0 with an older model for more repeatable evaluation runs.
    settings = {}
    if os.environ.get("BEDROCK_TEMPERATURE"):
        settings["temperature"] = float(os.environ["BEDROCK_TEMPERATURE"])
    return BedrockModel(
        model_id=model_id or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
        region_name=os.environ.get("AWS_REGION"),
        **settings,
    )


def build_agent(
    tools: Sequence[Any],
    *,
    approver: Approver | None = None,
    recorder: ToolCallRecorder | None = None,
    model_id: str | None = None,
    model: Model | None = None,
    system_prompt: str = SYSTEM_PROMPT,
    callback_handler: Any = None,
) -> Agent:
    """Create the restaurant agent.

    tools     MCP tools (connections.all_tools(client)) and/or @tool functions.
    approver  decides on write tools straight away. None means the agent pauses
              (stop_reason "interrupt") and ask() resolves the pause.
    recorder  a ToolCallRecorder to trace tool calls. Pass your own to read .calls afterwards.
    model     any Strands model; default is Bedrock with BEDROCK_MODEL_ID (or DEFAULT_MODEL_ID).

    Write tools always need approval: the ApprovalHook is installed whatever you pass.
    """
    hooks = [recorder] if recorder is not None else []
    hooks.append(ApprovalHook(approver))
    return Agent(
        model=model or default_model(model_id),
        tools=list(tools),
        system_prompt=system_prompt,
        hooks=hooks,
        callback_handler=callback_handler,
    )


def ask(agent: Agent, question: str, approver: Approver | None = None, max_pauses: int = 5) -> AgentResult:
    """Run one question. If the agent pauses for approval, ask `approver` and resume.

    With no approver, every pending write action is declined (safe default).
    """
    result = agent(question)
    for _ in range(max_pauses):
        if result.stop_reason != "interrupt":
            return result
        responses = []
        for interrupt in result.interrupts:
            reason = interrupt.reason or {}
            approved = approver is not None and approver(reason.get("tool", ""), reason.get("input", {}))
            responses.append(
                {"interruptResponse": {"interruptId": interrupt.id, "response": APPROVED if approved else DECLINED}}
            )
        result = agent(responses)
    raise RuntimeError(f"Agent paused for approval more than {max_pauses} times in one question")
