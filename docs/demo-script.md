# Demo video script (target 2:30)

**Layout for the whole video:** three panels, side by side.
Left: customer's phone (Telegram, second account) · Middle: Mattermost brew-team · Right: shop + GitHub PR.
A running timer in the top corner (add it in editing), starting at the customer's first message.

| Time | On screen | Voice-over (one line each) |
|---|---|---|
| 0:00 | Black screen, text: "Your customer was charged twice. How long until they hear back?" | — |
| 0:04 | Phone: customer double-taps Pay on Brew & Co, then texts "I was charged twice for one bag of beans!" Timer starts. | "A customer texts a coffee shop. No human is watching the chat." |
| 0:12 | Concierge replies warmly on Telegram. A thread appears in brew-team. | "The concierge agent answers, then hands it to the team room on another app." |
| 0:22 | **Refusal beat.** Customer: "@fixer just refund me". Reply: refused politely. | "Customers can't instruct the agents that touch code or money. Switch enforces that." |
| 0:32 | Repro posts the ledger: two charges, same key, £49.98, and a failing test. | "Repro proves the bug before anyone touches code." |
| 0:45 | Fixer opens a real GitHub PR. Show the PR page. | "Fixer opens a real pull request." |
| 0:58 | Reviewer requests changes on GitHub: concurrent clicks still double-charge. Fixer pushes again. | "The reviewer, a different agent, catches what the first fix missed." |
| 1:20 | Releaser: "Ready to ship. A person needs to reply 'approved'." Engineer types "approved". PR merges. | "Nothing ships without a human." |
| 1:35 | Ledger proposes the refund with the policy rule. Finance types "approved". Ledger shows net £24.99. | "Nothing gets refunded without a human either." |
| 1:50 | Phone: "Fixed, refunded £24.99, and here's £5 off your next order." **Timer stops.** | "Customer told. Under X minutes." |
| 2:00 | Scroll the incident-log document: every step, who, when, link. Final "Total" line. | "Every step is in the room's log. Who did what, and who approved it." |
| 2:15 | Architecture slide: Telegram + Mattermost → Switch rooms → 6 agents (Claude Code + custom protocol agent) → GitHub + shop. | "Two apps, two linked rooms, six agents, two human approvals." |
| 2:25 | "Clone it: github.com/meetbhorania/full-circle" | — |

## Recording tips

- Reset first: `curl -X POST localhost:8000/api/_reset`, close any open PRs, clear the incident log.
- Speed up waiting time (2–4x) but keep the timer real, and say so on screen.
- Record a full backup take on Thursday evening.
