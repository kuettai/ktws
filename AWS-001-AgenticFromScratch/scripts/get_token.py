#!/usr/bin/env python3
"""Get an access token from Cognito (or any OAuth 2.0 IdP) for calling the MCP server.

User login (authorization code + PKCE, opens a browser):
    export RST_MCP_TOKEN=$(python get_token.py --domain https://<prefix>.auth.<region>.amazoncognito.com \
        --client-id <kiro-user client id>)

Service-to-service (client credentials):
    export RST_MCP_TOKEN=$(python get_token.py --domain ... --client-id <quick-s2s id> \
        --client-secret <secret> --client-credentials --scope rst-mcp/read)

Only the token is printed to stdout. Tokens expire after 1 hour; run again to refresh.
Add --decode to print the token's claims instead (for debugging, Module 06).
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def token_request(domain: str, form: dict, client_id: str, client_secret: str | None) -> dict:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if client_secret:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    else:
        form["client_id"] = client_id
    req = urllib.request.Request(f"{domain}/oauth2/token", data=urllib.parse.urlencode(form).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"Token request failed: {e.code} {e.read().decode()}")


def login(domain: str, client_id: str, client_secret: str | None, scope: str) -> dict:
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(16)
    result: dict = {}
    done = threading.Event()

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = dict(urllib.parse.parse_qsl(parsed.query))
            if parsed.path != "/callback" or not ("code" in query or "error" in query):
                self.send_response(404)  # e.g. the browser asking for /favicon.ico
                self.end_headers()
                return
            ok = query.get("state") == state and "code" in query
            result.update(query if ok else {"error": query.get("error", "state mismatch")})
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h3>Signed in. You can close this tab.</h3>" if ok else b"<h3>Sign-in failed.</h3>")
            done.set()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Callback)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"{domain}/oauth2/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT_URI, "scope": scope,
        "state": state, "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        # Always show the login page, so you can switch test users (manager -> staff -> HQ)
        # instead of being signed in again as whoever signed in last.
        "prompt": "login",
    })
    print(f"Opening browser for sign-in:\n  {url}", file=sys.stderr)
    webbrowser.open(url)
    if not done.wait(timeout=300):
        sys.exit("Timed out waiting for sign-in")
    server.shutdown()
    if "error" in result:
        sys.exit(f"Sign-in failed: {result['error']}")
    return token_request(domain, {
        "grant_type": "authorization_code", "code": result["code"],
        "redirect_uri": REDIRECT_URI, "code_verifier": verifier,
    }, client_id, client_secret)


def decode(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--domain", required=True, help="IdP base URL, e.g. https://<prefix>.auth.<region>.amazoncognito.com")
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret")
    # With -c mcpResourceUrl the scope is "<McpUrl>/read" (RstAuthStack output ReadScope).
    p.add_argument("--scope", default=os.environ.get("RST_MCP_SCOPE", "openid rst-mcp/read"))
    p.add_argument("--client-credentials", action="store_true", help="Service-to-service, no browser")
    p.add_argument("--decode", action="store_true", help="Print claims instead of the raw token")
    args = p.parse_args()
    domain = args.domain.rstrip("/")

    if args.client_credentials:
        if not args.client_secret:
            sys.exit("--client-credentials needs --client-secret")
        tokens = token_request(domain, {"grant_type": "client_credentials", "scope": args.scope},
                               args.client_id, args.client_secret)
    else:
        tokens = login(domain, args.client_id, args.client_secret, args.scope)

    access_token = tokens["access_token"]
    print(json.dumps(decode(access_token), indent=2) if args.decode else access_token)


if __name__ == "__main__":
    main()
