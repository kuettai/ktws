"""A scripted model and fake restaurant tools, so tests never call Bedrock or AWS."""
import json
from typing import Any

from strands import tool
from strands.models import Model


class ScriptedModel(Model):
    """Replays a fixed list of turns.

    Each turn is either a string (final text answer) or a list of (tool_name, input) pairs
    (the model asks for those tools). `seen` keeps the messages passed on every call.
    """

    def __init__(self, turns: list[str | list[tuple[str, dict[str, Any]]]]):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []
        self._ids = 0

    def update_config(self, **model_config: Any) -> None:
        pass

    def get_config(self) -> dict:
        return {}

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.seen.append(json.loads(json.dumps(messages, default=str)))
        turn = self.turns.pop(0) if self.turns else "done"
        yield {"messageStart": {"role": "assistant"}}
        if isinstance(turn, str):
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": turn}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return
        for name, tool_input in turn:
            self._ids += 1
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"t{self._ids}", "name": name}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(tool_input)}}}}
            yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}


EXECUTED: list[tuple[str, dict]] = []


@tool
def get_top_items(branch_id: int, start_date: str, end_date: str, top_n: int = 5) -> dict:
    """Best-selling items at a branch."""
    EXECUTED.append(("get_top_items", {"branch_id": branch_id}))
    return {"rows": [{"item_name": "Spicy Chicken Burger", "qty_sold": 1200}]}


@tool
def get_current_stock(branch_id: int, item_id: int | None = None) -> dict:
    """Live stock for a branch."""
    EXECUTED.append(("get_current_stock", {"branch_id": branch_id}))
    return {"rows": [{"item_name": "Spicy Chicken Burger", "on_hand": 14, "is_low_stock": True}]}


@tool
def issue_refund(branch_id: int, order_id: int, reason: str, amount: float | None = None) -> dict:
    """Refund an order. Changes data."""
    EXECUTED.append(("issue_refund", {"branch_id": branch_id, "order_id": order_id}))
    return {"refund_id": "R-1", "status": "refunded"}


@tool
def request_stock_transfer(from_branch_id: int, to_branch_id: int, item_id: int, qty: int) -> dict:
    """Move stock between branches. Changes data."""
    EXECUTED.append(("request_stock_transfer", {"from_branch_id": from_branch_id}))
    return {"transfer_id": "T-1", "status": "requested"}


@tool(name="rst-ops___issue_refund")
def gateway_issue_refund(branch_id: int, order_id: int, reason: str, amount: float | None = None) -> dict:
    """issue_refund as AgentCore Gateway names it (MCP server target). Changes data."""
    EXECUTED.append(("rst-ops___issue_refund", {"branch_id": branch_id, "order_id": order_id}))
    return {"refund_id": "R-2", "status": "refunded"}


@tool(name="rst-api___issueRefund")
def gateway_openapi_refund(branchId: int, orderId: int, reason: str) -> dict:
    """The refund operation as Gateway exposes it from the OpenAPI contract. Changes data."""
    EXECUTED.append(("rst-api___issueRefund", {"branchId": branchId, "orderId": orderId}))
    return {"refundId": "R-3", "status": "refunded"}


ALL_TOOLS = [get_top_items, get_current_stock, issue_refund, request_stock_transfer]
GATEWAY_TOOLS = [gateway_issue_refund, gateway_openapi_refund]


def tool_results(messages: list[dict]) -> list[dict]:
    return [c["toolResult"] for m in messages for c in m.get("content", []) if "toolResult" in c]
