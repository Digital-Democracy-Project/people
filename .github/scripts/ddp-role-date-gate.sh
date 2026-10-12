#!/usr/bin/env bash
# DDP: wraps upstream's check_role_dates.py so the exact findings listed in .github/known-role-date-findings.txt
# are ignored, and EVERYTHING else still fails.
#
# Contract, read from check_role_dates.py main(): exit 0 = fine; exit 1 = blocking findings, printed to stdout one per
# line as "<path>: <problem>" and followed on stderr by exactly one message ("Role date integrity problems found
# (duplicate/dangling role entries)."). Warnings go to stdout as "warning: ..." (plus indented continuation lines) and
# there may be a "note: ..." line. Any other exit status, any other stderr text (a traceback, a uv message) or any other
# stdout line means something else went wrong, and the gate fails.
set -uo pipefail
KNOWN="${KNOWN:-.github/known-role-date-findings.txt}"
CHECKER="${CHECKER:-uv run python .github/scripts/check_role_dates.py}"
out=$(mktemp); err=$(mktemp)
# shellcheck disable=SC2086
$CHECKER "$@" >"$out" 2>"$err"; status=$?
cat "$out" "$err"
[[ $status -eq 0 ]] && exit 0
if [[ $status -ne 1 ]]; then echo "role-date gate: the check exited with status $status (not a findings failure)"; exit "$status"; fi
if [[ "$(grep -v -E '^[[:space:]]*$' "$err")" != "Role date integrity problems found (duplicate/dangling role entries)." ]]; then
  echo "role-date gate: unexpected stderr, so this is not a plain findings failure"; exit 1
fi
if grep -v -E '^(data/|warning:|note:|  |$)' "$out" | grep -q .; then
  echo "role-date gate: unexpected output format"; exit 1
fi
if ! grep -q -E '^data/' "$out"; then echo "role-date gate: failed without reporting a finding"; exit 1; fi
unknown=$(grep -E '^data/' "$out" | grep -v -x -F -f "$KNOWN" || true)
if [[ -n "$unknown" ]]; then
  echo "role-date gate: new findings (not in $KNOWN):"; echo "$unknown"; exit 1
fi
echo "role-date gate: only the known findings from $KNOWN; ignored."
