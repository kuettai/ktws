"""Cognito pre token generation trigger (V2): copy user attributes into the ACCESS token.

The MCP server reads `role` and `branch_id` from the access token to scope data.
Cognito only puts custom attributes in the ID token by default, and MCP clients send the
access token, so this trigger is required for branch scoping.
"""


def handler(event, context):
    attrs = event["request"].get("userAttributes", {})
    claims = {}
    if "custom:role" in attrs:
        claims["role"] = attrs["custom:role"]
    if "custom:branch_id" in attrs:
        claims["branch_id"] = attrs["custom:branch_id"]
    event["response"]["claimsAndScopeOverrideDetails"] = {
        "accessTokenGeneration": {"claimsToAddOrOverride": claims},
        "idTokenGeneration": {"claimsToAddOrOverride": claims},
    }
    return event
