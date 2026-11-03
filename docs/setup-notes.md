# Full Circle: setup notes

Working notes from the first setup session (Tue 3 Nov 2026). Used later for the README "Setup" section and the blog post.

## Environment

| Item | Version / value |
|---|---|
| Machine | MacBook Air, Apple silicon (arm64) |
| Docker | 28.4.0 |
| Switch Console | v0.40.1 (server: "On this computer") |
| Claude Code | 2.1.310 (update to 2.1.317 offered) |
| Messaging apps | Mattermost (bundled, default) + Telegram |

## What works (verified)

- Local Switch server running in Docker, admin signed in
- `switch-buddy` agent (Claude Code) replying in Console direct chat, in Mattermost Town Square, and in the Telegram group
- Telegram bot connected as **"Telegram – Brew & Co Customers"**, Telegram account linked
- Telegram group **Brew & Co Help** auto-became a Switch room; bot is group admin and sees all messages
- End-to-end: phone → Telegram → Switch → Claude Code → reply on phone (~4s)

## Gotchas and fixes

1. **Agent stuck on "Failed": `EACCES: permission denied, mkdir ~/.local/state/switch`**
   `~/.local` was owned by root (from an old sudo install).
   ```bash
   sudo chown -R $(whoami):staff ~/.local
   mkdir -p ~/.local/state/switch
   ```
   Then quit Console fully (⌘Q) and reopen.

2. **Claude Code "Not signed in" in Console.** Run `claude auth login` in a terminal, then **Recheck** in Settings → Agent providers. Check with `claude -p "say hi"`.

3. **Template name differs from the docs.** On v0.40.1 the helper template is **switch-buddy** (docs say "Switch expert"), and there's no "Start it in a room" toggle. The agent joined Town Square automatically.

4. **Telegram privacy.** `/setprivacy` in BotFather: tap the bot's button *first*, then **Disable**. If the bot joined a group before privacy was off, make it a **group admin** (fixes that chat right away).

5. **Telegram DMs to the bot are not routed to agents.** Agents only work in group rooms. Use `/invite_agent @agent-name` inside the group.

6. **Linking your Telegram account** only works after you've sent a message in a chat the bot is in.

7. **One session, one room at a time.** An agent can belong to rooms on different platforms, but a running session sits in one room and moves between them. Design implication: keep the customer-facing Concierge in the Telegram room and team agents in the team room, with one deliberate handoff.

## Useful room commands

- `/invite_agent @name` (Telegram) or `!invite-agent @name` (any app)
- `!roles`: list jobs in the room and who holds them
- `!set-alias @agent @short`: room-scoped short name
- `!follow-ups off`: require explicit @mentions (use for the deploy agent)

## Next

- [ ] Team room: decide Slack vs bundled Mattermost
- [ ] Demo shop (Brew & Co) with planted double-charge bug
- [ ] Concierge + Repro agents
