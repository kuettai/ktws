#!/usr/bin/env python3
"""Sign in as each workshop test user and save their access tokens, one file per user.

    python scripts/get_test_tokens.py <cognito-domain> <kiro-user-client-id> [user ...]
    python scripts/get_test_tokens.py https://rst-mcp-123456789012.auth.us-east-1.amazoncognito.com 5fmf... staff_branch_12
    (on Windows: py scripts\\get_test_tokens.py ...)

Default users: manager_branch_12 staff_branch_12 analyst_hq
Tokens go to /tmp/rst-token-<user> on macOS and Linux, %TEMP%\\rst-token-<user> on Windows
(readable only by you where the OS supports it), and expire after 1 hour.
Each token is checked: if you signed in as the wrong user, you are asked to try again.
The scope comes from RST_MCP_SCOPE, as in get_token.py.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_USERS = ["manager_branch_12", "staff_branch_12", "analyst_hq"]


def token_dir() -> Path:
    return Path(tempfile.gettempdir()) if os.name == "nt" else Path("/tmp")


def token_file(user: str) -> Path:
    return token_dir() / f"rst-token-{user}"


def token_user(token: str) -> str:
    """The username inside an access token (claims only), or "" if it can't be read."""
    try:
        body = token.strip().split(".")[1]
        body += "=" * (-len(body) % 4)
        return json.loads(base64.urlsafe_b64decode(body)).get("username", "")
    except Exception:
        return ""


def write_private(path: Path, text: str) -> None:
    """Write a file only the current user can read (0600 on macOS/Linux)."""
    if path.exists():
        path.unlink()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def fetch_token(domain: str, client_id: str) -> str:
    """Run get_token.py (browser sign-in) with this Python and return the printed token."""
    out = subprocess.run([sys.executable, str(HERE / "get_token.py"), "--domain", domain, "--client-id", client_id],
                         stdout=subprocess.PIPE, text=True)
    return out.stdout.strip()


def sign_in_all(domain: str, client_id: str, users: list, fetch=fetch_token, ask=input) -> None:
    for user in users:
        path = token_file(user)
        while True:
            print()
            ask(f"Next: sign in as '{user}'. Press Enter to open the login page... ")
            token = fetch(domain, client_id)
            write_private(path, token + "\n" if token else "")
            got = token_user(token)
            if got == user:
                print(f"OK: token for {user} saved to {path}")
                break
            print(f"That sign-in was for '{got or 'nobody'}', not '{user}'. Let's try again.")
    print()
    print("All done: " + " ".join(users))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Sign in as each test user and save their access tokens.")
    p.add_argument("domain", help="Cognito domain, e.g. https://<prefix>.auth.<region>.amazoncognito.com")
    p.add_argument("client_id", help="kiro-user app client ID")
    p.add_argument("users", nargs="*", help="test users (default: " + " ".join(DEFAULT_USERS) + ")")
    args = p.parse_args(argv)
    sign_in_all(args.domain, args.client_id, args.users or DEFAULT_USERS)


if __name__ == "__main__":
    main()
