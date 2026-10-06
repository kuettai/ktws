#!/usr/bin/env python3
"""MCP workshop - pre-event check for participant laptops and networks.

Checks that a laptop has the software, network access and local ports the workshop needs.
It only reads: it installs nothing, changes no settings and sends nothing anywhere.

    python3 rst_preflight.py                  # software, network, ports   (about 1 minute)
    python3 rst_preflight.py --deep           # + test package downloads (pip, npm, Docker image)
    python3 rst_preflight.py --aws --profile <name>
                                              # + AWS service access in a test account (read-only)

On Windows use `py rst_preflight.py` if `python3` is not found.
Needs Python 3.8 or newer to run (the workshop itself needs 3.12+, which this script checks).

At the end it writes rst-preflight-report-<date>.txt next to this script. At an instructor-led
event, send that file to the instructor. It contains no passwords, keys or tokens. With --aws it includes the
AWS account ID and role name of the profile you used.
"""
import argparse
import datetime
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"
results = []  # (section, status, check, detail)


def record(section, status, check, detail=""):
    results.append((section, status, check, detail))
    print("  [{:<4}] {:<44} {}".format(status, check, detail))


def run(cmd, timeout=60):
    """Run a command; return (exit_code, combined_output). exit_code None if not runnable."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None, "not found on PATH"
    try:
        p = subprocess.run([exe] + cmd[1:], capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return None, "timed out after {}s".format(timeout)
    except OSError as e:
        return None, str(e)


def version_tuple(text):
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


# ---- 1. Software -----------------------------------------------------------------------------

def check_software():
    print("\n1. Software")
    s = "software"

    # Python 3.12+ (the interpreter running this script, then python3 / py on PATH)
    candidates = [sys.executable] + [c for c in ("python3", "python", "py") if shutil.which(c)]
    best = None
    for c in candidates:
        code, out = run([c, "--version"]) if c != sys.executable else (0, platform.python_version())
        v = version_tuple(out) if code == 0 else None
        if v and (best is None or v > best[0]):
            best = (v, c)
    if best and best[0] >= (3, 12):
        record(s, PASS, "Python 3.12+", "{} ({})".format(".".join(map(str, best[0])), best[1]))
    else:
        found = ".".join(map(str, best[0])) if best else "none"
        record(s, FAIL, "Python 3.12+", "found {} - install Python 3.12 or newer".format(found))

    def tool(name, cmd, minimum=None, required=True, hint=""):
        code, out = run(cmd)
        if code != 0:
            record(s, FAIL if required else WARN, name, "not found or not working. " + hint)
            return None
        v = version_tuple(out)
        if minimum and (not v or v < minimum):
            record(s, FAIL, name, "found {}, need {}+. {}".format(
                ".".join(map(str, v)) if v else out[:40], ".".join(map(str, minimum)), hint))
            return v
        record(s, PASS, name, out.splitlines()[0][:60])
        return v

    tool("uv (Python package manager)", ["uv", "--version"], hint="https://docs.astral.sh/uv/")
    tool("Node.js 22.19+", ["node", "--version"], minimum=(22, 19), hint="MCP Inspector needs 22.19 or newer: https://nodejs.org")
    tool("npm / npx", ["npx", "--version"], hint="comes with Node.js")
    tool("Git", ["git", "--version"])
    aws_v = tool("AWS CLI v2", ["aws", "--version"], minimum=(2, 0),
                 hint="https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")

    # Docker or Finch, and the engine must be running
    engine = None
    for name in ("docker", "finch"):
        if shutil.which(name):
            code, out = run([name, "info", "--format", "{{.ServerVersion}}"], timeout=30)
            if code == 0:
                engine = name
                record(s, PASS, "Docker or Finch (running)", "{} {}".format(name, out.splitlines()[0][:40]))
                break
            record(s, WARN, "{} engine".format(name), "installed but not running - start Docker Desktop / "
                   "`finch vm start`")
    if not engine and not any(r[2] == "docker engine" or r[2] == "finch engine" for r in results):
        record(s, FAIL, "Docker or Finch", "not found - needed from Day 1 afternoon")

    # Kiro
    kiro_paths = [
        "/Applications/Kiro.app",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Kiro\Kiro.exe"),
        os.path.expanduser("~/.local/share/kiro"),
    ]
    if shutil.which("kiro") or any(os.path.exists(p) for p in kiro_paths):
        record(s, PASS, "Kiro installed", "also open Kiro once and sign in")
    else:
        record(s, WARN, "Kiro installed", "not found in the usual places - install from https://kiro.dev "
               "(ignore if installed elsewhere)")
    return engine, aws_v


# ---- 2. Network ------------------------------------------------------------------------------

# (group, host, required). Any HTTP answer (even 403/404) means the network lets us through.
HOSTS = [
    ("Kiro", "app.kiro.dev", True),
    ("Kiro", "assets.app.kiro.dev", True),
    ("Kiro", "prod.us-east-1.auth.desktop.kiro.dev", True),
    ("Kiro", "runtime.us-east-1.kiro.dev", True),
    ("Kiro", "management.us-east-1.kiro.dev", True),
    ("Kiro", "q.us-east-1.amazonaws.com", True),
    ("Kiro", "prod.download.desktop.kiro.dev", False),
    ("Sign-in", "signin.aws", True),
    ("Sign-in", "signin.aws.amazon.com", True),
    ("Sign-in", "oidc.us-east-1.amazonaws.com", True),
    ("Sign-in", "portal.sso.us-east-1.amazonaws.com", True),
    ("Sign-in", "cognito-identity.us-east-1.amazonaws.com", False),
    ("Workshop Studio", "catalog.workshops.aws", True),
    ("Workshop Studio", "catalog.us-east-1.prod.workshops.aws", True),
    ("Workshop Studio", "static.us-east-1.prod.workshops.aws", True),
    ("AWS Console", "console.aws.amazon.com", True),
    ("AWS Console", "us-east-1.console.aws.amazon.com", True),
    ("Amazon Quick", "quicksight.aws.amazon.com", True),
    ("Amazon Quick", "us-east-1.quicksight.aws.amazon.com", True),
    ("AWS APIs", "sts.us-east-1.amazonaws.com", True),
    ("AWS APIs", "cloudformation.us-east-1.amazonaws.com", True),
    ("AWS APIs", "s3.us-east-1.amazonaws.com", True),
    ("AWS APIs", "api.ecr.us-east-1.amazonaws.com", True),
    ("AWS APIs", "ecs.us-east-1.amazonaws.com", True),
    ("AWS APIs", "logs.us-east-1.amazonaws.com", True),
    ("AWS APIs", "ssm.us-east-1.amazonaws.com", True),
    ("AWS APIs", "secretsmanager.us-east-1.amazonaws.com", True),
    ("AWS APIs", "lambda.us-east-1.amazonaws.com", True),
    ("AWS APIs", "iam.amazonaws.com", True),
    ("AWS APIs", "cognito-idp.us-east-1.amazonaws.com", True),
    ("AWS APIs", "redshift-serverless.us-east-1.amazonaws.com", True),
    ("AWS APIs", "redshift-data.us-east-1.amazonaws.com", True),
    ("AWS APIs", "bedrock.us-east-1.amazonaws.com", True),
    ("AWS APIs", "bedrock-runtime.us-east-1.amazonaws.com", True),
    ("AWS APIs", "bedrock-agentcore.us-east-1.amazonaws.com", True),
    ("AWS APIs", "bedrock-agentcore-control.us-east-1.amazonaws.com", True),
    ("Packages", "pypi.org", True),
    ("Packages", "files.pythonhosted.org", True),
    ("Packages", "registry.npmjs.org", True),
    ("Packages", "registry-1.docker.io", True),
    ("Packages", "auth.docker.io", True),
    ("Packages", "production.cloudflare.docker.com", True),
    ("Packages", "public.ecr.aws", True),
    ("Packages", "github.com", False),
    ("Packages", "raw.githubusercontent.com", False),
]

TRUSTED_ISSUERS = ("Amazon", "DigiCert", "Let's Encrypt", "GlobalSign", "Sectigo", "Google Trust",
                   "GoDaddy", "Starfield", "Cloudflare", "ISRG", "Microsoft", "Baltimore", "COMODO", "Entrust")


def probe(host, region):
    host = host.replace("us-east-1", region)
    url = "https://{}/".format(host)
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "rst-preflight/1.0"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return host, True, "HTTP {} ({:.1f}s)".format(r.status, time.time() - start)
    except urllib.error.HTTPError as e:  # the server answered: the network path works
        return host, True, "HTTP {} ({:.1f}s)".format(e.code, time.time() - start)
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            return host, False, "TLS certificate not trusted - HTTPS inspection by a proxy?"
        if isinstance(reason, socket.gaierror):
            return host, False, "DNS lookup failed - host blocked or no internet"
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return host, False, "timed out - blocked by firewall/proxy?"
        return host, False, str(reason)[:70]
    except (socket.timeout, TimeoutError):
        return host, False, "timed out - blocked by firewall/proxy?"
    except Exception as e:  # noqa: BLE001 - report anything else as a failure
        return host, False, "{}: {}".format(type(e).__name__, str(e)[:60])


def cert_issuer(host):
    """Issuer organisation of the certificate a host presents (direct connection only)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
        # Without verification Python does not decode the cert; look for the issuer O= in DER text.
        text = der.decode("latin-1")
        orgs = [m for m in TRUSTED_ISSUERS if m in text]
        return ", ".join(orgs) if orgs else "unrecognised issuer"
    except OSError as e:
        return "could not connect directly ({})".format(str(e)[:40])


