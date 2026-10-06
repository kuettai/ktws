"""OAuth resource-server support (pre-built).

The MCP server never logs users in. It validates access tokens issued by an OIDC provider
(Cognito in the workshop) and exposes the caller's identity to tools via current_caller().

Auth is enabled when OIDC_ISSUER is set. Swapping IdP (Entra, Keycloak, Okta) is config only.

Environment:
    OIDC_ISSUER             e.g. https://cognito-idp.<region>.amazonaws.com/<user_pool_id>
    OIDC_JWKS_URL           optional, default <issuer>/.well-known/jwks.json
    OIDC_ALLOWED_AUDIENCES  comma-separated client IDs (Cognito) or audiences (other IdPs)
    OIDC_REQUIRED_SCOPES    comma-separated, default rst-mcp/read
    MCP_PUBLIC_URL          public URL of this server, e.g. https://xxxx.cloudfront.net/mcp
    CLAIM_ROLE              claim holding the caller role, default role
    CLAIM_BRANCH_ID         claim holding the caller branch, default branch_id
    SERVICE_ROLE            role for service-to-service tokens (no user), default hq
    LOCAL_ROLE              role when auth is disabled (stdio / local), default hq
    LOCAL_BRANCH_ID         branch when auth is disabled, optional
"""
import logging
import os
from dataclasses import dataclass

import anyio.to_thread
import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings

log = logging.getLogger(__name__)

ROLES = ("hq", "manager", "staff")


def _csv(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


class JwtTokenVerifier:
    """Validates RS256 JWT access tokens against the IdP's JWKS."""

    def __init__(self, issuer: str, jwks_url: str, allowed_audiences: list[str]):
        self.issuer = issuer
        self.allowed_audiences = set(allowed_audiences)
        self.jwks = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def decode(self, token: str) -> dict:
        key = self.jwks.get_signing_key_from_jwt(token).key
        # Cognito access tokens carry client_id instead of aud, so audience is checked below.
        claims = jwt.decode(
            token, key, algorithms=["RS256"], issuer=self.issuer,
            options={"verify_aud": False, "require": ["exp", "iss"]},
        )
        if claims.get("token_use", "access") != "access":
            raise jwt.InvalidTokenError("not an access token")
        aud = claims.get("aud", [])
        audiences = {claims.get("client_id")} | (set(aud) if isinstance(aud, list) else {aud})
        if self.allowed_audiences and not audiences & self.allowed_audiences:
            raise jwt.InvalidTokenError("token not issued for this server")
        return claims

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await anyio.to_thread.run_sync(self.decode, token)
        except Exception as e:  # any failure = 401, never leak details to the caller
            log.info("Rejected token: %s", e)
            return None
        scopes = (claims.get("scope") or claims.get("scp") or "").split()
        return AccessToken(
            token=token,
            client_id=claims.get("client_id") or claims.get("azp") or "",
            scopes=scopes,
            expires_at=claims.get("exp"),
            subject=claims.get("sub"),
            claims=claims,
        )


def build_auth() -> tuple[AuthSettings | None, JwtTokenVerifier | None]:
    issuer = os.environ.get("OIDC_ISSUER")
    if not issuer:
        log.warning("OIDC_ISSUER not set: authentication DISABLED. Local development only.")
        return None, None
    settings = AuthSettings(
        issuer_url=issuer,
        resource_server_url=os.environ["MCP_PUBLIC_URL"],
        required_scopes=_csv("OIDC_REQUIRED_SCOPES", "rst-mcp/read"),
        validate_token_resource=False,  # audience checked in JwtTokenVerifier
    )
    verifier = JwtTokenVerifier(
        issuer=issuer,
        jwks_url=os.environ.get("OIDC_JWKS_URL", f"{issuer.rstrip('/')}/.well-known/jwks.json"),
        allowed_audiences=_csv("OIDC_ALLOWED_AUDIENCES"),
    )
    return settings, verifier


@dataclass(frozen=True)
class Caller:
    role: str                 # hq | manager | staff
    branch_id: int | None     # None = not linked to a branch
    subject: str | None       # user or client identifier, for logging
    is_service: bool          # service-to-service token (no human)


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def current_caller() -> Caller:
    """Identity of whoever is calling the current tool."""
    token = get_access_token()
    if token is None:
        return Caller(
            role=os.environ.get("LOCAL_ROLE", "hq"),
            branch_id=_to_int(os.environ.get("LOCAL_BRANCH_ID")),
            subject="local",
            is_service=False,
        )
    claims = token.claims or {}
    role = claims.get(os.environ.get("CLAIM_ROLE", "role"))
    branch_id = _to_int(claims.get(os.environ.get("CLAIM_BRANCH_ID", "branch_id")))
    # Cognito client_credentials tokens have sub == client_id and no username.
    is_service = role is None and "username" not in claims and claims.get("sub") == claims.get("client_id")
    if is_service:
        role = os.environ.get("SERVICE_ROLE", "hq")
    if role not in ROLES:
        role = "staff"  # least privilege for unknown or missing roles
    return Caller(role=role, branch_id=branch_id, subject=token.subject, is_service=is_service)
