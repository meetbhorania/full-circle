"""qa-gate: a custom Switch agent written in plain Python. No LLM.

It joins brew-team through the Switch agent protocol (WebSocket in, HTTP out)
and, when someone hands it a pull request, it:

  1. checks the PR out in its own git worktree (never touches the live shop),
  2. runs the test suite,
  3. fires 10 simultaneous checkouts with one idempotency key and requires
     exactly one charge, and a reused key with a different order to get 409,
  4. scans the PR's added lines for real customer data from the live ledger,

then posts a pass/fail table in the thread and hands the PR to @releaser
(pass) or back to @fixer (fail).

    python3 qa_gate.py register   # once: registers the agent with Switch
    python3 qa_gate.py run        # keep running while you demo
    python3 qa_gate.py allow      # (re)set: you and your agents may address it

Settings come from environment variables (see README.md next to this file).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import httpx
import websockets

NAME = "qa-gate"
API = os.environ.get("SWITCH_API_URL", "http://localhost:63126").rstrip("/")
REPO = Path(os.environ.get("FULL_CIRCLE_DIR", Path(__file__).resolve().parents[2]))
SHOP = os.environ.get("SHOP_URL", "http://localhost:8000").rstrip("/")
STATE = Path(os.environ.get("QA_GATE_STATE", Path.home() / ".config" / "full-circle" / "qa-gate.json"))
PR_RE = re.compile(r"(?:/pull/|#|PR\s*)(\d+)", re.I)


# --------------------------------------------------------------------------
# State and HTTP helpers
# --------------------------------------------------------------------------
def load_state() -> dict:
    if not STATE.exists():
        sys.exit(f"Not registered yet. Run: python3 {Path(__file__).name} register")
    return json.loads(STATE.read_text())


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))
    STATE.chmod(0o600)  # holds the agent's API key


class Ops:
    """Calls Switch operations: POST /agents/{id}/ops/{operation}."""

    def __init__(self, agent_id: str, api_key: str, connection_id: str):
        self.agent_id = agent_id
        self.client = httpx.AsyncClient(
            base_url=API,
            timeout=30,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Switch-Connection-Id": connection_id,
            },
        )

    async def call(self, op: str, **args):
        r = await self.client.post(f"/agents/{self.agent_id}/ops/{op}", json=args)
        if r.status_code != 200:
            raise RuntimeError(f"{op} failed: {r.status_code} {r.text[:300]}")
        return r.json().get("result")


# --------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------
OWNER_AND_OWNER_AGENTS = {"rules": [{"rooms": "*", "room_groups": "*", "users": [], "agents": [],
                                     "owner": True, "owner_agents": True, "platform": False}]}
_gateway: httpx.Client | None = None


def gateway() -> httpx.Client:
    """A Gateway API session as the signed-in owner (asks once per run)."""
    global _gateway
    if _gateway is None:
        import getpass
        print("Sign in to Switch (the same admin account as Switch Console).")
        email = input("Email: ").strip()
        password = getpass.getpass("Password (hidden): ")
        _gateway = httpx.Client(base_url=f"{API}/gateway", timeout=60)
        r = _gateway.post("/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            sys.exit(f"Sign-in failed ({r.status_code}): {r.text[:200]}")
    return _gateway


def allow(agent_id: str | None = None) -> None:
    """Let you and your agents address qa-gate. Only the owner may set this."""
    agent_id = agent_id or load_state()["agent_id"]
    r = gateway().put(f"/agents/{agent_id}/addressing-policy", json={"policy": OWNER_AND_OWNER_AGENTS})
    if r.status_code != 200:
        sys.exit(f"Couldn't set who can talk to qa-gate ({r.status_code}): {r.text[:200]}")
    print("Who can talk to qa-gate: you and your agents (customers are refused).")


def registration_key_from_login() -> str:
    """Create a registration key through the Gateway API, as the signed-in admin.

    The Gateway API is mounted at {API}/gateway. Logging in sets a session
    cookie; POST /gateway/api-keys then returns a new registration key, owned
    by you, so qa-gate becomes your agent. The password is never stored.
    """
    r = gateway().post("/api-keys", json={"label": "qa-gate"})
    if r.status_code != 200:
        sys.exit(f"Couldn't create a registration key ({r.status_code}): {r.text[:200]}")
    print("Created a registration key labelled 'qa-gate'.")
    return r.json()["key"]


def register() -> None:
    try:
        httpx.get(f"{API}/health", timeout=5).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Can't reach the Switch agent bridge at {API}/health ({exc}).\n"
                 "Set SWITCH_API_URL to your server's API URL.")
    pending = STATE.with_suffix(".regkey")
    key = os.environ.get("SWITCH_REGISTRATION_KEY") or (pending.read_text().strip() if pending.exists() else "")
    if not key:
        key = registration_key_from_login()
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(key); pending.chmod(0o600)  # reused if this run is interrupted
    body = {
        "name": NAME,
        "display_name": NAME,
        "description": "Plain-Python QA gate: tests, concurrency stress, privacy scan. No LLM.",
        "connector_type": "full-circle-python",
        "integration_profile": {
            "connection_model": "always_on",
            "message_exchange": True,
            "pre_invocation_mediation": [],
            "post_invocation_mediation": [],
            "event_reporting": [],
        },
    }
    print("Registering qa-gate on every connected messaging app (can take a minute or two)...")
    r = httpx.post(f"{API}/agents", json=body, headers={"Authorization": f"Bearer {key}"}, timeout=180)
    if r.status_code == 409:
        # Usually an earlier attempt that finished after we stopped waiting.
        # overwrite=true re-issues the agent's key; it only works if it's yours.
        print("qa-gate already exists (probably from an earlier attempt); re-registering it...")
        r = httpx.post(f"{API}/agents", json={**body, "overwrite": True},
                       headers={"Authorization": f"Bearer {key}"}, timeout=180)
    if r.status_code != 200:
        sys.exit(f"Registration failed ({r.status_code}): {r.text[:300]}")
    data = r.json()
    save_state({"agent_id": data["id"], "api_key": data["api_key"], "connection_id": str(uuid.uuid4())})
    pending.unlink(missing_ok=True)
    print(f"Registered {NAME} ({data['id']}).")
    # Let the owner's other agents (fixer, reviewer) hand it work; customers stay refused.
    # Switch only lets the owner change this, not the agent itself.
    allow(data["id"])
    print(f"API key saved to {STATE} (keep it private). Now invite qa-gate to brew-team, then run:")
    print(f"  python3 {Path(__file__).name} run")


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------
def sh(cmd: list[str], cwd: Path | None = None, env: dict | None = None, timeout: int = 300):
    p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def python_cmd(wt: Path) -> list[str]:
    """python3 with pytest + fastapi on this machine, else the shop's Docker image."""
    rc, _ = sh(["python3", "-c", "import pytest, fastapi, httpx"])
    if rc == 0:
        return ["python3"]
    rc, image = sh(["docker", "inspect", "brewco-shop", "--format", "{{.Config.Image}}"])
    if rc != 0:
        raise RuntimeError("Need python3 with pytest+fastapi, or the brewco-shop container running")
    return ["docker", "run", "--rm", "-v", f"{wt}:/app", "-w", "/app",
            "-e", "PAYMENT_LATENCY_MS", "-e", "LEDGER_PATH", image.strip(), "python"]