def check_network(region):
    print("\n2. Network (HTTPS to each host the workshop uses)")
    s = "network"
    proxies = {k: v for k, v in os.environ.items() if k.lower() in ("https_proxy", "http_proxy", "no_proxy")}
    record(s, INFO, "Proxy settings in environment", ", ".join(sorted(proxies)) or "none")
    # AWS_REGION / AWS_DEFAULT_REGION override the profile's region, so a stale value sends
    # deployments to the wrong region.
    for var in ("AWS_REGION", "AWS_DEFAULT_REGION"):
        value = os.environ.get(var)
        if value and value != region:
            record(s, WARN, "{} environment variable".format(var), "set to {} but the workshop uses {} - "
                   "unset it or set it to {}".format(value, region, region))

    out = {}
    threads = []
    for group, host, required in HOSTS:
        t = threading.Thread(target=lambda h=host: out.__setitem__(h, probe(h, region)))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    for group, host, required in HOSTS:
        real_host, ok, detail = out[host]
        status = PASS if ok else (FAIL if required else WARN)
        record(s, status, "{}: {}".format(group, real_host), detail)

    issuer = cert_issuer("sts.{}.amazonaws.com".format(region))
    if "Amazon" in issuer:
        record(s, PASS, "No HTTPS inspection on AWS traffic", "certificate issued by " + issuer)
    else:
        record(s, WARN, "HTTPS inspection on AWS traffic?", "certificate issuer: {} - a proxy may be "
               "re-signing traffic; ask IT for an exception for *.amazonaws.com".format(issuer))


