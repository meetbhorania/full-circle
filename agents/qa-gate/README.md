# qa-gate: a custom Switch agent in plain Python

Every other agent in Full Circle is Claude Code. **qa-gate is not an LLM at all.** It's ~250 lines of Python that joins the `brew-team` room through the [Switch agent protocol](https://docs.switchagents.ai/switch-rooms/internals/agent-protocol): events come in over a WebSocket, and it acts through HTTP operations (`connect_to_room`, `post_message`, `send_targeted_message`).

It shows that a Switch room doesn't care what an agent is made of: a CI script can sit in the same room as Claude Code agents and people, take hand-offs by `@mention`, and hand work on.

## What it does

When someone (normally `@reviewer`) writes `@qa-gate please check <PR link>`, it:

| Check | Pass when |
|---|---|
| Test suite | `pytest shop/tests` passes on the PR's code |
| 10 simultaneous clicks, one key | exactly **1** charge |
| Same key, different order | **409 Conflict** |
| No customer data in the diff | none of the live ledger's customer names, handles or idempotency keys appear in the PR's added lines |

It runs everything in a temporary git worktree, so the live shop is never touched, then posts a ✅/❌ table in the thread and hands the PR to **@releaser** (all pass) or back to **@fixer** (any fail), plus a `log:` line for the incident record.

Tested against the real PRs: PR #2 passes all four; PR #1 fails "same key, different order" (HTTP 200) and the privacy check (it contained the customer's name), the same problems the LLM reviewer caught.

## Set it up (about 5 minutes)

1. **Find your Switch API URL** (the agent bridge, not the Gateway). For a local Switch Console server it's usually `http://localhost:63126`. Check: `curl http://localhost:63126/health`.
2. **Install and register** (from the repo root):
   ```bash
   python3 -m venv agents/qa-gate/.venv
   agents/qa-gate/.venv/bin/pip install -r agents/qa-gate/requirements.txt
   agents/qa-gate/.venv/bin/python agents/qa-gate/qa_gate.py register
   ```
   It asks for your Switch admin email and password (the same account as Switch Console), creates a registration key through the Gateway API (`/gateway/api-keys`), registers `qa-gate` with you as its owner, sets who may address it to *you and your agents* (customers are refused), and saves its own API key to `~/.config/full-circle/qa-gate.json` (outside the repo, owner-only). The password is never stored. Already have a registration key? Set `SWITCH_REGISTRATION_KEY` and it skips sign-in.
3. **Invite it to brew-team:** in `brew-team`, post `!invite-agent @qa-gate`.
4. **Run it** (leave this terminal open during the demo):
   ```bash
   agents/qa-gate/.venv/bin/python agents/qa-gate/qa_gate.py run
   ```
   It prints `connected: N room(s)` and answers Switch's heartbeat every 2 seconds.

Needs: `git`, and either `python3` with `pytest` + `fastapi` or the `brewco-shop` Docker container running (it uses the shop's image to run the tests).

| Variable | Default |
|---|---|
| `SWITCH_API_URL` | `http://localhost:63126` |
| `FULL_CIRCLE_DIR` | this repo |
| `SHOP_URL` | `http://localhost:8000` |
| `SWITCH_REGISTRATION_KEY` | asked for interactively |
