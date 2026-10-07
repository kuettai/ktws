"""AgentCore Gateway REQUEST interceptor: pass the caller's sign-in token on to the target.

Without this, the Gateway calls the MCP server on AgentCore Runtime with its own service token,
so the server can't tell which user is asking and branch scoping stops working. The Gateway has
already checked this token (inbound authorizer) before the interceptor runs.
"""


def handler(event, context):
    request = event.get("mcp", {}).get("gatewayRequest", {})
    headers = request.get("headers") or {}
    auth = next((v for k, v in headers.items() if k.lower() == "authorization"), None)
    transformed = {"body": request.get("body")}
    if auth:
        transformed["headers"] = {"Authorization": auth}
    return {"interceptorOutputVersion": "1.0", "mcp": {"transformedGatewayRequest": transformed}}