STRESS = r"""
import os, threading, tempfile
os.environ["LEDGER_PATH"] = os.path.join(tempfile.mkdtemp(), "l.json")
os.environ["PAYMENT_LATENCY_MS"] = "300"
from fastapi.testclient import TestClient
from shop.app import app
c = TestClient(app)
body = {"customer": "qa-user", "item": "beans-1kg", "idempotency_key": "qa-same-key"}
ts = [threading.Thread(target=lambda: c.post("/api/checkout", json=body)) for _ in range(10)]
[t.start() for t in ts]; [t.join() for t in ts]
n = len(c.get("/api/charges").json()["charges"])
reuse = c.post("/api/checkout", json={**body, "quantity": 3}).status_code
print(f"{n} {reuse}")
"""


def privacy_findings(diff: str) -> list[str]:
    """Real customer data from the live ledger that appears in the PR's added lines."""
    try:
        live = httpx.get(f"{SHOP}/api/charges", timeout=5).json()["charges"]
    except Exception:  # noqa: BLE001
        live = []
    secrets = {c["idempotency_key"] for c in live if c.get("idempotency_key")}
    secrets |= {c["customer"] for c in live if c.get("customer") and c["customer"] not in ("test-user", "qa-user")}
    secrets |= {"sam.brewco"}
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    return sorted({s for s in secrets for l in added if s and re.search(rf"\b{re.escape(s)}\b", l)})