# ---- 3. Local ports --------------------------------------------------------------------------

PORTS = {
    6274: "MCP Inspector web page",
    6275: "MCP Inspector (internal)",
    6278: "MCP Inspector (internal)",
    7778: "Kiro / Quick sign-in callback",
    8000: "MCP server (local HTTP)",
    8080: "mock POS / Inventory / Sales API",
    8081: "Promotions service",
    8765: "MCP server (Kiro OAuth test)",
}


def check_ports():
    print("\n3. Local ports (must be free and reachable on 127.0.0.1)")
    s = "ports"
    for port, use in PORTS.items():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
        except OSError:
            record(s, WARN, "port {} ({})".format(port, use), "already in use - close the app using it "
                   "before the workshop")
            srv.close()
            continue
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=3):
                pass
            record(s, PASS, "port {} ({})".format(port, use), "free")
        except OSError as e:
            record(s, FAIL, "port {} ({})".format(port, use), "local connection blocked: {}".format(e))
        finally:
            srv.close()


# ---- 4. Package downloads (--deep) -----------------------------------------------------------

def check_downloads(engine):
    print("\n4. Package downloads (test only, nothing is installed)")
    s = "downloads"
    with tempfile.TemporaryDirectory() as tmp:
        code, out = run(["uv", "pip", "install", "--dry-run", "--python", sys.executable,
                         "--target", tmp, "mcp", "strands-agents", "fastapi"], timeout=180)
        if code == 0:
            record(s, PASS, "Python packages from PyPI (uv)", "mcp, strands-agents, fastapi resolved")
        else:
            record(s, FAIL, "Python packages from PyPI (uv)", (out.splitlines() or ["uv not found"])[-1][:80])

    for pkg in ("@modelcontextprotocol/inspector", "aws-cdk"):
        code, out = run(["npm", "view", pkg, "version"], timeout=120)
        if code == 0:
            record(s, PASS, "npm package {}".format(pkg), "version " + out.splitlines()[-1][:20])
        else:
            record(s, FAIL, "npm package {}".format(pkg), (out.splitlines() or ["npm not found"])[-1][:80])

    if engine:
        code, out = run([engine, "pull", "python:3.12-slim"], timeout=600)
        record(s, PASS if code == 0 else FAIL, "Container image python:3.12-slim ({})".format(engine),
               "pulled" if code == 0 else (out.splitlines() or [""])[-1][:80])
    else:
        record(s, WARN, "Container image download", "skipped - Docker/Finch not running")


