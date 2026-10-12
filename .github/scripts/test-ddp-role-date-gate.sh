#!/usr/bin/env bash
# Local test of ddp-role-date-gate.sh with a fake checker (no network, no repo data). Run: bash .github/scripts/test-ddp-role-date-gate.sh
set -u
here=$(cd "$(dirname "$0")" && pwd); tmp=$(mktemp -d)
K="data/az/legislature/Known-1.yml: role has end_date 2019-01-14 but no start_date (district='27', type='upper')"
N="data/xx/legislature/New-1.yml: role has end_date 2024-01-01 but no start_date (district='1', type='upper')"
M="Role date integrity problems found (duplicate/dangling role entries)."
printf '# header\n%s\n' "$K" > "$tmp/known.txt"
cat > "$tmp/fake.sh" <<'F'
case "$CASE" in
  ok)            echo "No changed person files to check";;
  known_only)    echo "$K"; echo "warning: 2 people have a role end_date of x"; echo "  Verify each person"; echo "note: 3 finding(s) pre-exist"; echo "$M" >&2; exit 1;;
  known_and_new) echo "$K"; echo "$N"; echo "$M" >&2; exit 1;;
  crash_after_known) echo "$K"; echo "Traceback (most recent call last):" >&2; echo "ValueError: boom" >&2; exit 1;;
  stderr_extra)  echo "$K"; echo "uv: something odd" >&2; echo "$M" >&2; exit 1;;
  exit_two)      echo "$K"; echo "$M" >&2; exit 2;;
  odd_stdout)    echo "$K"; echo "SURPRISE: new diagnostic format"; echo "$M" >&2; exit 1;;
  no_finding)    echo "$M" >&2; exit 1;;
esac
F
fail=0
check() { # name expected_exit_is_zero(0|1)
  KNOWN="$tmp/known.txt" CHECKER="bash $tmp/fake.sh" CASE="$1" K="$K" N="$N" M="$M" bash "$here/ddp-role-date-gate.sh" >/dev/null 2>&1; got=$?
  if { [[ $2 == 0 && $got -eq 0 ]] || [[ $2 == 1 && $got -ne 0 ]]; }; then echo "ok   $1 (exit $got)"; else echo "FAIL $1 (exit $got, wanted $([[ $2 == 0 ]] && echo 0 || echo non-zero))"; fail=1; fi
}
check ok 0; check known_only 0
check known_and_new 1; check crash_after_known 1; check stderr_extra 1; check exit_two 1; check odd_stdout 1; check no_finding 1
exit $fail