def check_pr(pr: int) -> tuple[bool, str]:
    wt = Path(tempfile.gettempdir()) / "qa-gate" / f"pr-{pr}"
    rows: list[tuple[str, bool, str]] = []
    sh(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO)
    shutil.rmtree(wt, ignore_errors=True)
    rc, out = sh(["git", "fetch", "-q", "origin", f"pull/{pr}/head:refs/qa/pr-{pr}", "--force"], cwd=REPO)
    if rc != 0:
        return False, f"Couldn't fetch PR #{pr}: {out[-300:]}"
    sh(["git", "worktree", "add", "-q", "--detach", str(wt), f"refs/qa/pr-{pr}"], cwd=REPO)
    try:
        py = python_cmd(wt)
        rc, out = sh(py + ["-m", "pytest", "-q", "shop/tests"], cwd=wt, env={"PAYMENT_LATENCY_MS": "0"})
        summary = next((l for l in reversed(out.splitlines()) if "passed" in l or "failed" in l or "error" in l), out[-120:])
        rows.append(("Test suite", rc == 0, summary.strip("= ")))

        rc, out = sh(py + ["-c", STRESS], cwd=wt)
        try:
            charges, reuse = (int(x) for x in out.strip().splitlines()[-1].split())
            rows.append(("10 simultaneous clicks, one key", charges == 1, f"{charges} charge(s), want 1"))
            rows.append(("Same key, different order", reuse == 409, f"HTTP {reuse}, want 409"))
        except Exception:  # noqa: BLE001
            rows.append(("Concurrency stress", False, out[-200:]))

        sh(["git", "fetch", "-q", "origin", "main"], cwd=REPO)
        rc, diff = sh(["git", "diff", f"origin/main...refs/qa/pr-{pr}"], cwd=REPO)
        leaks = privacy_findings(diff) if rc == 0 else ["(couldn't read diff)"]
        rows.append(("No customer data in the diff", not leaks, "clean" if not leaks else f"found {len(leaks)} item(s) from the live ledger"))
    finally:
        sh(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO)
        sh(["git", "update-ref", "-d", f"refs/qa/pr-{pr}"], cwd=REPO)

    ok = all(r[1] for r in rows)
    table = "| Check | Result | Detail |\n|---|---|---|\n" + "\n".join(
        f"| {name} | {'✅' if passed else '❌'} | {detail} |" for name, passed, detail in rows)
    return ok, table


# --------------------------------------------------------------------------
# run: the agent loop
# --------------------------------------------------------------------------
async def handle(ops: Ops, data: dict) -> None:
    p = data.get("payload", {})
    if not p.get("addressed"):
        return
    room_id, thread = data.get("room_id"), p.get("thread_id") or p.get("message_id")
    await ops.call("connect_to_room", room_id=room_id, include_general_instructions=False)
    m = PR_RE.search(p.get("body", ""))
    if not m:
        await ops.call("post_message", thread_id=thread,
                       body="Hand me a pull request (a link or #number) and I'll run the QA gate on it.")
        return
    pr = int(m.group(1))
    await ops.call("post_message", thread_id=thread,
                   body=f"Running the QA gate on PR #{pr}: tests, 10-click concurrency stress, key reuse, privacy scan.")
    ok, table = await asyncio.to_thread(check_pr, pr)
    verdict = f"QA gate on PR #{pr}: **{'passed' if ok else 'failed'}**\n\n{table}"
    await ops.call("send_targeted_message", thread_id=thread,
                   target_names=["releaser" if ok else "fixer"],
                   body=verdict + ("\n\nReady for you. It still needs a person's approval to ship."
                                   if ok else "\n\nBack to you: fix the failing checks and hand it to me again."))
    await ops.call("post_message", thread_id=thread,
                   body=f"log: {__import__('time').strftime('%H:%M:%S')}  qa-gate  "
                        f"{'Passed' if ok else 'Failed'} PR #{pr}  https://github.com/meetbhorania/full-circle/pull/{pr}")


async def run() -> None:
    st = load_state()
    ops = Ops(st["agent_id"], st["api_key"], st["connection_id"])
    ws_url = API.replace("http", "ws", 1) + f"/agents/{st['agent_id']}/connection/ws"
    cursor, generation = None, None
    while True:
        params = {"connection_id": st["connection_id"], "scope": "all", "filter": "addressed",
                  "client": NAME, "client_version": "1.0"}
        if cursor is not None:
            params["start_from"] = str(cursor)
        if generation is not None:
            params["expected_generation"] = str(generation)
        url = ws_url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        try:
            async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {st['api_key']}"},
                                          max_size=None) as ws:
                async for raw in ws:
                    frame = json.loads(raw)
                    event, data = frame.get("event"), frame.get("data", {})
                    if event == "ping":  # answer first, always
                        await ws.send(json.dumps({"type": "pong", "cursor": cursor or 0}))
                    elif event == "connection_state":
                        cursor, generation = data.get("cursor", cursor), data.get("generation")
                        print(f"connected: {len(data.get('rooms') or [])} room(s), cursor {cursor}")
                    elif event == "message":
                        cursor = frame.get("id", cursor)
                        asyncio.create_task(safe(handle(ops, data)))
                    elif event in ("command", "room_join"):
                        cursor = frame.get("id", cursor)
                    elif event == "gap":
                        cursor = data.get("resumed_at", cursor)
                    elif event in ("refused", "evicted"):
                        print(f"{event}: {data}")
                        if data.get("code") == "taken_over":
                            return
        except (OSError, websockets.ConnectionClosed) as exc:
            print(f"connection lost ({exc}); reconnecting in 3 s")
        await asyncio.sleep(3)


async def safe(coro) -> None:
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        print(f"error handling message: {exc}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "register":
        register()
    elif cmd == "allow":
        allow()
    elif cmd == "run":
        asyncio.run(run())
    else:
        print(__doc__)