# ---- 5. AWS access (--aws) -------------------------------------------------------------------

def aws(args, profile, region, timeout=60):
    cmd = ["aws"] + args + ["--region", region, "--output", "json"]
    if profile:
        cmd += ["--profile", profile]
    return run(cmd, timeout=timeout)


def check_aws(profile, region, invoke_model):
    print("\n5. AWS access (read-only calls in the account of profile {!r})".format(profile or "default"))
    s = "aws"
    code, out = aws(["sts", "get-caller-identity"], profile, region)
    if code != 0:
        record(s, FAIL, "AWS credentials", out.splitlines()[-1][:90] if out else "no output")
        return
    ident = json.loads(out)
    record(s, PASS, "AWS credentials", "account {}, {}".format(ident["Account"], ident["Arn"].split("/")[-2]
                                                                 if "/" in ident["Arn"] else ident["Arn"]))

    checks = [
        ("CloudFormation", ["cloudformation", "list-stacks", "--max-items", "1"]),
        ("CDK bootstrap", ["ssm", "get-parameter", "--name", "/cdk-bootstrap/hnb659fds/version"]),
        ("S3", ["s3api", "list-buckets", "--max-items", "1"]),
        ("ECR", ["ecr", "describe-repositories", "--max-items", "1"]),
        ("ECS", ["ecs", "list-clusters", "--max-items", "1"]),
        ("Elastic Load Balancing", ["elbv2", "describe-load-balancers", "--max-items", "1"]),
        ("CloudFront", ["cloudfront", "list-distributions", "--max-items", "1"]),
        ("Lambda", ["lambda", "list-functions", "--max-items", "1"]),
        ("Secrets Manager", ["secretsmanager", "list-secrets", "--max-results", "1"]),
        ("CloudWatch Logs", ["logs", "describe-log-groups", "--max-items", "1"]),
        ("Cognito user pools", ["cognito-idp", "list-user-pools", "--max-results", "1"]),
        ("Redshift Serverless", ["redshift-serverless", "list-workgroups", "--max-items", "1"]),
        ("Bedrock (model catalogue)", ["bedrock", "list-inference-profiles", "--max-results", "100"]),
        ("AgentCore Runtime", ["bedrock-agentcore-control", "list-agent-runtimes", "--max-results", "1"]),
        ("AgentCore Gateway", ["bedrock-agentcore-control", "list-gateways", "--max-results", "1"]),
        ("AgentCore Identity", ["bedrock-agentcore-control", "list-oauth2-credential-providers",
                                "--max-results", "1"]),
        ("AgentCore Policy", ["bedrock-agentcore-control", "list-policy-engines", "--max-results", "1"]),
    ]
    for name, args in checks:
        code, out = aws(args, profile, region)
        last = out.splitlines()[-1][:90] if out else ""
        if code == 0:
            record(s, PASS, name, "access OK")
            if name.startswith("Bedrock"):
                models = {p["inferenceProfileId"] for p in json.loads(out).get("inferenceProfileSummaries", [])}
                want = [m for m in models if "claude-sonnet-5-5" in m]
                record(s, PASS if want else FAIL, "Claude Sonnet 5.5 available",
                       ", ".join(sorted(want)) or "not listed - request model access in the Bedrock console")
        elif name == "CDK bootstrap" and "ParameterNotFound" in out:
            record(s, WARN, name, "account not bootstrapped yet - instructors run `cdk bootstrap`")
        elif "Invalid choice" in out or "invalid choice" in out:
            record(s, FAIL, name, "AWS CLI too old for this service - update AWS CLI v2")
        else:
            record(s, FAIL, name, last)

    if invoke_model:
        body = json.dumps([{"role": "user", "content": [{"text": "Reply with OK"}]}])
        code, out = aws(["bedrock-runtime", "converse", "--model-id", "global.anthropic.claude-sonnet-5-5",
                         "--messages", body, "--inference-config", '{"maxTokens": 50}'], profile, region)
        record(s, PASS if code == 0 else FAIL, "Bedrock model call (Sonnet 5.5)",
               "model answered" if code == 0 else out.splitlines()[-1][:90])


