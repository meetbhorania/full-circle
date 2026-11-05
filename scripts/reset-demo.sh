#!/usr/bin/env bash
# Reset Full Circle to a clean demo state before a rehearsal or video take.
#
#   ./scripts/reset-demo.sh
#
# What it does:
#   1. Closes any open pull requests and deletes fix/* branches (local and GitHub)
#   2. Removes extra git worktrees the agents created
#   3. Puts the shop code back to the "demo-start" tag (bug restored),
#      as a normal commit, so public history is never rewritten
#   4. Clears the live ledger and restarts the shop
#
# It never touches switch/, docs/, README or anything outside shop/.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }

step "Checking you're on main with nothing uncommitted"
git checkout -q main
git pull -q --ff-only
if [ -n "$(git status --porcelain -- . ':!shop/data')" ]; then
  echo "You have uncommitted changes. Commit or stash them first:"; git status --short; exit 1
fi

step "Closing open pull requests"
for n in $(gh pr list --state open --json number -q '.[].number'); do
  gh pr close "$n" --comment "Closed by reset-demo.sh before a new take." >/dev/null && echo "  closed #$n"
done

step "Removing agent worktrees"
git worktree list --porcelain | awk '/^worktree /{print $2}' | while read -r wt; do
  [ "$wt" = "$(pwd -P)" ] || [ "$wt" = "$(pwd)" ] && continue
  git worktree remove --force "$wt" && echo "  removed $wt"
done
git worktree prune

step "Deleting fix/* branches"
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/fix/); do
  git branch -D "$b" >/dev/null && echo "  deleted local $b"
done
for b in $(git ls-remote --heads origin 'fix/*' | awk '{sub("refs/heads/","",$2); print $2}'); do
  git push -q origin --delete "$b" && echo "  deleted remote $b"
done

step "Restoring the shop code to demo-start (bug back in)"
added=$(git diff --name-only --diff-filter=A demo-start HEAD -- shop/ || true)
[ -n "$added" ] && git rm -q $added
git restore --source demo-start --staged --worktree -- shop/
if git diff --cached --quiet; then
  echo "  already at demo-start"
else
  git commit -q -m "chore(demo): reset shop to demo-start for the next take"
  git push -q
  echo "  committed and pushed"
fi

step "Clearing the ledger and restarting the shop"
docker compose restart shop >/dev/null
sleep 2
curl -s -X POST localhost:8000/api/_reset >/dev/null
curl -s localhost:8000/api/health && echo

step "Ready. Double-click Pay as Sam, then complain in #help."
