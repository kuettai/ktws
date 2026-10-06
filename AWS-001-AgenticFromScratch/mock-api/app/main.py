"""Mock Restaurant Operations API. Implements ../openapi.yaml (the contract is the source of truth).

Run:  MOCK_API_KEY=local-dev-key uv run uvicorn app.main:app --port 8080
"""
import os
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import data

app = FastAPI(title="Restaurant Operations API (mock)", version="1.0.0")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ.get("MOCK_API_KEY", "local-dev-key")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise ApiError(401, "UNAUTHORIZED", "Missing or invalid X-API-Key header")


def branch_or_404(branch_id: int) -> int:
    if branch_id not in data.BRANCHES:
        raise ApiError(404, "BRANCH_NOT_FOUND", f"Branch {branch_id} not found")
    return branch_id


def item_or_404(item_id: int) -> int:
    if item_id not in data.MENU:
        raise ApiError(404, "ITEM_NOT_FOUND", f"Item {item_id} not found")
    return item_id


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}


api = [Depends(require_api_key)]


# ---- Reference ----------------------------------------------------------------------------

@app.get("/branches", dependencies=api, operation_id="listBranches")
def list_branches(region: str | None = None) -> list[dict]:
    return [
        {k: b[k] for k in ("branchId", "name", "region", "format")}
        for b in data.BRANCHES.values()
        if region is None or b["region"].lower() == region.lower()
    ]


@app.get("/branches/{branchId}", dependencies=api, operation_id="getBranch")
def get_branch(branchId: int) -> dict:
    return data.branch_detail(branch_or_404(branchId))


@app.get("/menu/items", dependencies=api, operation_id="listMenuItems")
def list_menu_items(category: Literal["chicken", "burger", "sides", "drinks", "dessert"] | None = None) -> list[dict]:
    return [
        {"itemId": m["itemId"], "name": m["name"], "category": m["category"], "price": m["price"], "available": True}
        for m in data.MENU.values()
        if category is None or m["category"] == category
    ]


# ---- POS -----------------------------------------------------------------------------------

def _summary(order: dict) -> dict:
    return {k: v for k, v in order.items() if k != "lines"}


@app.get("/pos/{branchId}/orders", dependencies=api, operation_id="listOrders")
def list_orders(
    branchId: int,
    status: Literal["open", "preparing", "ready", "completed", "cancelled", "refunded"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    orders = data.orders_today(branch_or_404(branchId))
    if status:
        orders = [o for o in orders if o["status"] == status]
    return [_summary(o) for o in reversed(orders)][:limit]  # newest first


@app.get("/pos/{branchId}/orders/{orderId}", dependencies=api, operation_id="getOrder")
def get_order(branchId: int, orderId: int) -> dict:
    order = data.find_order(branch_or_404(branchId), orderId)
    if order is None:
        raise ApiError(404, "ORDER_NOT_FOUND", f"Order {orderId} not found at branch {branchId} today")
    return order


class RefundRequest(BaseModel):
    reason: str = Field(max_length=200)
    amount: float | None = None


@app.post("/pos/{branchId}/orders/{orderId}/refund", dependencies=api, operation_id="issueRefund")
def issue_refund(branchId: int, orderId: int, body: RefundRequest) -> dict:
    try:
        return data.issue_refund(branch_or_404(branchId), orderId, body.reason, body.amount)
    except KeyError:
        raise ApiError(404, "ORDER_NOT_FOUND", f"Order {orderId} not found at branch {branchId} today") from None
    except data.Conflict as e:
        raise ApiError(409, "NOT_REFUNDABLE", str(e)) from None


# ---- Inventory -----------------------------------------------------------------------------

@app.get("/inventory/{branchId}/stock", dependencies=api, operation_id="getStockLevels")
def get_stock_levels(branchId: int, lowStockOnly: bool = False) -> list[dict]:
    levels = data.stock_levels(branch_or_404(branchId))
    return [s for s in levels if s["isLowStock"]] if lowStockOnly else levels


@app.get("/inventory/{branchId}/stock/{itemId}", dependencies=api, operation_id="getItemStock")
def get_item_stock(branchId: int, itemId: int) -> dict:
    item_or_404(itemId)
    return next(s for s in data.stock_levels(branch_or_404(branchId)) if s["itemId"] == itemId)


class TransferRequest(BaseModel):
    fromBranchId: int
    toBranchId: int
    itemId: int
    qty: int = Field(ge=1, le=500)


@app.post("/inventory/transfers", dependencies=api, operation_id="requestStockTransfer", status_code=201)
def request_stock_transfer(body: TransferRequest) -> dict:
    branch_or_404(body.fromBranchId)
    branch_or_404(body.toBranchId)
    item_or_404(body.itemId)
    try:
        return data.request_transfer(body.fromBranchId, body.toBranchId, body.itemId, body.qty)
    except data.Conflict as e:
        raise ApiError(409, "TRANSFER_REJECTED", str(e)) from None


# ---- Sales ---------------------------------------------------------------------------------

@app.get("/sales/{branchId}/today", dependencies=api, operation_id="getTodaySales")
def get_today_sales(branchId: int) -> dict:
    return data.sales_today(branch_or_404(branchId))