# ---- Report ----------------------------------------------------------------------------------

def write_report(args):
    counts = {k: sum(1 for r in results if r[1] == k) for k in (PASS, WARN, FAIL)}
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rst-preflight-report-{}.txt".format(stamp))
    lines = [
        "MCP workshop - pre-event check",
        "Date: {}".format(datetime.datetime.now().isoformat(timespec="seconds")),
        "OS: {} {} ({})".format(platform.system(), platform.release(), platform.machine()),
        "Options: deep={} aws={} region={}".format(args.deep, args.aws, args.region),
        "Result: {} pass, {} warning, {} fail".format(counts[PASS], counts[WARN], counts[FAIL]),
        "",
    ]
    lines += ["[{:<4}] {:<9} {:<44} {}".format(st, sec, chk, det) for sec, st, chk, det in results]
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        path = None
    print("\nResult: {} pass, {} warning, {} fail".format(counts[PASS], counts[WARN], counts[FAIL]))
    if counts[FAIL]:
        print("Fix the FAIL items (most need IT: install rights, firewall/proxy allowlist).")
    elif counts[WARN]:
        print("No blockers. Review the WARN items.")
    else:
        print("All good - this laptop is ready for the workshop.")
    if path:
        print("Report saved to: {}\nAt an instructor-led event, send this file to the instructor.".format(path))
    return 1 if counts[FAIL] else 0


def main():
    p = argparse.ArgumentParser(description="MCP workshop pre-event check (read-only).")
    p.add_argument("--deep", action="store_true", help="also test package downloads (pip, npm, Docker image)")
    p.add_argument("--aws", action="store_true", help="also test AWS service access (read-only)")
    p.add_argument("--profile", help="AWS CLI profile for --aws (default: your default credentials)")
    p.add_argument("--region", default="us-east-1", help="AWS region used by the workshop (default us-east-1)")
    p.add_argument("--invoke-model", action="store_true",
                   help="with --aws: one tiny Bedrock model call (costs a fraction of a cent)")
    args = p.parse_args()

    print("MCP workshop - pre-event check (read-only; nothing is installed or changed)")
    engine, aws_v = check_software()
    check_network(args.region)
    check_ports()
    if args.deep:
        check_downloads(engine)
    if args.aws:
        if aws_v is None:
            record("aws", FAIL, "AWS access", "skipped - AWS CLI v2 not available")
        else:
            check_aws(args.profile, args.region, args.invoke_model)
    sys.exit(write_report(args))


if __name__ == "__main__":
    main()
