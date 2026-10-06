#!/usr/bin/env python3
"""Create the workshop test users in the Cognito user pool.

    python scripts/create_test_users.py <UserPoolId> [--region R] [--profile P]
    (on Windows: py scripts\\create_test_users.py <UserPoolId>)

Asks once for a shared password (12+ characters) for all test users. When input is piped in
(`... < password-file`), the password is read from that instead.
Works on Windows, macOS and Linux; needs the AWS CLI v2 on the PATH.
"""
import argparse
import getpass
import shutil
import subprocess
import sys

# username, role, branch_id ("" = no branch restriction)
USERS = [
    ("analyst_hq", "hq", ""),
    ("manager_branch_12", "manager", "12"),
    ("staff_branch_12", "staff", "12"),
    ("manager_branch_5", "manager", "5"),
]


def read_password() -> str:
    if sys.stdin.isatty():
        return getpass.getpass("Password for all test users: ")
    print("Password for all test users: ")
    return sys.stdin.readline().rstrip("\r\n")


def aws_base(region, profile):
    exe = shutil.which("aws")
    if not exe:
        sys.exit("AWS CLI not found on PATH. Install AWS CLI v2 first.")
    base = [exe]
    if region:
        base += ["--region", region]
    if profile:
        base += ["--profile", profile]
    return base


def attributes(role: str, branch: str) -> list:
    attrs = [f"Name=custom:role,Value={role}"]
    if branch:
        attrs.append(f"Name=custom:branch_id,Value={branch}")
    return attrs


def create(base, pool_id: str, password: str, username: str, role: str, branch: str, run=subprocess.run) -> None:
    attrs = attributes(role, branch)
    created = run(base + ["cognito-idp", "admin-create-user", "--user-pool-id", pool_id, "--username", username,
                          "--user-attributes", *attrs, "--message-action", "SUPPRESS"],
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if created.returncode != 0:  # user exists already: just update the attributes
        run(base + ["cognito-idp", "admin-update-user-attributes", "--user-pool-id", pool_id, "--username", username,
                    "--user-attributes", *attrs], check=True)
    run(base + ["cognito-idp", "admin-set-user-password", "--user-pool-id", pool_id, "--username", username,
                "--password", password, "--permanent"], check=True)
    print(f"  {username}  role={role}  branch={branch or '-'}")


def main(argv=None, run=subprocess.run) -> None:
    p = argparse.ArgumentParser(description="Create the workshop test users in a Cognito user pool.")
    p.add_argument("user_pool_id", help="RstAuthStack output UserPoolId, e.g. us-east-1_AbCdEf123")
    p.add_argument("--region", help="AWS region (default: AWS_REGION or your profile's region)")
    p.add_argument("--profile", help="AWS CLI profile (default: AWS_PROFILE or default credentials)")
    args = p.parse_args(argv)
    base = aws_base(args.region, args.profile)
    password = read_password()
    if len(password) < 12:
        sys.exit("The password must be at least 12 characters.")
    print(f"Creating users in {args.user_pool_id}")
    for username, role, branch in USERS:
        try:
            create(base, args.user_pool_id, password, username, role, branch, run=run)
        except subprocess.CalledProcessError as e:
            sys.exit(f"Failed for {username} (exit {e.returncode}). Check the pool ID, region and credentials.")


if __name__ == "__main__":
    main()
