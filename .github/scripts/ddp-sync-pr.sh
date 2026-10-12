#!/usr/bin/env bash
# Keeps one standing PR from the mirror branch sync/upstream into main (PLAN-fork-management.md §8.3/§8.4).
# Same approach as the code forks' script; UPSTREAM_REPO comes from the workflow's env. This job never pushes to main:
# a person approves the PR, and upstream's own Lint YAML (yamllint, os-people lint, duplicate-person, role-date,
# new-URL and committee checks, each reporting only what the change introduces) is the gate on it.
set -euo pipefail
git remote add upstream "https://github.com/${UPSTREAM_REPO}.git"
git fetch --quiet upstream main
pr=$(gh pr list --head sync/upstream --state open --json number -q '.[0].number')
behind=$(git rev-list --count --first-parent origin/main..upstream/main)
if [ "$behind" -eq 0 ]; then
  if [ -n "$pr" ]; then gh pr close "$pr" --comment "main now contains upstream; nothing to merge."; fi
  echo "up to date"; exit 0
fi
data=$(git diff --name-only origin/main...upstream/main -- data | wc -l | tr -d ' ')
workflows=$(git diff --name-only origin/main...upstream/main -- .github | sed 's/^/  /' || true)   # workflow changes are the security-relevant part and would be buried in a big data diff
set +e   # git exits 1 for conflicts AND for a bad ref, so judge the output, not the exit code
mt=$(git merge-tree --write-tree --name-only --no-messages origin/main upstream/main 2>/tmp/mt.err)
set -e
[[ "$(printf '%s\n' "$mt" | head -1)" =~ ^[0-9a-f]{40,64}$ ]] || { echo "merge-tree failed: $(cat /tmp/mt.err)"; exit 1; }
conflicts=$(printf '%s\n' "$mt" | sed 1d | grep -v '^$' || true)   # a real result starts with a tree id; conflicts are the lines after it
git push --force origin upstream/main:refs/heads/sync/upstream   # sync/upstream is owned by this job alone: an exact mirror of upstream, never committed to by hand
title="Sync upstream (${behind} commits)"
body="Upstream mainline commits: ${behind}. Files under data/: ${data}.
Would conflict today: ${conflicts:-none}
Changes under .github/ (read these first; they can run code):
${workflows:-  none}
Gate: this PR's Lint YAML check. Merge with a real merge commit (not a rebase), per PLAN-fork-management.md §8.3."
if [ -z "$pr" ]; then gh pr create --base main --head sync/upstream --title "$title" --body "$body"
else gh pr edit "$pr" --title "$title" --body "$body"; fi
