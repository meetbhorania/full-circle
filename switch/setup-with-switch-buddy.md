# Setting up Full Circle with switch-buddy

switch-buddy (Switch's built-in helper agent, with "Can manage agents" on) does the setup from these files. Replace `<FULL_CIRCLE_PATH>` with the output of `pwd` in your full-circle folder.

## Message 1: fix the room and add the policy

```
Please update brew-team using files in <FULL_CIRCLE_PATH>/switch/ (read them from disk):
1. Replace the room instructions with the text below the "---" line in rooms/brew-team.md. Keep the @ off agent names like you did before.
2. Delete the "incident-log" document. We now log with "log:" lines in the thread instead.
3. Create a room-scoped document called "refund-policy" with the content of documents/refund-policy.md, and its instructions: "The refund rules. Read this before proposing any refund or credit. Never go beyond it."
4. Set the room instructions of the Discord room "#help" to the text below the "---" line in rooms/brew-help.md.
5. Run "!follow-ups off" in brew-team.
Tell me what you changed and anything you couldn't do.
```

## Message 2: create the six agents

```
Please create six agents on my MacBook, all with provider Claude Code and working directory <FULL_CIRCLE_PATH>.
For each one, read its file in <FULL_CIRCLE_PATH>/switch/agents/ and use:
- the name, description, rooms and "who can talk to it" from the settings table
- everything under "## Instructions" as the agent instructions
The files are: concierge.md, repro.md, fixer.md, reviewer.md, release-manager.md (agent name "releaser"), ledger.md.
Then:
- have "reviewer" take the role "reviewer" in brew-team
- have "releaser" take the role "release-manager" in brew-team
- invite concierge and releaser to the Discord room "#help"
- invite all six to brew-team
Tell me what you created, each agent's "who can talk to it" setting, and anything you couldn't do.
```
