import pytest
from fastapi.testclient import TestClient

from app import data
from app.main import app

KEY = {"X-API-Key": "test-key"}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("MOCK_API_KEY", "test-key")
    monkeypatch.setenv("MOCK_NOW", "2026-10-01T14:30:00")
    data.REFUNDS.clear()
    data.TRANSFERS.clear()


client = TestClient(app)


def test_requires_api_key():
    assert client.get("/branches").status_code == 401
    assert client.get("/branches", headers={"X-API-Key": "wrong"}).json()["code"] == "UNAUTHORIZED"
    assert client.get("/health").status_code == 200


def test_branches_match_reference():
    branches = client.get("/branches", headers=KEY).json()
    assert len(branches) == 30
    assert branches[11]["branchId"] == 12
    assert client.get("/branches?region=Capital", headers=KEY).json()
    assert client.get("/branches/999", headers=KEY).json() == {"code": "BRANCH_NOT_FOUND", "message": "Branch 999 not found"}


def test_orders_only_up_to_now_and_deterministic():
    orders = client.get("/pos/12/orders?limit=100", headers=KEY).json()
    assert orders and all(o["createdAt"] <= "2026-10-01T14:30:00+00:00" for o in orders)
    assert orders == client.get("/pos/12/orders?limit=100", headers=KEY).json()
    detail = client.get(f"/pos/12/orders/{orders[0]['orderId']}", headers=KEY).json()
    assert detail["lines"]


def test_branch_12_low_on_chicken():
    low = client.get("/inventory/12/stock?lowStockOnly=true", headers=KEY).json()
    assert {1, 2} <= {s["itemId"] for s in low}


def test_refund_once_then_conflict():
    completed = client.get("/pos/12/orders?status=completed", headers=KEY).json()[0]
    url = f"/pos/12/orders/{completed['orderId']}/refund"
    first = client.post(url, json={"reason": "cold food"}, headers=KEY)
    assert first.status_code == 200 and first.json()["amount"] == completed["totalAmount"]
    assert client.post(url, json={"reason": "again"}, headers=KEY).status_code == 409


def test_transfer_moves_stock():
    before = client.get("/inventory/12/stock/1", headers=KEY).json()["onHand"]
    r = client.post("/inventory/transfers", json={"fromBranchId": 1, "toBranchId": 12, "itemId": 1, "qty": 5}, headers=KEY)
    assert r.status_code == 201
    assert client.get("/inventory/12/stock/1", headers=KEY).json()["onHand"] == before + 5
    too_many = client.post("/inventory/transfers", json={"fromBranchId": 1, "toBranchId": 12, "itemId": 1, "qty": 500}, headers=KEY)
    assert too_many.status_code == 409


def test_today_sales():
    s = client.get("/sales/12/today", headers=KEY).json()
    assert s["businessDate"] == "2026-10-01" and s["orderCount"] > 0 and s["revenue"] > 0


def test_ops_prefix_reaches_the_same_api():
    """CloudFront sends https://<cdn>/ops/... here (Day 2): same routes, same API key check."""
    assert client.get("/ops/branches", headers=KEY).status_code == 200
    assert client.get("/ops/branches").status_code == 401
