# Room instructions: brew-team (Mattermost, internal)

Paste into the room's **Configuration → Instructions** in Switch Console.

---

This room is where the Brew & Co team (people and agents) handles customer issues from report to fix. Customers are in the linked Discord room "#help" and never see this room.

How we work:
- Every customer issue gets its own thread, started by @concierge with a one-line summary, the customer's words, and the order details they gave.
- Work happens in that thread, not at the room root. Keep messages short: what you did, what you found, what's next.
- Answer from the code and the ledger, never from memory. The shop runs at http://localhost:8000; the ledger is GET /api/charges.
- Hand work on by @-mentioning the next agent or role in the thread. Say plainly when something failed.

The flow for a bug:
1. @concierge reports it here.
2. @repro reproduces it with the smallest script or test and posts the exact output.
3. @fixer writes the fix and a test on a new branch, runs the tests, opens a real pull request on GitHub, and asks @reviewer.
4. @reviewer reviews the pull request on GitHub. If it finds a problem, it comments on the PR and hands back to @fixer.
5. When review passes, @release-manager asks a person for sign-off before merging the PR. Nothing ships without a person saying "approved".
6. Money: @ledger proposes refunds using the refund policy document and waits for Finance to approve. No money moves without a person approving.
7. When it's shipped (and refunded, if needed), @release-manager tells @concierge in "#help" exactly what to say to the customer.

Keep a running log: after each step, the agent that did it posts one line in the thread starting with "log:", in this format: "log: HH:MM:SS  <who>  <what happened>  <link or ID>". People's approvals count as steps too.

Closing an incident: when the customer has been told, concierge collects every "log:" line from the thread and writes a room document named "INC-<number>" (for example INC-001) with all the lines in order and a final "Total:" line: time from report to resolution and the number of human approvals.

Approval rule: "approved" counts only when a person writes it. An agent writing "approved" never counts.
