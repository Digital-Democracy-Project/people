#!/usr/bin/env bash
#
# CodeBot test helper for people.
#
# Runs this repo's real CI checks -- os-people lint, os-committees lint,
# check_duplicate_people.py -- against THIS checkout (the clone CodeBot is
# editing), in an isolated, throwaway Docker container built from
# .codebot/Dockerfile. No Postgres/Redis needed: linting is pure
# YAML-schema validation against local files, no DB or network involved.
#
# IMPORTANT -- scoped to changed states, deliberately, matching CI's own
# "lint selectively" steps (.github/workflows/lint-yaml.yml): data/ covers
# ~50 states and running os-people lint across all of them on every run
# would be needlessly slow for a ticket that only ever touches one or two.
# Auto-detects touched states from the branch diff against origin/main; pass
# explicit state codes to override.
#
# The devos `test-ticket` skill invokes this via the required `.codebot/test.sh`
# entrypoint (Step 0 of that skill looks for that exact path at the repo root).
#
# Usage:
#   .codebot/test.sh [TICKET_KEY] [state-code ...]
#
#   TICKET_KEY is optional, used only for labelling the run and scoping the
#   image tag. Extra args, if given, are treated as explicit two-letter state
#   codes to lint instead of auto-detecting them from the branch diff.
#
# Exit code is non-zero if any lint step fails.

set -euo pipefail

# --- AGENTS-250: the Mac's test Docker VM, never production's ------------------
# On the Mac, Docker is two VMs: production's (CAMS, api-v3, the dev broker and its copy of production) and a test
# VM on /Volumes/DDP-HOT for every throwaway test stack and image build. ddp-agents'
# deployment/scripts/colima-test.sh is the one place that knows where the test VM is; when it exists, this script
# takes DOCKER_HOST from it and stops (exit 2) if the test VM is not available, instead of building on production.
# Elsewhere (no such file) DOCKER_HOST is left as it is. DDP_COLIMA_TEST_SH overrides the path; empty turns it off.
COLIMA_TEST_SH="${DDP_COLIMA_TEST_SH-/Users/agentsmith/Developer/repos/ddp-agents/deployment/scripts/colima-test.sh}"
if [[ -n "${COLIMA_TEST_SH}" && -r "${COLIMA_TEST_SH}" ]]; then
  if ! WHY="$(bash "${COLIMA_TEST_SH}" check 2>&1)"; then
    echo "ERROR: the test Docker VM is not available, so nothing was built: ${WHY}" >&2
    exit 2
  fi
  DOCKER_HOST="$(bash "${COLIMA_TEST_SH}" docker-host)"
  export DOCKER_HOST
  if ! docker info >/dev/null 2>&1; then
    echo "ERROR: the test Docker VM is set up but not running (${DOCKER_HOST}), so nothing was built." >&2
    echo "       Start it with: ${COLIMA_TEST_SH} colima start" >&2
    exit 2
  fi
  echo ">>> Docker: the test VM (${DOCKER_HOST})"
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TICKET_KEY="${1:-run}"
shift || true
STATE_ARGS=("$@")

SAFE_KEY="$(echo "${TICKET_KEY}" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/-\{2,\}/-/g; s/^-//; s/-$//')"
# Image tag scoped by ticket key + PID, not a fixed shared name -- see
# openstates-scrapers/openstates-core's identical comment: CAMS's worker pool
# can run multiple CodeBot tickets concurrently.
IMAGE="codebot-people-test:${SAFE_KEY:-run}-$$"

cleanup() {
  docker rmi "${IMAGE}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo ">>> CodeBot isolated test run for ${TICKET_KEY} (people)"
echo ">>> image=${IMAGE}"

echo ">>> building image from this checkout..."
docker build -q -t "${IMAGE}" -f "${REPO_ROOT}/.codebot/Dockerfile" "${REPO_ROOT}" >/dev/null

CHANGED_FILES=""
if [[ ${#STATE_ARGS[@]} -gt 0 ]]; then
  STATES=("${STATE_ARGS[@]}")
else
  CHANGED_FILES="$(git -C "${REPO_ROOT}" diff origin/main...HEAD --name-only -- data/ 2>/dev/null || true)"
  STATES=()
  while IFS= read -r state; do
    [[ -n "${state}" ]] && STATES+=("${state}")
  done < <(printf '%s\n' "${CHANGED_FILES}" | awk -F/ 'NF>1{print $2}' | sort -u)
fi

if [[ ${#STATES[@]} -eq 0 ]]; then
  echo ">>> no data/<state>/ changes detected on this branch -- nothing to lint"
  exit 0
fi

echo ">>> states: ${STATES[*]}"

STATUS=0

echo ">>> running: os-people lint ${STATES[*]}"
docker run --rm -e OS_PEOPLE_DIRECTORY=/opt/people "${IMAGE}" os-people lint "${STATES[@]}" || STATUS=$?

echo ">>> running: os-committees lint ${STATES[*]}"
docker run --rm -e OS_PEOPLE_DIRECTORY=/opt/people "${IMAGE}" os-committees lint "${STATES[@]}" || STATUS=$?

echo ">>> running: check_duplicate_people.py"
if [[ ${#STATE_ARGS[@]} -gt 0 ]]; then
  docker run --rm "${IMAGE}" python .github/scripts/check_duplicate_people.py "${STATES[@]}" || STATUS=$?
else
  # Intentional word-splitting of CHANGED_FILES -- mirrors CI's own unquoted
  # ${ALL_CHANGED_FILES} usage in lint-yaml.yml to pass multiple filenames.
  docker run --rm "${IMAGE}" python .github/scripts/check_duplicate_people.py --changed-files ${CHANGED_FILES} || STATUS=$?
fi

exit "${STATUS}"
