"""Tests for create_test_users.py and get_test_tokens.py. No AWS calls, no browser."""
import base64
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import create_test_users as ctu  # noqa: E402
import get_test_tokens as gtt  # noqa: E402


class FakeRun:
    """Records AWS CLI calls; admin-create-user fails for usernames in `existing`."""

    def __init__(self, existing=()):
        self.calls = []
        self.existing = set(existing)

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        failed = "admin-create-user" in argv and argv[argv.index("--username") + 1] in self.existing
        return subprocess.CompletedProcess(argv, 1 if failed else 0)


BASE = ["aws", "--region", "us-east-1"]


def test_creates_each_user_with_exact_cli_arguments(capsys):
    run = FakeRun()
    for username, role, branch in ctu.USERS:
        ctu.create(BASE, "pool-1", "pw-123456789012", username, role, branch, run=run)
    assert run.calls[0] == BASE + ["cognito-idp", "admin-create-user", "--user-pool-id", "pool-1",
                                   "--username", "analyst_hq", "--user-attributes", "Name=custom:role,Value=hq",
                                   "--message-action", "SUPPRESS"]
    assert run.calls[1] == BASE + ["cognito-idp", "admin-set-user-password", "--user-pool-id", "pool-1",
                                   "--username", "analyst_hq", "--password", "pw-123456789012", "--permanent"]
    assert run.calls[2][run.calls[2].index("--user-attributes") + 1:][:2] == [
        "Name=custom:role,Value=manager", "Name=custom:branch_id,Value=12"]
    assert len(run.calls) == 8
    out = capsys.readouterr().out
    assert "  analyst_hq  role=hq  branch=-" in out and "  manager_branch_5  role=manager  branch=5" in out


def test_existing_user_gets_attributes_updated():
    run = FakeRun(existing={"staff_branch_12"})
    ctu.create(BASE, "pool-1", "pw-123456789012", "staff_branch_12", "staff", "12", run=run)
    assert [c[len(BASE) + 1] for c in run.calls] == ["admin-create-user", "admin-update-user-attributes", "admin-set-user-password"]
    assert run.calls[1][-2:] == ["Name=custom:role,Value=staff", "Name=custom:branch_id,Value=12"]


def test_region_and_profile_passed_to_aws(monkeypatch):
    monkeypatch.setattr(ctu.shutil, "which", lambda name: "/usr/bin/aws")
    assert ctu.aws_base("us-east-1", "sandbox") == ["/usr/bin/aws", "--region", "us-east-1", "--profile", "sandbox"]


def jwt(username):
    body = base64.urlsafe_b64encode(json.dumps({"username": username}).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


def test_token_user_reads_username_and_handles_garbage():
    assert gtt.token_user(jwt("manager_branch_12")) == "manager_branch_12"
    assert gtt.token_user("") == "" and gtt.token_user("not-a-token") == ""


def test_retries_until_the_right_user_signs_in(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gtt, "token_dir", lambda: tmp_path)
    tokens = iter([jwt("manager_branch_12"), jwt("staff_branch_12"), "", jwt("analyst_hq")])
    prompts = []
    gtt.sign_in_all("https://d", "client", ["staff_branch_12", "analyst_hq"],
                    fetch=lambda d, c: next(tokens), ask=prompts.append)
    out = capsys.readouterr().out
    assert "That sign-in was for 'manager_branch_12', not 'staff_branch_12'." in out
    assert "That sign-in was for 'nobody', not 'analyst_hq'." in out
    assert len(prompts) == 4
    assert gtt.token_user((tmp_path / "rst-token-staff_branch_12").read_text()) == "staff_branch_12"
    assert gtt.token_user((tmp_path / "rst-token-analyst_hq").read_text()) == "analyst_hq"
    if sys.platform != "win32":
        assert (tmp_path / "rst-token-analyst_hq").stat().st_mode & 0o777 == 0o600
    assert out.strip().endswith("All done: staff_branch_12 analyst_hq")


def test_token_paths_per_os(monkeypatch):
    monkeypatch.setattr(gtt.os, "name", "posix")
    assert gtt.token_file("x") == Path("/tmp/rst-token-x")
