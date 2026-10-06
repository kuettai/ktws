"""End-to-end auth over Streamable HTTP with real signed JWTs (Cognito-shaped)."""
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from starlette.testclient import TestClient

import tools.hello
import tools.redshift_tools as rt
from lib.auth import JwtTokenVerifier

ISSUER = "https://cognito-idp.ap-southeast-1.amazonaws.com/ap-southeast-1_TEST"
CLIENT_ID = "quick-user-client"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


class FakeSigningKey:
    key = KEY.public_key()


def token(key=KEY, **overrides) -> str:
    claims = {
        "iss": ISSUER, "sub": "user-123", "username": "manager_branch_12", "client_id": CLIENT_ID,
        "token_use": "access", "scope": "openid rst-mcp/read", "exp": int(time.time()) + 300,
        "role": "manager", "branch_id": "12",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture
def client(monkeypatch):
    verifier = JwtTokenVerifier(ISSUER, f"{ISSUER}/.well-known/jwks.json", [CLIENT_ID])
    monkeypatch.setattr(verifier.jwks, "get_signing_key_from_jwt", lambda t: FakeSigningKey)
    srv = MCPServer("rst-test", token_verifier=verifier, auth=AuthSettings(
        issuer_url=ISSUER, resource_server_url="https://mcp.example.com/mcp",
        required_scopes=["rst-mcp/read"], validate_token_resource=False,
    ))
    srv.tool()(tools.hello.who_am_i)
    srv.tool()(rt.get_daily_branch_sales)
    app = srv.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")
    with TestClient(app, base_url="https://mcp.example.com") as c:
        yield c


def rpc(client, method, params=None, bearer=None):
    headers = dict(MCP_HEADERS)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp", json=body, headers=headers)


def call(client, name, args, bearer):
    initialize(client, bearer)
    r = rpc(client, "tools/call", {"name": name, "arguments": args}, bearer)
    assert r.status_code == 200, r.text
    return json.loads(r.json()["result"]["content"][0]["text"])


def initialize(client, bearer):
    r = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "test", "version": "1"}}, bearer)
    assert r.status_code == 200, r.text


def test_no_token_401_points_to_metadata(client):
    r = rpc(client, "tools/list")
    assert r.status_code == 401
    assert "resource_metadata=" in r.headers["www-authenticate"]


def test_protected_resource_metadata(client):
    r = client.get("/.well-known/oauth-protected-resource/mcp")
    assert r.status_code == 200
    assert r.json()["authorization_servers"] == [ISSUER]


@pytest.mark.parametrize("bad", [
    token(key=OTHER_KEY),                    # wrong signature (fake JWKS still returns KEY)
    token(exp=int(time.time()) - 10),        # expired
    token(iss="https://evil.example.com"),   # wrong issuer
    token(client_id="some-other-app"),       # issued to another app
    token(token_use="id"),                   # ID token, not access token
])
def test_bad_tokens_rejected(client, bad):
    assert rpc(client, "tools/list", bearer=bad).status_code == 401


def test_resource_bound_token_accepted(client):
    # Quick sends resource=<MCP URL>; Cognito then sets aud to that URL. client_id still identifies the app.
    bound = token(aud="https://mcp.example.com/mcp")
    assert rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "t", "version": "1"}}, bound).status_code == 200


def test_missing_scope_forbidden(client):
    assert rpc(client, "tools/list", bearer=token(scope="openid")).status_code == 403


def test_identity_reaches_tools(client):
    result = call(client, "who_am_i", {}, token())
    assert result == {"role": "manager", "branch_id": 12, "is_service": False}


def test_service_token_gets_service_role(client):
    s2s = token(sub=CLIENT_ID, username=None, role=None, branch_id=None, scope="rst-mcp/read")
    result = call(client, "who_am_i", {}, s2s)
    assert result == {"role": "hq", "branch_id": None, "is_service": True}


def test_manager_scoped_over_http(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(rt, "run_query", lambda sql, params: seen.update(params) or [])
    result = call(client, "get_daily_branch_sales",
                  {"branch_id": 5, "start_date": "2026-09-01", "end_date": "2026-09-07"}, token())
    assert seen["branch_id"] == 12
    assert "instead of branch 5" in result["note"]
